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
from .tradability import load_eligibility, load_suspensions

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
                     periods_per_year: int = 12, benchmark: str = BENCHMARK,
                     eligibility: pd.DataFrame | None = None,
                     suspensions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Metrics for every model at every cost level, as a tidy long table."""
    rows = []
    for level in levels:
        results = run_models(panels, realised, mapping, cost_bps=level, benchmark=benchmark,
                             eligibility=eligibility, suspensions=suspensions)
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
             cost_levels=None, weights_label: str | None = None,
             tradability_data: Path | None = None, freeze_suspensions: bool = False, per_side_cost: bool = False) -> dict:
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
    eligibility = (load_eligibility(tradability_data, expected.index, assets)
                   if tradability_data is not None else None)
    for name, panel in panels.items():
        panel.drop(columns=[column for column in panel.columns if column not in assets],
                   inplace=True, errors="ignore")
        if not panel.index.equals(mapping.index):
            raise ValueError(f"{name}: weights must cover every forecast origin")
        if eligibility is not None and (panel.where(~eligibility).abs() > 1e-10).any().any():
            raise ValueError(f"{name}: nonzero weights on ineligible assets")

    if freeze_suspensions and tradability_data is None:
        raise ValueError("frozen execution requires tradability data")
    suspensions = load_suspensions(tradability_data, expected.index, assets) if freeze_suspensions else None
    if per_side_cost and suspensions is None:
        suspensions = pd.DataFrame(False, index=expected.index, columns=assets)
    risk_free = monthly_risk_free(risk_free_path, mapping.values)
    results = run_models(panels, actual, mapping, cost_bps=cost_bps, benchmark=BENCHMARK,
                         eligibility=eligibility, suspensions=suspensions)

    attribution_tables = {}
    diagnostics = {}
    for name in panels:
        panel = results[name].weights
        decomposition = attribution_module.decompose(
            panel, expected, actual, mapping, benchmark_weights=results[BENCHMARK].weights
        )
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
        "execution": ("frozen suspended holdings, per-side cash-funded cost" if freeze_suspensions
                      else "immediate targets, per-side cash-funded cost" if per_side_cost
                      else "immediate targets, half-L1 turnover cost after inception"),
        "first realised month": str(realised_dates.min().date()),
        "last realised month": str(realised_dates.max().date()),
    }
    if tradability_data is not None:
        config["tradability data"] = _display_path(tradability_data)
    sensitivity = None
    if cost_levels:
        sensitivity = cost_sensitivity(panels, actual, mapping, cost_levels,
                                       risk_free=risk_free, eligibility=eligibility, suspensions=suspensions)
    written = report_module.write_report(
        results, BENCHMARK, out_dir, risk_free=risk_free, attribution_tables=attribution_tables,
        diagnostics=diagnostics, config=config, make_figures=make_figures,
        sensitivity=sensitivity)

    if suspensions is not None:
        execution_rows = []
        for name, result in results.items():
            result.weights.to_csv(out_dir / "tables" / f"executed_{name.replace('/', '_')}.csv", index_label="Date")
            frozen = result.weights.where(suspensions, 0.0).sum(axis=1)
            execution_rows.append({"Model": name, "MonthsWithFrozenHoldings": int((frozen > 1e-10).sum()),
                                   "MaxFrozenWeight": frozen.max(), "MaxExecutedWeight": result.weights.max().max()})
        pd.DataFrame(execution_rows).to_csv(out_dir / "tables" / "execution.csv", index=False)

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
    parser.add_argument("--tradability-data", type=Path,
                        help="directory for vendor flags; defaults to data/ for the main forecast")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--tag", type=str, default="latest")
    parser.add_argument("--cost-bps", type=float, default=0.0)
    parser.add_argument("--cost-sweep", type=str, default="0,10,30,50",
                        help="comma separated one-way cost levels in bp for the sensitivity table; empty disables it")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--freeze-suspensions", action="store_true")
    execution.add_argument("--per-side-cost", action="store_true",
                           help="fund per-side buy and sell costs with immediate target execution")
    parser.add_argument("--no-figures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    out_dir = arguments.out or (Paths().root / "part4_evaluation" / "reports" / arguments.tag)
    levels = [float(item) for item in arguments.cost_sweep.split(",") if item.strip()]
    expected_path = contracts.resolve_expected_returns(arguments.expected)
    tradability_data = arguments.tradability_data
    if tradability_data is None and expected_path.resolve() == Paths().expected_returns:
        tradability_data = Paths().root / "data"
    written = evaluate(arguments.weights, expected_path, arguments.actual, out_dir,
                       risk_free_path=arguments.risk_free, cost_bps=arguments.cost_bps,
                       make_figures=not arguments.no_figures, cost_levels=levels or None,
                       tradability_data=tradability_data, freeze_suspensions=arguments.freeze_suspensions,
                       per_side_cost=arguments.per_side_cost)
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
