"""Tables, figures and a markdown write-up for the Part 4 evaluation.

The report is deliberately split into two layers: everything numeric is
computed here and dumped to CSV, and the markdown file states the measured
facts plus explicit prompts for the interpretation that Part 4 is actually
graded on.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import metrics as metric
from . import stats as inference
from .backtest import BacktestResult

METRIC_COLUMNS = {
    "annualized_return": "Annualized return",
    "annualized_volatility": "Annualized volatility",
    "sharpe_ratio": "Sharpe ratio",
    "max_drawdown": "Maximum drawdown",
    "sortino_ratio": "Sortino ratio",
    "calmar_ratio": "Calmar ratio",
    "hit_rate": "Hit rate",
    "total_return": "Total return",
    "annual_turnover": "Annual turnover",
    "total_cost": "Cumulative cost",
}


def metrics_table(results: dict[str, BacktestResult], risk_free=0.0,
                  periods_per_year: int = 12) -> pd.DataFrame:
    """One row per strategy, the four required metrics first."""
    rows = {name: result.metrics(risk_free=risk_free, periods_per_year=periods_per_year)
            for name, result in results.items()}
    table = pd.DataFrame(rows).T
    ordered = [column for column in METRIC_COLUMNS if column in table.columns]
    return table[ordered].rename(columns=METRIC_COLUMNS)


def comparison_table(results: dict[str, BacktestResult], benchmark: str,
                     risk_free=0.0, periods_per_year: int = 12) -> pd.DataFrame:
    """Excess performance and formal tests against the 1/N benchmark."""
    if benchmark not in results:
        raise KeyError(f"benchmark {benchmark!r} is not among the results")
    base = results[benchmark]
    rows = {}
    for name, result in results.items():
        if name == benchmark:
            continue
        common = result.returns.index.intersection(base.returns.index)
        active = result.returns.loc[common] - base.returns.loc[common]
        rf = risk_free.reindex(common) if isinstance(risk_free, pd.Series) else risk_free
        strategy_excess = result.returns.loc[common] - rf
        benchmark_excess = base.returns.loc[common] - rf
        test = inference.sharpe_difference_test(strategy_excess, benchmark_excess)
        alpha = inference.alpha_vs_benchmark(strategy_excess, benchmark_excess, periods_per_year)
        rows[name] = {
            "Excess annualized return": (metric.annualized_return(result.returns, periods_per_year)
                                         - metric.annualized_return(base.returns, periods_per_year)),
            "Tracking error": float(active.std(ddof=1) * np.sqrt(periods_per_year)),
            "Information ratio": float(active.mean() / active.std(ddof=1) * np.sqrt(periods_per_year))
            if active.std(ddof=1) > 0 else float("nan"),
            "Sharpe difference": test["difference"],
            "Sharpe z-statistic": test["z_statistic"],
            "p-value": test["p_value"],
            "Alpha (annualized)": alpha["alpha_annualized"],
            "Alpha t-statistic": alpha["t_statistic"],
            "Beta to 1/N": alpha["beta"],
            "Active hit rate": float((active > 0).mean()),
        }
    return pd.DataFrame(rows).T


def plot_wealth(results: dict[str, BacktestResult], path: Path, benchmark: str,
                title: str = "Out-of-sample wealth") -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9, 5))
    for name, result in results.items():
        wealth = metric.wealth_index(result.returns)
        highlight = name == benchmark
        axis.plot(wealth.index, wealth.to_numpy(), label=name,
                  linewidth=2.4 if highlight else 1.3,
                  linestyle="--" if highlight else "-",
                  color="black" if highlight else None,
                  alpha=1.0 if highlight else 0.85)
    axis.set_title(title)
    axis.set_ylabel("Growth of 1 unit")
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8, ncol=2)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def plot_risk_return(results: dict[str, BacktestResult], path: Path, benchmark: str,
                     periods_per_year: int = 12) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7.5, 5))
    offsets = [(8, 4), (8, -6), (8, 12), (8, -14), (8, 20), (8, -22)]
    for position, (name, result) in enumerate(results.items()):
        volatility = metric.annualized_volatility(result.returns, periods_per_year)
        annual = metric.annualized_return(result.returns, periods_per_year)
        axis.scatter(volatility, annual, s=70, zorder=3)
        axis.annotate(name, (volatility, annual), textcoords="offset points",
                      xytext=offsets[position % len(offsets)], fontsize=8,
                      va="center", ha="left")
    axis.set_xlabel("Annualized volatility")
    axis.set_ylabel("Annualized return")
    axis.set_title("Risk-return map, OOS")
    axis.grid(alpha=0.3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def plot_rolling_sharpe(results: dict[str, BacktestResult], path: Path, benchmark: str,
                        window: int = 24, periods_per_year: int = 12) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(9, 5))
    for name, result in results.items():
        series = result.returns
        if len(series) < window:
            continue
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std(ddof=1)
        rolling = rolling_mean / rolling_std * np.sqrt(periods_per_year)
        highlight = name == benchmark
        axis.plot(rolling.index, rolling.to_numpy(), label=name,
                  linewidth=2.2 if highlight else 1.1,
                  linestyle="--" if highlight else "-",
                  color="black" if highlight else None,
                  alpha=1.0 if highlight else 0.8)
    axis.axhline(0.0, color="grey", linewidth=0.8)
    axis.set_title(f"Rolling {window}-month Sharpe ratio")
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8, ncol=2)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def _markdown_table(frame: pd.DataFrame, float_format: str = "{:.4f}") -> str:
    header = "| " + " | ".join([frame.index.name or "Model"] + [str(column) for column in frame.columns]) + " |"
    separator = "| " + " | ".join(["---"] * (len(frame.columns) + 1)) + " |"
    lines = [header, separator]
    for index, row in frame.iterrows():
        cells = [str(index)]
        for value in row:
            if isinstance(value, (int, np.integer)):
                cells.append(str(int(value)))
            elif isinstance(value, (float, np.floating)):
                cells.append("" if not np.isfinite(value) else float_format.format(value))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(results: dict[str, BacktestResult], benchmark: str, out_dir: Path, *,
                 risk_free=0.0, periods_per_year: int = 12, attribution_tables=None,
                 diagnostics=None, test_tables=None, config: dict | None = None,
                 make_figures: bool = True, sensitivity: pd.DataFrame | None = None) -> dict:
    """Write CSVs, figures and REPORT.md; return the paths that were created."""
    out_dir = Path(out_dir)
    (out_dir / "tables").mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    table = metrics_table(results, risk_free=risk_free, periods_per_year=periods_per_year)
    table.to_csv(out_dir / "tables" / "performance_summary.csv")
    written["performance_summary"] = str(out_dir / "tables" / "performance_summary.csv")

    comparison = comparison_table(results, benchmark, risk_free=risk_free, periods_per_year=periods_per_year)
    comparison.to_csv(out_dir / "tables" / "versus_benchmark.csv")
    written["versus_benchmark"] = str(out_dir / "tables" / "versus_benchmark.csv")

    returns = pd.DataFrame({name: result.returns for name, result in results.items()})
    returns.to_csv(out_dir / "tables" / "oos_returns.csv")
    written["oos_returns"] = str(out_dir / "tables" / "oos_returns.csv")

    if attribution_tables:
        attribution_dir = out_dir / "tables" / "attribution"
        attribution_dir.mkdir(exist_ok=True)
        for label, frame in attribution_tables.items():
            path = attribution_dir / f"{label}.csv"
            frame.to_csv(path)
            written[f"attribution {label}"] = str(path)
    if diagnostics:
        for label, frame in diagnostics.items():
            path = out_dir / "tables" / f"{label}.csv"
            frame.to_csv(path)
            written[label] = str(path)
    if test_tables:
        for label, frame in test_tables.items():
            path = out_dir / "tables" / f"{label}.csv"
            frame.to_csv(path)
            written[label] = str(path)

    if sensitivity is not None and not sensitivity.empty:
        path = out_dir / "tables" / "cost_sensitivity.csv"
        sensitivity.to_csv(path, index=False)
        written["cost_sensitivity"] = str(path)

    if make_figures:
        try:
            written["wealth"] = str(plot_wealth(results, out_dir / "figures" / "wealth.png", benchmark))
            written["risk_return"] = str(plot_risk_return(results, out_dir / "figures" / "risk_return.png", benchmark))
            written["rolling_sharpe"] = str(plot_rolling_sharpe(
                results, out_dir / "figures" / "rolling_sharpe.png", benchmark))
        except ImportError:
            written["figures"] = "matplotlib is not installed; figures skipped"

    lines = ["# Part 4 - out-of-sample performance evaluation", ""]
    if config:
        lines.append("## Run configuration")
        lines.append("")
        for key, value in config.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    lines += ["## Required metrics", "",
              "Every strategy uses the same eligible universe, calendar and cost model. "
              "the 1/N portfolio is the benchmark required by the brief.", "",
              _markdown_table(table), ""]

    lines += ["## Against the 1/N benchmark", "",
              "A positive Sharpe difference is not evidence by itself: the z-statistic uses Memmel's "
              "corrected test, and alpha is Jensen's alpha on the 1/N return with a Newey-West t-statistic.", "",
              _markdown_table(comparison), ""]

    if attribution_tables:
        lines += ["## Where the gap comes from", "",
                  "The gross return gap against the same 1/N benchmark splits into the "
                  "forecast return on active weights and the return from forecast errors.", ""]
        combined = pd.concat(list(attribution_tables.values()))
        lines += [_markdown_table(combined), ""]

    if sensitivity is not None and not sensitivity.empty:
        sharpes = sensitivity.pivot(index="Model", columns="cost_bps", values="sharpe_ratio")
        sharpes.columns = [f"{level:g} bp" for level in sharpes.columns]
        returns = sensitivity.pivot(index="Model", columns="cost_bps", values="annualized_return")
        returns.columns = [f"{level:g} bp" for level in returns.columns]
        lines += ["## Cost sensitivity", "",
                  "One-way transaction cost per unit of traded notional. The ranking is only "
                  "credible at the cost level the group is willing to defend.", "",
                  "Sharpe ratio by cost level:", "", _markdown_table(sharpes), "",
                  "Annualized return by cost level:", "", _markdown_table(returns), ""]

    if diagnostics:
        lines += ["## Weight behaviour", ""]
        for label, frame in diagnostics.items():
            summary = frame.describe().T[["mean", "std", "min", "max"]]
            lines += [f"### {label}", "", _markdown_table(summary), ""]

    report_path = out_dir / "REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    written["report"] = str(report_path)
    return written
