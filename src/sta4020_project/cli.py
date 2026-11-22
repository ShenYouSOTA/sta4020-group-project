"""Command line entry point for the Part 4 evaluation.

Example:
    python -m sta4020_project.cli --tag sample --cost-bps 10

With no arguments it reads the canonical artifacts:
artifacts/part1/P1_Expected_Returns.csv, artifacts/part1/Actual_Returns.csv,
artifacts/part3/Portfolio_Weights.csv and writes to
part4_evaluation/reports/<tag>/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import attribution as attribution_module
from . import contracts
from . import report as report_module
from .backtest import DEFAULT_WINDOWS, run_models, subperiod_performance
from .contracts import Paths

BENCHMARK = "1/N"


def monthly_risk_free(path: Path | None, dates: pd.Index) -> pd.Series | float:
    """Compound the daily risk-free file into the months spanned by dates."""
    if path is None or not Path(path).exists():
        return 0.0
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "RF" not in frame.columns:
        return 0.0
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values("date")
    growth = (1.0 + pd.to_numeric(frame["RF"], errors="raise"))
    periods = pd.PeriodIndex(frame["date"], freq="M")
    monthly = growth.groupby(periods).prod() - 1.0
    wanted = pd.PeriodIndex(pd.DatetimeIndex(dates), freq="M")
    values = monthly.reindex(wanted)
    if values.isna().any():
        values = values.fillna(0.0)
    return pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates))


def cost_sensitivity(panels: dict[str, pd.DataFrame], realised: pd.DataFrame,
                     mapping: pd.Series, levels, *, risk_free=0.0,
                     periods_per_year: int = 12, benchmark: str = BENCHMARK) -> pd.DataFrame:
    """Metrics for every model at every cost level, as a tidy long table."""
    rows = []
    for level in levels:
        results = run_models(panels, realised, mapping, cost_bps=level, benchmark=benchmark)
        for name, result in results.items():
            values = result.metrics(risk_free=risk_free, periods_per_year=periods_per_year)
            rows.append({
                "cost_bps": float(level),
                "Model": name,
                "annualized_return": values["annualized_return"],
                "annualized_volatility": values["annualized_volatility"],
                "sharpe_ratio": values["sharpe_ratio"],
                "max_drawdown": values["max_drawdown"],
                "annual_turnover": values["annual_turnover"],
            })
    return pd.DataFrame(rows)


def evaluate(weights_path: Path, expected_path: Path, actual_path: Path, out_dir: Path, *,
             risk_free_path: Path | None = None, cost_bps: float = 0.0,
             make_figures: bool = True, windows: dict | None = None,
             cost_levels=None, weights_label: str | None = None) -> dict:
    """Run the full Part 4 evaluation and return the written paths."""
    expected = contracts.read_wide(expected_path, label=Path(expected_path).name)
    actual = contracts.read_wide(actual_path, label="Actual_Returns")
    weights = contracts.read_weights(weights_path)

    assets = [column for column in expected.columns if column in actual.columns]
    if len(assets) < contracts.MIN_ASSETS:
        raise ValueError(f"only {len(assets)} common assets; the brief requires at least 20")
    expected = expected[assets]
    actual = actual[assets]

    mapping = contracts.target_dates(expected.index, actual.index)
    panels = contracts.weights_to_wide(weights)
    for name, panel in panels.items():
        panel.drop(columns=[column for column in panel.columns if column not in assets],
                   inplace=True, errors="ignore")

    risk_free = monthly_risk_free(risk_free_path, mapping.values)
    results = run_models(panels, actual, mapping, cost_bps=cost_bps, benchmark=BENCHMARK)

    attribution_tables = {}
    diagnostics = {}
    for name, panel in panels.items():
        decomposition = attribution_module.decompose(panel, expected, actual, mapping)
        summary = attribution_module.summarise(decomposition)
        frame = pd.DataFrame([summary])
        frame.index = pd.Index([name], name="Model")
        attribution_tables[name] = frame
        diagnostics[name] = attribution_module.weight_diagnostics(panel, expected, mapping)

    subperiods = {}
    for name, result in results.items():
        subperiods[name] = subperiod_performance(
            result, windows or DEFAULT_WINDOWS, risk_free=risk_free)

    realised_dates = pd.DatetimeIndex(mapping.to_numpy())
    config = {
        "weights file": weights_label or _display_path(weights_path),
        "expected returns": _display_path(expected_path),
        "realised returns": _display_path(actual_path),
        "assets": len(assets),
        "origins": len(panels[list(panels)[0]].index) if panels else 0,
        "realised months": len(realised_dates),
        "transaction cost (bp, one-way)": cost_bps,
        "first realised month": str(realised_dates.min().date()),
        "last realised month": str(realised_dates.max().date()),
    }
    sensitivity = None
    if cost_levels:
        sensitivity = cost_sensitivity(panels, actual, mapping, cost_levels,
                                       risk_free=risk_free)
    written = report_module.write_report(
        results, BENCHMARK, out_dir, risk_free=risk_free, attribution_tables=attribution_tables,
        diagnostics=diagnostics, config=config, make_figures=make_figures,
        sensitivity=sensitivity)

    subperiod_dir = out_dir / "tables" / "subperiods"
    subperiod_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in subperiods.items():
        slug = name.replace("/", "_").replace(" ", "_").lower()
        frame.to_csv(subperiod_dir / f"{slug}.csv")
    written["subperiods"] = str(subperiod_dir)
    return written


def _display_path(path) -> str:
    """Report a path relative to the repository root so the log is portable."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(Paths().root.resolve()))
    except ValueError:
        return str(resolved)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Part 4 out-of-sample evaluation")
    root = Paths().root
    parser.add_argument("--weights", type=Path, default=Paths().weights)
    parser.add_argument("--expected", type=Path, default=None,
                        help="Part 1 forecast file; defaults to the current main forecast")
    parser.add_argument("--actual", type=Path, default=Paths().actual_returns)
    parser.add_argument("--risk-free", type=Path, default=root / "data" / "risk_free.csv")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--tag", type=str, default="latest")
    parser.add_argument("--cost-bps", type=float, default=0.0)
    parser.add_argument("--cost-sweep", type=str, default="0,10,30,50",
                        help="comma separated one-way cost levels in bp for the sensitivity table; empty disables it")
    parser.add_argument("--no-figures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    out_dir = arguments.out or (Paths().root / "part4_evaluation" / "reports" / arguments.tag)
    levels = [float(item) for item in arguments.cost_sweep.split(",") if item.strip()]
    expected_path = contracts.resolve_expected_returns(arguments.expected)
    written = evaluate(arguments.weights, expected_path, arguments.actual, out_dir,
                       risk_free_path=arguments.risk_free, cost_bps=arguments.cost_bps,
                       make_figures=not arguments.no_figures, cost_levels=levels or None)
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
