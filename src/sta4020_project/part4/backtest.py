"""Out-of-sample backtest engine with explicit execution modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import metrics as metric


class ExecutionMode(StrEnum):
    """How monthly rebalances handle trading restrictions and transaction costs."""

    LEGACY_HALF_L1 = "legacy_half_l1"
    IMMEDIATE_PER_SIDE = "immediate_per_side"
    FROZEN_PER_SIDE = "frozen_per_side"


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


def execute_rebalance(target, previous, suspended, cost_rate):
    """Solve the post-fee stock budget while keeping suspended shares fixed."""
    if not 0 <= cost_rate < 1:
        raise ValueError("per-side transaction cost must be in [0, 1)")
    if np.any(target[suspended] > 1e-10):
        raise ValueError("target requires purchases in a suspended name")
    frozen = np.where(suspended, previous, 0.0)
    budget = 1.0 - frozen.sum()

    def turnover(fee):
        holdings = frozen + target * (budget - fee)
        return np.abs(holdings - previous).sum()

    fee = (brentq(lambda value: value - cost_rate * turnover(value), 0.0, budget,
                  xtol=1e-14) if cost_rate and budget > 0 else 0.0)
    return (frozen + target * (budget - fee)) / (1.0 - fee), turnover(fee), fee


def _resolve_execution_mode(
    execution_mode: ExecutionMode | None,
    suspensions: pd.DataFrame | None,
) -> ExecutionMode:
    if execution_mode is not None:
        if execution_mode == ExecutionMode.FROZEN_PER_SIDE and suspensions is None:
            raise ValueError("FROZEN_PER_SIDE execution requires a suspensions mask")
        return execution_mode
    return ExecutionMode.FROZEN_PER_SIDE if suspensions is not None else ExecutionMode.LEGACY_HALF_L1


def run_backtest(weights: pd.DataFrame, realised: pd.DataFrame, mapping: pd.Series,
                 *, name: str = "", cost_bps: float = 0.0,
                 suspensions: pd.DataFrame | None = None,
                 execution_mode: ExecutionMode | None = None) -> BacktestResult:
    """Simulate one weight path."""
    mode = _resolve_execution_mode(execution_mode, suspensions)
    assets = list(realised.columns)
    weights = weights.reindex(columns=assets).sort_index()
    no_blocks = np.zeros(len(assets), dtype=bool)

    rows, executed = [], []
    drifted_weights = None
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

        if mode in (ExecutionMode.FROZEN_PER_SIDE, ExecutionMode.IMMEDIATE_PER_SIDE):
            previous = np.zeros_like(w) if drifted_weights is None else drifted_weights
            blocked = (
                suspensions.loc[origin, assets].to_numpy(dtype=bool)
                if mode == ExecutionMode.FROZEN_PER_SIDE
                else no_blocks
            )
            w, traded, cost = execute_rebalance(w, previous, blocked, cost_bps / 1e4)
            gross = float(w @ r)
            net = (1.0 - cost) * (1.0 + gross) - 1.0
        else:
            traded = (float(np.abs(w).sum()) if drifted_weights is None
                      else float(0.5 * np.abs(w - drifted_weights).sum()))
            gross = float(w @ r)
            cost = cost_bps / 1e4 * traded
            net = gross - cost
        executed.append(w)
        rows.append({
            "origin": origin,
            "realised_date": target,
            "gross": gross,
            "cost": cost,
            "net": net,
            "turnover": traded,
        })
        holdings = w * (1.0 + r)
        if holdings.sum() <= 0:
            raise ValueError(f"{target.date()}: portfolio wealth exhausted")
        drifted_weights = holdings / holdings.sum()

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
        weights=pd.DataFrame(executed, index=pd.DatetimeIndex(table["origin"]), columns=assets),
    )


def run_models(weight_panels: dict[str, pd.DataFrame], realised: pd.DataFrame, mapping: pd.Series,
               *, cost_bps: float = 0.0, benchmark: str = "1/N",
               eligibility: pd.DataFrame | None = None,
               suspensions: pd.DataFrame | None = None,
               execution_mode: ExecutionMode | None = None) -> dict[str, BacktestResult]:
    """Backtest every model in the Part 3 weight file plus the 1/N benchmark."""
    results = {
        name: run_backtest(
            panel, realised, mapping, name=name, cost_bps=cost_bps,
            suspensions=suspensions, execution_mode=execution_mode,
        )
        for name, panel in weight_panels.items()
    }
    origins = pd.DatetimeIndex(sorted(set().union(*(panel.index for panel in weight_panels.values()))))
    benchmark_weights = equal_weight(origins, list(realised.columns))
    if eligibility is not None:
        eligible = eligibility.loc[origins, realised.columns]
        benchmark_weights = eligible.div(eligible.sum(axis=1), axis=0)
    results[benchmark] = run_backtest(
        benchmark_weights, realised, mapping, name=benchmark, cost_bps=cost_bps,
        suspensions=suspensions, execution_mode=execution_mode,
    )
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
