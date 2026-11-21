"""Out-of-sample backtest engine.

Inputs are the Part 1 realised returns and the Part 3 weight file.  For every
forecast origin we look up the realised month it is predicting, apply the
target weights, deduct proportional transaction costs on the traded amount and
compound.  The 1/N benchmark is generated here so that portfolio and benchmark
always see exactly the same universe, calendar and cost model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import metrics as metric


@dataclass
class BacktestResult:
    """Realised performance of one weight path."""

    name: str
    returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    turnovers: pd.Series
    weights: pd.DataFrame

    def metrics(self, risk_free=0.0, periods_per_year: int = 12) -> dict:
        values = metric.summary(self.returns, risk_free=risk_free, periods_per_year=periods_per_year)
        values["average_turnover"] = float(self.turnovers.mean()) if len(self.turnovers) else float("nan")
        values["annual_turnover"] = values["average_turnover"] * periods_per_year
        values["total_cost"] = float(self.costs.sum())
        return values


def equal_weight(origins: pd.Index, assets: list[str]) -> pd.DataFrame:
    """Constant equal-weight portfolio on the same origins and universe."""
    columns = list(assets)
    return pd.DataFrame(1.0 / len(columns), index=pd.DatetimeIndex(origins), columns=columns)


def run_backtest(weights: pd.DataFrame, realised: pd.DataFrame, mapping: pd.Series,
                 *, name: str = "", cost_bps: float = 0.0) -> BacktestResult:
    """Simulate one weight path.

    weights   : origin x asset target weights (already long-only, sum to one)
    realised  : month-end x asset realised simple returns
    mapping   : origin -> realised date (see contracts.target_dates)
    cost_bps  : one-way cost in basis points applied to traded notional
    """
    assets = list(realised.columns)
    weights = weights.reindex(columns=assets).sort_index()

    rows = []
    previous = None
    for origin, target in mapping.items():
        if origin not in weights.index:
            continue
        if target not in realised.index:
            raise ValueError(f"realised return for {target.date()} is missing")
        w = weights.loc[origin].to_numpy(dtype=float)
        if not np.isfinite(w).all():
            raise ValueError(f"{origin.date()}: weights contain NaN")
        if abs(w.sum() - 1.0) > 1e-6:
            raise ValueError(f"{origin.date()}: weights sum to {w.sum():.8f}, not one")
        if (w < -1e-10).any():
            raise ValueError(f"{origin.date()}: negative weights violate the long-only constraint")

        r = realised.loc[target].to_numpy(dtype=float)
        if not np.isfinite(r).all():
            raise ValueError(f"{target.date()}: realised returns contain NaN")

        if previous is None:
            traded = float(np.abs(w).sum())   # buying the whole book from cash
        else:
            grown = previous * (1.0 + r)
            base = grown / grown.sum()        # weights drift with the market
            traded = float(0.5 * np.abs(w - base).sum())
        gross = float(w @ r)
        cost = cost_bps / 1e4 * traded
        rows.append({
            "origin": origin,
            "realised_date": target,
            "gross": gross,
            "cost": cost,
            "net": gross - cost,
            "turnover": traded,
        })
        previous = w

    if not rows:
        raise ValueError("no origin produced a realised return")

    table = pd.DataFrame(rows).set_index("realised_date")
    if table.index.has_duplicates:
        duplicates = table.index[table.index.duplicated()].unique()
        raise ValueError(f"duplicated realised dates: {list(duplicates[:3])}")

    return BacktestResult(
        name=name or "portfolio",
        returns=table["net"].sort_index(),
        gross_returns=table["gross"].sort_index(),
        costs=table["cost"].sort_index(),
        turnovers=table.set_index("origin")["turnover"].sort_index(),
        weights=weights.loc[[origin for origin in table["origin"]]],
    )


def run_models(weight_panels: dict[str, pd.DataFrame], realised: pd.DataFrame, mapping: pd.Series,
               *, cost_bps: float = 0.0, benchmark: str = "1/N") -> dict[str, BacktestResult]:
    """Backtest every model in the Part 3 weight file plus the 1/N benchmark."""
    results = {
        name: run_backtest(panel, realised, mapping, name=name, cost_bps=cost_bps)
        for name, panel in weight_panels.items()
    }
    origins = pd.DatetimeIndex(sorted(set().union(*(panel.index for panel in weight_panels.values()))))
    benchmark_weights = equal_weight(origins, list(realised.columns))
    results[benchmark] = run_backtest(benchmark_weights, realised, mapping, name=benchmark, cost_bps=cost_bps)
    return results


def subperiod_performance(result: BacktestResult, windows: dict[str, tuple[str, str]],
                          risk_free=0.0, periods_per_year: int = 12) -> pd.DataFrame:
    """Performance metrics inside named date windows (inclusive)."""
    rows = {}
    for label, (start, end) in windows.items():
        window = result.returns.loc[start:end]
        if len(window) < 3:
            continue
        rows[label] = metric.summary(window, risk_free=risk_free, periods_per_year=periods_per_year)
    return pd.DataFrame(rows).T


DEFAULT_WINDOWS = {
    "2015 crash and aftermath": ("2015-01-01", "2015-12-31"),
    "2016-2017": ("2016-01-01", "2017-12-31"),
    "2018 de-risking": ("2018-01-01", "2018-12-31"),
    "2019-2020 rally": ("2019-01-01", "2020-12-31"),
    "2021-2022 drawdown": ("2021-01-01", "2022-12-31"),
    "2023-2024": ("2023-01-01", "2024-12-31"),
}
