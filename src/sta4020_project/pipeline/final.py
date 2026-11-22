"""Run and audit the STA4020 final experiment from the canonical local inputs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from ..part1 import forecasts as return_forecasts
from ..part2 import risk
from ..part4 import cli
from ..part4.diagnostics import (
    MVO, final_attribution, high_coverage_portfolios, prediction_comparison, risk_comparison, table,
)
from ..shared.config import FinalExperimentConfig
from ..shared.contracts import Paths, read_covariance_panel, read_weights, read_wide, target_dates
from ..shared.market_data import monthly_panel, monthly_risk_free
from ..shared.tradability import load_eligibility
from . import checks
from .sample import load_part3_module


@contextmanager
def descriptor_path(data: Path, supplied: Path | None):
    if supplied is not None:
        yield supplied
        return
    with TemporaryDirectory(prefix="sta4020-descriptors-") as directory:
        subprocess.run(
            ["unzip", "-q", str(data / "addition" / "descriptors.zip"), "descriptors.pkl", "-d", directory],
            check=True,
        )
        yield Path(directory) / "descriptors.pkl"


def fingerprint(path: Path) -> dict:
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def _validate_calendar(expected: pd.DataFrame, actual: pd.DataFrame) -> pd.Series:
    targets = target_dates(expected.index, actual.index)
    if len(expected.columns) != 50 or len(targets) < 60:
        raise ValueError("the final study requires the fixed 50-stock pool and at least 60 months")
    origins = expected.index.to_period("M")
    if (not origins.equals(pd.period_range(origins[0], origins[-1], freq="M"))
            or not pd.DatetimeIndex(targets).to_period("M").equals(origins + 1)):
        raise ValueError("the final study requires consecutive origins and exact next-month outcomes")
    return targets


def _audit_final_gates(
    chosen: Path,
    broad: Path,
    weights: Path,
    output: Path,
    targets: pd.Series,
    max_weight: float,
    commands: list[list[str]],
) -> pd.DataFrame:
    args = ["--expected", str(chosen), "--covariance", str(broad), "--weights", str(weights)]
    commands.append(["sta4020-check-artifacts", *args])
    if checks.check_artifacts(args):
        raise ValueError("final artifact contract failed")
    allocations = read_weights(weights)
    if allocations["Model"].nunique() != 5 or allocations["Weight"].max() > max_weight + 1e-9:
        raise ValueError("final target weights fail the five-strategy or weight cap check")
    coverage = pd.read_csv(broad.with_suffix(".coverage.csv"), parse_dates=["Formation", "Realization"])
    realized = coverage["Realization"].dropna()
    if not ((coverage.loc[realized.index, "Formation"] + pd.offsets.MonthEnd()) == realized).all():
        raise ValueError("factor realization dates are misaligned")
    diagnostics = pd.read_csv(output / "covariance_diagnostics.csv", index_col="method")
    if diagnostics.loc["B", "months_positive_definite"] != len(targets):
        raise ValueError("B must be positive definite at every origin")
    if diagnostics.loc["B", "max_top5_trace_share"] >= 0.95:
        raise ValueError("B covariance exceeds the top-five eigenvalue concentration gate")
    style_correlations = pd.read_csv(output / "style_correlations.csv", index_col=0).to_numpy()
    off_diagonal = ~np.eye(len(style_correlations), dtype=bool)
    style_vif = pd.read_csv(output / "style_vif.csv", index_col=0).to_numpy()
    if style_correlations[off_diagonal].max() >= 0.7 or style_vif.max() >= 5:
        raise ValueError("B style exposures exceed the correlation or VIF gate")
    return allocations


def run_final(
    root: Path,
    paths: Paths,
    tag: str,
    descriptors_path: Path | None,
    *,
    config: FinalExperimentConfig | None = None,
) -> None:
    cfg = config or FinalExperimentConfig()
    data = root / "data"
    forecast_dir = root / "artifacts/part1" / tag
    risk_dir = root / "artifacts/part2" / tag
    allocation_dir = root / "artifacts/part3" / tag
    report = root / "part4_evaluation/reports" / tag
    experiments = report / "experiments"
    output = report / "tables"

    for directory in (forecast_dir, risk_dir, allocation_dir, report):
        if directory.exists():
            raise FileExistsError(f"tag {tag} is already in use at {directory}; choose a fresh --tag")
    output.mkdir(parents=True)

    expected, actual = read_wide(paths.expected_returns), read_wide(paths.actual_returns)
    targets = _validate_calendar(expected, actual)
    assets = sorted(set(expected.columns) & set(actual.columns))

    # Preload shared read-only frames once across all Part 3 allocations.
    part3 = load_part3_module(root)
    shared_eligibility = load_eligibility(data, expected.index, assets)
    shared_mcap = monthly_panel(pd.read_pickle(data / "mcap.pkl"), expected.index, assets)
    shared_rf = monthly_risk_free(data / "risk_free.csv", expected.index)
    covariance_cache: dict[Path, dict[pd.Timestamp, np.ndarray]] = {}
    commands: list[list[str]] = []

    def recorded_descriptor_args(descriptors: Path) -> list[str]:
        return ["--descriptors", str(descriptors)] if descriptors_path is not None else []

    def build_risk(method: str, destination: Path, descriptors: Path) -> Path:
        args = ["--method", method, "--output", str(destination)]
        commands.append(["sta4020-build-risk", *args, *recorded_descriptor_args(descriptors)])
        risk.main([*args, "--descriptors", str(descriptors)])
        return destination

    def allocate(
        name: str,
        forecast: Path,
        covariance: Path,
        *,
        aversion: float = cfg.part3.risk_aversion,
        cap_prior: bool = False,
        final: bool = False,
        reuse_weights: Path | None = None,
        copy_to_final_dir: bool = False,
        frozen: bool = True,
    ) -> tuple[Path, Path]:
        print(f"Running {name}", flush=True)
        weights_dir = allocation_dir if final else allocation_dir / "experiments" / name
        weights = weights_dir / "Portfolio_Weights.csv"
        target = report if final else experiments / name
        if reuse_weights is not None:
            if copy_to_final_dir:
                weights_dir.mkdir(parents=True, exist_ok=True)
                for fname in (
                    "Portfolio_Weights.csv",
                    "OOS_Portfolio_Returns.csv",
                    "Forecast_Portfolio_Metrics.csv",
                    "Tradability_Diagnostics.csv",
                ):
                    src = reuse_weights.parent / fname
                    if src.is_file():
                        shutil.copy2(src, weights_dir / fname)
            else:
                weights = reuse_weights
        else:
            cli_record = [
                "python", "part3_portfolio/Part3.py", "--expected", str(forecast),
                "--covariance", str(covariance), "--tradability-data", str(data),
                "--max-weight", str(cfg.part3.max_weight), "--risk-aversion", str(aversion),
                "--risk-free-data", str(data / "risk_free.csv"), "--output-dir", str(weights_dir),
            ]
            if cap_prior:
                cli_record.extend(["--market-caps", str(data / "mcap.pkl")])
            commands.append(cli_record)
            if covariance not in covariance_cache:
                covariance_cache[covariance] = read_covariance_panel(covariance, assets=assets)
            part3.run_part3(
                forecast,
                covariance,
                paths.actual_returns,
                weights_dir,
                risk_aversion=aversion,
                max_weight=cfg.part3.max_weight,
                covariance_panel=covariance_cache[covariance],
                eligibility=shared_eligibility,
                market_caps=shared_mcap if cap_prior else None,
                origin_risk_free=shared_rf,
            )

        eval_args = [
            "--expected", str(forecast), "--weights", str(weights), "--out", str(target),
            "--tradability-data", str(data), "--cost-bps", str(cfg.part4.cost_bps),
            "--freeze-suspensions" if frozen else "--per-side-cost",
        ]
        if not final:
            eval_args.extend(["--cost-sweep", "", "--no-figures"])
        commands.append(["sta4020-evaluate", *eval_args])
        if cli.main(eval_args):
            raise ValueError(f"evaluation failed for {name}")
        return weights, target

    with descriptor_path(data, descriptors_path) as descriptors:
        broad = build_risk("broad-factor", risk_dir / "P2_Covariance.csv", descriptors)
        b_fm_weights, b_fm = allocate("risk-b", paths.expected_returns, broad)
        args = ["--output-dir", str(forecast_dir)]
        commands.append(["sta4020-build-returns", *args, *recorded_descriptor_args(descriptors)])
        return_forecasts.main([*args, "--descriptors", str(descriptors)])
        risk_runs = {"B": (broad, b_fm)}
        for label, method in (("A", "factor"), ("Sample", "sample"), ("Ledoit–Wolf", "ledoit-wolf")):
            cov = build_risk(method, risk_dir / f"{method}.csv", descriptors)
            _, evaluation = allocate(f"risk-{method}", paths.expected_returns, cov)
            risk_runs[label] = cov, evaluation

    forecast_reports = {"fm": b_fm}
    forecast_weights = {"fm": b_fm_weights}
    for name in ("extended", "historical"):
        w_path, evaluation = allocate(f"forecast-{name}", forecast_dir / f"{name}.csv", broad)
        forecast_reports[name] = evaluation
        forecast_weights[name] = w_path

    selection = prediction_comparison(forecast_dir, actual, data, expected.index, output)
    sharpes = {name: table(result, "performance_summary").loc[MVO, "Sharpe ratio"]
               for name, result in forecast_reports.items()}
    selection.update(fm_mvo_sharpe=sharpes["fm"], extended_mvo_sharpe=sharpes["extended"])
    selected = "extended" if (
        selection["ic_gain_ci95"][0] > 0 and selection["high_coverage_ic_gain"] > 0
        and sharpes["extended"] >= sharpes["fm"]
    ) else "fm"
    selection["selected"] = selected
    selection["high_coverage_years"] = high_coverage_portfolios(forecast_reports, data, output)
    (report / "model_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    portfolio_tables = [
        table(evaluation, "performance_summary").assign(forecast=name)
        for name, evaluation in forecast_reports.items()
    ]
    pd.concat(portfolio_tables).rename_axis("model").to_csv(output / "forecast_portfolios.csv")

    chosen = forecast_dir / f"{selected}.csv"
    # Reuse already-optimized target weights for the selected forecast instead of re-solving SLSQP.
    weights, _ = allocate(
        "final", chosen, broad, final=True,
        reuse_weights=forecast_weights[selected], copy_to_final_dir=True,
    )
    _, immediate = allocate("immediate", chosen, broad, reuse_weights=weights, frozen=False)
    pd.concat({"Frozen": table(report, "performance_summary"),
               "Immediate": table(immediate, "performance_summary")},
              names=["execution", "model"]).to_csv(output / "execution_sensitivity.csv")

    variants = []
    for aversion in cfg.part3.sensitivity_aversions:
        for prior in cfg.part3.sensitivity_priors:
            evaluation = report
            if (aversion, prior) != (cfg.part3.risk_aversion, "Uniform"):
                _, evaluation = allocate(
                    f"allocation-{aversion}-{prior.split()[0].lower()}",
                    chosen, broad, aversion=aversion, cap_prior=prior == "Market cap",
                )
            variants.append(table(evaluation, "performance_summary").assign(aversion=aversion, prior=prior))
    pd.concat(variants).rename_axis("model").to_csv(output / "portfolio_sensitivity.csv")
    pd.concat({name: table(result, "performance_summary") for name, (_, result) in risk_runs.items()},
              names=["method", "model"]).to_csv(output / "risk_portfolios.csv")

    risk_comparison(risk_runs, report, expected, actual, data, output)
    final_attribution(broad, report, expected, actual, output)
    allocations = _audit_final_gates(chosen, broad, weights, output, targets, cfg.part3.max_weight, commands)

    archive = data / "addition/descriptors.zip"
    inputs = [paths.expected_returns, paths.actual_returns, paths.universe]
    inputs.extend(path for path in (archive, descriptors_path) if path is not None and path.is_file())
    inputs.extend(data / name for name in (
        "monthly_returns.pkl", "mcap.pkl", "BLACKLIST.pkl",
        "UNTRADABLE.pkl", "risk_free.csv", "price.h5", "daily_amount.pkl",
    ))

    def relative(path) -> str:
        target_path = Path(path).resolve()
        return str(target_path.relative_to(root)) if target_path.is_relative_to(root) else str(target_path)

    manifest = {
        "tag": tag,
        "python": sys.version.split()[0],
        "packages": {name: importlib.metadata.version(name)
                     for name in ("numpy", "pandas", "scipy", "h5py", "scikit-learn", "matplotlib")},
        "config": cfg.to_dict(),
        "inputs": {relative(path): fingerprint(path) for path in inputs},
        "origins": [str(expected.index[0].date()), str(expected.index[-1].date())],
        "realization": [str(targets.iloc[0].date()), str(targets.iloc[-1].date())],
        "months": len(targets),
        "assets": len(expected.columns),
        "strategies": allocations["Model"].nunique(),
        "cost_bps_per_side": cfg.part4.cost_bps,
        "target_cap": cfg.part3.max_weight,
        "selected_forecast": selected,
        "reproduce": ("uv run --locked --extra risk --extra final sta4020-run-final --tag " + shlex.quote(tag)),
        "command_note": "Run subcommands in the locked risk and final uv environment from the repository root.",
        "commands": [shlex.join(relative(arg) if arg.startswith(str(root) + "/") else arg
                                for arg in command) for command in commands],
    }
    (report / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Final evaluation and diagnostics: {report}", flush=True)


def main(argv=None) -> int:
    paths = Paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="final", help="new output directory name, separate from interim runs")
    parser.add_argument("--descriptors", type=Path, help="optional extracted descriptor pickle")
    args = parser.parse_args(argv)
    if not args.tag.startswith("final") or not args.tag.replace("-", "").isalnum():
        parser.error("tag must start with 'final' and contain only letters, digits and hyphens")
    if args.descriptors is not None:
        args.descriptors = args.descriptors.resolve()
    run_final(paths.root, paths, args.tag, args.descriptors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
