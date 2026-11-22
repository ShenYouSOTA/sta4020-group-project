"""Run and audit the STA4020 final experiment from the canonical local inputs."""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from . import checks, cli, risk, return_forecasts
from .contracts import Paths, read_weights, read_wide, target_dates
from .final_diagnostics import (
    MVO, final_attribution, prediction_comparison, risk_comparison, table,
)

COST_BPS = 10
MAX_WEIGHT = 0.10


@contextmanager
def descriptor_path(data, supplied):
    if supplied is not None:
        yield supplied
        return
    with TemporaryDirectory(prefix="sta4020-descriptors-") as directory:
        subprocess.run(["unzip", "-q", str(data / "addition" / "descriptors.zip"),
                        "descriptors.pkl", "-d", directory], check=True)
        yield Path(directory) / "descriptors.pkl"


def fingerprint(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def run_final(root, paths, tag, descriptors_path):
    data = root / "data"
    forecast_dir = root / "artifacts/part1" / tag
    risk_dir = root / "artifacts/part2" / tag
    allocation_dir = root / "artifacts/part3" / tag
    report = root / "part4_evaluation/reports" / tag
    experiments = report / "experiments"
    output = report / "tables"
    output.mkdir(parents=True, exist_ok=True)
    logs = report / "logs"
    logs.mkdir(exist_ok=True)
    expected, actual = read_wide(paths.expected_returns), read_wide(paths.actual_returns)
    targets = target_dates(expected.index, actual.index)
    if len(expected.columns) != 50 or len(targets) < 60:
        raise ValueError("the final study requires the fixed 50-stock pool and at least 60 months")
    commands = []

    def build_risk(method, destination, descriptors):
        args = ["--method", method, "--output", str(destination), "--descriptors", str(descriptors)]
        commands.append(["sta4020-build-risk", *args])
        risk.main(args)
        return destination

    def allocate(name, forecast, covariance, *, aversion=5, cap_prior=False, final=False,
                 reuse_weights=None, frozen=True):
        print(f"Running {name}", flush=True)
        weights_dir = allocation_dir if final else allocation_dir / "experiments" / name
        weights = reuse_weights or weights_dir / "Portfolio_Weights.csv"
        target = report if final else experiments / name
        if reuse_weights is None:
            args = [
                "python", "part3_portfolio/Part3.py", "--expected", str(forecast),
                "--covariance", str(covariance), "--tradability-data", str(data),
                "--max-weight", str(MAX_WEIGHT), "--risk-aversion", str(aversion),
                "--risk-free-data", str(data / "risk_free.csv"), "--output-dir", str(weights_dir),
            ]
            if cap_prior:
                args.extend(["--market-caps", str(data / "mcap.pkl")])
            commands.append(args)
            with (logs / f"{name}.log").open("w") as handle:
                process = subprocess.run([sys.executable, *args[1:]], cwd=root,
                                         stdout=handle, stderr=subprocess.STDOUT)
            if process.returncode:
                raise ValueError((logs / f"{name}.log").read_text())
        args = ["--expected", str(forecast), "--weights", str(weights), "--out", str(target),
                "--tradability-data", str(data), "--cost-bps", str(COST_BPS),
                "--freeze-suspensions" if frozen else "--per-side-cost"]
        if not final:
            args.extend(["--cost-sweep", "", "--no-figures"])
        commands.append(["sta4020-evaluate", *args])
        if cli.main(args):
            raise ValueError(f"evaluation failed for {name}")
        return weights, target

    with descriptor_path(data, descriptors_path) as descriptors:
        broad = build_risk("broad-factor", risk_dir / "P2_Covariance.csv", descriptors)
        _, b_fm = allocate("risk-b", paths.expected_returns, broad)
        args = ["--output-dir", str(forecast_dir), "--descriptors", str(descriptors)]
        commands.append(["python", "-m", "sta4020_project.return_forecasts", *args])
        return_forecasts.main(args)
        risk_runs = {"B": (broad, b_fm)}
        for label, method in (("A", "factor"), ("Sample", "sample"), ("Ledoit–Wolf", "ledoit-wolf")):
            cov = build_risk(method, risk_dir / f"{method}.csv", descriptors)
            _, evaluation = allocate(f"risk-{method}", paths.expected_returns, cov)
            risk_runs[label] = cov, evaluation

    forecast_reports = {"fm": b_fm}
    for name in ("extended", "historical"):
        _, evaluation = allocate(f"forecast-{name}", forecast_dir / f"{name}.csv", broad)
        forecast_reports[name] = evaluation
    selection = prediction_comparison(forecast_dir, actual, data, expected.index, output)
    sharpes = {name: table(result, "performance_summary").loc[MVO, "Sharpe ratio"]
               for name, result in forecast_reports.items()}
    selection.update(fm_mvo_sharpe=sharpes["fm"], extended_mvo_sharpe=sharpes["extended"])
    selected = "extended" if (
        selection["ic_gain_ci95"][0] > 0 and selection["high_coverage_ic_gain"] > 0
        and sharpes["extended"] >= sharpes["fm"]
    ) else "fm"
    selection["selected"] = selected
    (report / "model_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    portfolio_tables = []
    for name, evaluation in forecast_reports.items():
        portfolio_tables.append(table(evaluation, "performance_summary").assign(forecast=name))
    pd.concat(portfolio_tables).rename_axis("model").to_csv(output / "forecast_portfolios.csv")

    chosen = forecast_dir / f"{selected}.csv"
    weights, _ = allocate("final", chosen, broad, final=True)
    _, immediate = allocate("immediate", chosen, broad, reuse_weights=weights, frozen=False)
    pd.concat({"Frozen": table(report, "performance_summary"),
               "Immediate": table(immediate, "performance_summary")},
              names=["execution", "model"]).to_csv(output / "execution_sensitivity.csv")
    variants = []
    for aversion in (2, 5, 10):
        for prior in ("Uniform", "Market cap"):
            evaluation = report
            if (aversion, prior) != (5, "Uniform"):
                _, evaluation = allocate(f"allocation-{aversion}-{prior.split()[0].lower()}",
                                         chosen, broad, aversion=aversion, cap_prior=prior == "Market cap")
            variants.append(table(evaluation, "performance_summary").assign(aversion=aversion, prior=prior))
    pd.concat(variants).rename_axis("model").to_csv(output / "portfolio_sensitivity.csv")
    pd.concat({name: table(result, "performance_summary") for name, (_, result) in risk_runs.items()},
              names=["method", "model"]).to_csv(output / "risk_portfolios.csv")

    risk_comparison(risk_runs, report, expected, actual, data, output)
    final_attribution(broad, report, expected, actual, output)
    args = ["--expected", str(chosen), "--covariance", str(broad), "--weights", str(weights)]
    commands.append(["sta4020-check-artifacts", *args])
    if checks.check_artifacts(args):
        raise ValueError("final artifact contract failed")
    allocations = read_weights(weights)
    if allocations["Model"].nunique() != 5 or allocations["Weight"].max() > MAX_WEIGHT + 1e-9:
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

    archive = data / "addition/descriptors.zip"
    inputs = [paths.expected_returns, paths.actual_returns, paths.universe]
    inputs.extend(path for path in (archive, descriptors_path) if path is not None and path.is_file())
    inputs.extend(data / name for name in ("monthly_returns.pkl", "mcap.pkl", "BLACKLIST.pkl",
                  "UNTRADABLE.pkl", "risk_free.csv", "price.h5", "daily_amount.pkl"))

    def relative(path):
        target = Path(path).resolve()
        return str(target.relative_to(root)) if target.is_relative_to(root) else str(target)

    manifest = {
        "tag": tag, "python": sys.version.split()[0],
        "packages": {name: importlib.metadata.version(name)
                     for name in ("numpy", "pandas", "scipy", "h5py", "scikit-learn", "matplotlib")},
        "inputs": {relative(path): fingerprint(path) for path in inputs},
        "origins": [str(expected.index[0].date()), str(expected.index[-1].date())],
        "realization": [str(targets.iloc[0].date()), str(targets.iloc[-1].date())],
        "months": len(targets), "assets": len(expected.columns), "strategies": allocations["Model"].nunique(),
        "cost_bps_per_side": COST_BPS, "target_cap": MAX_WEIGHT, "selected_forecast": selected,
        "reproduce": "uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline",
        "commands": [shlex.join(relative(arg) if arg.startswith(str(root) + "/") else arg
                                for arg in command) for command in commands],
    }
    (report / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Final evaluation and diagnostics: {report}", flush=True)


def main(argv=None):
    paths = Paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="final", help="new output directory name, separate from the interim runs")
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
