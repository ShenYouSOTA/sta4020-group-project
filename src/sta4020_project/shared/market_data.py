"""Shared market-data alignment helpers (zero dependency on Part 1–4)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def monthly_panel(frame: pd.DataFrame, dates: pd.DatetimeIndex, assets) -> pd.DataFrame:
    """Align trading-day and calendar month-ends without changing asset order."""
    aligned = frame.copy()
    aligned.index = pd.DatetimeIndex(aligned.index).to_period("M")
    result = aligned.reindex(index=dates.to_period("M"), columns=assets)
    result.index = dates
    return result


def monthly_risk_free(path: Path | None, dates: pd.Index) -> pd.Series | float:
    """Compound the daily risk-free file into the months spanned by dates."""
    if path is None or not Path(path).exists():
        return 0.0
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "RF" not in frame.columns:
        return 0.0
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values("date")
    growth = 1.0 + pd.to_numeric(frame["RF"], errors="raise")
    periods = pd.PeriodIndex(frame["date"], freq="M")
    monthly = growth.groupby(periods).prod() - 1.0
    wanted = pd.PeriodIndex(pd.DatetimeIndex(dates), freq="M")
    values = monthly.reindex(wanted)
    if values.isna().any():
        values = values.fillna(0.0)
    return pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates))
