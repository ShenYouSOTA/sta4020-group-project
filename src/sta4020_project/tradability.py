"""Month-end inclusion masks shared by the optimizer and the benchmark."""

import pandas as pd

DELISTED_ASSET = "300330.SZ"
DELISTED_FROM = pd.Timestamp("2023-05-31")


def _close_pairs(data_dir, origins, assets):
    calendar = pd.DatetimeIndex(pd.to_datetime(
        pd.read_csv(data_dir / "risk_free.csv", usecols=["date"])["date"]
    ))
    closes = calendar.to_series().groupby(calendar.to_period("M")).max()
    trading_dates = closes.reindex(origins.to_period("M"))
    if trading_dates.isna().any():
        raise ValueError("trading calendar does not cover all forecast origins")
    return pd.MultiIndex.from_product([trading_dates, assets], names=["date", "asset"])


def load_suspensions(data_dir, origins, assets):
    """Freeze existing holdings when the vendor flags the execution close."""
    pairs = _close_pairs(data_dir, origins, assets)
    blocked = pairs.isin(pd.read_pickle(data_dir / "UNTRADABLE.pkl").index)
    result = pd.DataFrame(blocked.reshape(len(origins), len(assets)), index=origins, columns=assets)
    if DELISTED_ASSET in result:
        result.loc[origins >= DELISTED_FROM, DELISTED_ASSET] = False
    return result


def load_eligibility(data_dir, origins, assets):
    """Use vendor flags at each month's last trading close."""
    pairs = _close_pairs(data_dir, origins, assets)
    allowed = ~pairs.isin(pd.read_pickle(data_dir / "BLACKLIST.pkl").index)
    allowed &= ~pairs.isin(pd.read_pickle(data_dir / "UNTRADABLE.pkl").index)
    result = pd.DataFrame(allowed.reshape(len(origins), len(assets)),
                          index=origins, columns=assets)
    if DELISTED_ASSET in result:
        result.loc[origins >= DELISTED_FROM, DELISTED_ASSET] = False
    if not result.any(axis=1).all():
        raise ValueError("at least one origin has no eligible assets")
    return result
