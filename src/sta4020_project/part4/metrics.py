"""Performance metrics required by the Part 4 brief.

Every function takes simple (not log) periodic returns in decimal units and
works on whatever frequency is implied by periods_per_year.  The project runs
on monthly data, so the default is 12.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 12


def _series(returns) -> pd.Series:
    series = pd.Series(returns, dtype=float).dropna()
    if series.empty:
        raise ValueError("empty return series")
    return series


def wealth_index(returns, initial: float = 1.0) -> pd.Series:
    """Compounded wealth index; the first value already includes month 1."""
    return initial * (1.0 + _series(returns)).cumprod()


def annualized_return(returns, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    """Geometric CAGR implied by the realised path."""
    series = _series(returns)
    growth = float(np.prod(1.0 + series.to_numpy()))
    if growth <= 0:
        return -1.0
    return growth ** (periods_per_year / len(series)) - 1.0


def annualized_volatility(returns, periods_per_year: int = PERIODS_PER_YEAR, ddof: int = 1) -> float:
    return float(_series(returns).std(ddof=ddof) * np.sqrt(periods_per_year))


def _risk_free_per_period(risk_free, index: pd.Index) -> np.ndarray:
    if risk_free is None:
        return np.zeros(len(index))
    if np.isscalar(risk_free):
        return np.full(len(index), float(risk_free))
    series = pd.Series(risk_free, dtype=float).reindex(index)
    if series.isna().any():
        raise ValueError("risk-free series does not cover the return index")
    return series.to_numpy()


def sharpe_ratio(returns, risk_free=0.0, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    """Annualised Sharpe ratio; risk_free is a per-period rate."""
    series = _series(returns)
    excess = series.to_numpy() - _risk_free_per_period(risk_free, series.index)
    deviation = float(excess.std(ddof=1))
    if not np.isfinite(deviation) or deviation < 1e-15:
        return float("nan")
    return float(excess.mean() / deviation * np.sqrt(periods_per_year))


def drawdown_series(returns) -> pd.Series:
    wealth = wealth_index(returns)
    return wealth / wealth.cummax() - 1.0


def max_drawdown(returns) -> float:
    """Most negative peak-to-trough drawdown, as a negative decimal."""
    return float(drawdown_series(returns).min())


def max_drawdown_details(returns) -> dict:
    """Peak, trough and recovery dates of the worst drawdown."""
    series = _series(returns)
    wealth = wealth_index(series)
    drawdown = wealth / wealth.cummax() - 1.0
    trough = drawdown.idxmin()
    peak = wealth.loc[:trough].idxmax()
    after = wealth.loc[trough:]
    recovered = after[after >= wealth.loc[peak]]
    return {
        "max_drawdown": float(drawdown.min()),
        "peak": peak,
        "trough": trough,
        "recovery": recovered.index[0] if len(recovered) else None,
        "length_months": int(series.index.get_loc(trough) - series.index.get_loc(peak)),
    }


def downside_deviation(returns, risk_free=0.0, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    series = _series(returns)
    excess = series.to_numpy() - _risk_free_per_period(risk_free, series.index)
    shortfall = np.minimum(excess, 0.0)
    return float(np.sqrt(np.mean(shortfall ** 2)) * np.sqrt(periods_per_year))


def sortino_ratio(returns, risk_free=0.0, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    series = _series(returns)
    excess = series.to_numpy() - _risk_free_per_period(risk_free, series.index)
    downside = downside_deviation(series, risk_free, periods_per_year)
    if downside == 0:
        return float("nan")
    return float(excess.mean() * periods_per_year / downside)


def calmar_ratio(returns, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    drawdown = max_drawdown(returns)
    if drawdown == 0:
        return float("nan")
    return float(annualized_return(returns, periods_per_year) / abs(drawdown))


def hit_rate(returns) -> float:
    series = _series(returns)
    return float((series > 0).mean())


def turnover(previous, current) -> float:
    """One-way turnover 0.5 * sum|w_new - w_old| between two weight vectors."""
    left = np.asarray(previous, dtype=float)
    right = np.asarray(current, dtype=float)
    if left.shape != right.shape:
        raise ValueError("weight vectors must have the same length")
    return float(0.5 * np.abs(right - left).sum())


def concentration(weights) -> dict:
    """Herfindahl index and effective number of holdings for one weight vector."""
    vector = np.asarray(weights, dtype=float)
    if vector.ndim != 1:
        raise ValueError("weights must be one-dimensional")
    total = vector.sum()
    if total <= 0:
        raise ValueError("weights must have positive total")
    share = vector / total
    hhi = float((share ** 2).sum())
    return {
        "hhi": hhi,
        "effective_n": float(1.0 / hhi),
        "max_weight": float(share.max()),
        "non_zero": int((share > 1e-9).sum()),
    }


def summary(returns, risk_free=0.0, periods_per_year: int = PERIODS_PER_YEAR) -> dict:
    """The four metrics required by the brief plus the usual companions."""
    series = _series(returns)
    return {
        "annualized_return": annualized_return(series, periods_per_year),
        "annualized_volatility": annualized_volatility(series, periods_per_year),
        "sharpe_ratio": sharpe_ratio(series, risk_free, periods_per_year),
        "max_drawdown": max_drawdown(series),
        "sortino_ratio": sortino_ratio(series, risk_free, periods_per_year),
        "calmar_ratio": calmar_ratio(series, periods_per_year),
        "hit_rate": hit_rate(series),
        "periods": int(len(series)),
        "total_return": float((1.0 + series).prod() - 1.0),
    }
