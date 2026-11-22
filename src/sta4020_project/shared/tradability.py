"""Month-end inclusion and delisting masks shared across all parts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DELISTED_ASSET = "300330.SZ"
DELISTED_FROM = pd.Timestamp("2023-05-31")
DEFAULT_DELISTINGS: dict[str, pd.Timestamp] = {DELISTED_ASSET: DELISTED_FROM}


def active_mask(
    dates: pd.DatetimeIndex,
    assets: pd.Index | list[str],
    delistings: dict[str, pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """Return boolean (dates x assets) mask that is False on/after delisting dates."""
    rules = DEFAULT_DELISTINGS if delistings is None else delistings
    mask = pd.DataFrame(True, index=dates, columns=assets)
    for asset, cutoff in rules.items():
        if asset in mask.columns:
            mask.loc[dates >= cutoff, asset] = False
    return mask


def _close_pairs(data_dir: Path, origins: pd.DatetimeIndex, assets) -> pd.MultiIndex:
    calendar = pd.DatetimeIndex(pd.to_datetime(
        pd.read_csv(data_dir / "risk_free.csv", usecols=["date"])["date"]
    ))
    closes = calendar.to_series().groupby(calendar.to_period("M")).max()
    trading_dates = closes.reindex(origins.to_period("M"))
    if trading_dates.isna().any():
        raise ValueError("trading calendar does not cover all forecast origins")
    return pd.MultiIndex.from_product([trading_dates, assets], names=["date", "asset"])


def load_suspensions(
    data_dir: Path,
    origins: pd.DatetimeIndex,
    assets,
    *,
    delistings: dict[str, pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """Freeze existing holdings when the vendor flags the execution close."""
    pairs = _close_pairs(data_dir, origins, assets)
    blocked = pairs.isin(pd.read_pickle(data_dir / "UNTRADABLE.pkl").index)
    result = pd.DataFrame(blocked.reshape(len(origins), len(assets)), index=origins, columns=assets)
    rules = DEFAULT_DELISTINGS if delistings is None else delistings
    for asset, cutoff in rules.items():
        if asset in result.columns:
            result.loc[origins >= cutoff, asset] = False
    return result


def load_eligibility(
    data_dir: Path,
    origins: pd.DatetimeIndex,
    assets,
    *,
    delistings: dict[str, pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """Use vendor flags at each month's last trading close."""
    pairs = _close_pairs(data_dir, origins, assets)
    allowed = ~pairs.isin(pd.read_pickle(data_dir / "BLACKLIST.pkl").index)
    allowed &= ~pairs.isin(pd.read_pickle(data_dir / "UNTRADABLE.pkl").index)
    result = pd.DataFrame(allowed.reshape(len(origins), len(assets)), index=origins, columns=assets)
    result &= active_mask(origins, assets, delistings=delistings)
    if not result.any(axis=1).all():
        raise ValueError("at least one origin has no eligible assets")
    return result
