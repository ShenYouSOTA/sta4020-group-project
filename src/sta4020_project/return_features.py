"""Headless version of the Part 1 notebook's Shanghai/Shenzhen feature builder."""

import h5py
import numpy as np
import pandas as pd

MIN_FACTOR_PAIRS = 100
TRAIN_MONTHS = 72
RISK_MONTHS = 36


def month_index(frame):
    frame = frame.copy()
    frame.index = pd.DatetimeIndex(frame.index).to_period("M")
    frame = frame.sort_index()
    assert frame.index.is_unique and frame.columns.is_unique
    return frame


def restrictions_on_days(path, days):
    records = pd.read_pickle(path).index
    dates = records.get_level_values("date")
    selected = records[dates.isin(days)]
    return {
        pd.Timestamp(date): pd.Index(rows.index.get_level_values("asset").unique())
        for date, rows in selected.to_frame(index=True).groupby(level="date", sort=False)
    }


def load_daily_amount(path, days, asset_columns):
    amount = pd.read_pickle(path)["total_turnover"]
    date_level = amount.index.levels[1]
    keep = date_level.isin(days)[amount.index.codes[1]]
    wide = amount.loc[keep].unstack("order_book_id")
    wide.columns = (
        wide.columns.str.replace(".XSHE", ".SZ", regex=False)
        .str.replace(".XSHG", ".SH", regex=False)
    )
    assert wide.index.is_unique and wide.columns.is_unique
    return wide.reindex(index=days, columns=asset_columns).astype("float32")



def pca_exposures(history):
    complete = history.dropna(axis=1)
    assert complete.shape[1] >= MIN_FACTOR_PAIRS
    centered = complete.to_numpy() - complete.to_numpy().mean(axis=0)
    variances, directions = np.linalg.eigh(centered @ centered.T)
    top = directions[:, -3:][:, ::-1]
    market_direction = centered.mean(axis=1)
    direction = top[:, 0] * (1 if top[:, 0] @ market_direction >= 0 else -1)
    # Scale PC1 to the volatility of the equal-weight reference return.
    factor = direction * np.linalg.norm(market_direction)
    loading = (factor @ centered) / (factor @ factor)
    residual = centered - top @ (top.T @ centered)
    pca_features = pd.DataFrame({
        "pc1_market_beta": loading,
        "pca_residual_volatility": residual.std(axis=0, ddof=1),
    }, index=complete.columns)
    explained = variances[-3:][::-1] / variances.sum()
    return pca_features, explained


class ReturnFeatures:
    def __init__(self, data_dir, origins):
        raw_returns = month_index(pd.read_pickle(data_dir / "monthly_returns.pkl"))
        market_cap = month_index(pd.read_pickle(data_dir / "mcap.pkl"))
        first_formation = origins[0]
        first_feature_month = first_formation - (TRAIN_MONTHS + 1)
        last_target = origins[-1] + 1
        formation_months = pd.period_range(first_feature_month, last_target - 1, freq="M")
        assert raw_returns.loc[:last_target].index.equals(pd.period_range(raw_returns.index[0], last_target, freq="M"))

        with h5py.File(data_dir / "price.h5", "r") as price_file:
            store = price_file["price"]
            trading_days = pd.DatetimeIndex(store["axis1"][:])
            price_columns = pd.Index(store["axis0"].asstr()[:], name="Asset")
            assert price_columns.equals(pd.Index(store["block0_items"].asstr()[:]))
            assert trading_days.is_unique and trading_days.is_monotonic_increasing
            start = trading_days.searchsorted((first_feature_month - 5).start_time)
            finish = trading_days.searchsorted(last_target.end_time, side="right")
            prices = pd.DataFrame(
                store["block0_values"][start:finish], index=trading_days[start:finish],
                columns=price_columns,
            )

        assets = prices.columns.intersection(raw_returns.columns).sort_values()
        assets = assets[assets.str.fullmatch(r"\d{6}\.(SZ|SH)")]
        prices = prices.reindex(columns=assets).where(lambda values: values.gt(0))
        returns = raw_returns.reindex(columns=assets).replace([np.inf, -np.inf], np.nan)
        market_cap = market_cap.reindex(columns=assets)
        assert not returns.lt(-1).any().any()

        exchange_month = pd.Series(prices.index, index=prices.index).groupby(prices.index.to_period("M"))
        last_close = exchange_month.last()
        signal_close = exchange_month.nth(-2)
        signal_close.index = signal_close.index.to_period("M")
        assert (signal_close.reindex(formation_months) < last_close.reindex(formation_months)).all()

        audit_days = pd.Index(signal_close.reindex(formation_months)).union(
            pd.Index(last_close.reindex(origins))
        )
        blacklist = restrictions_on_days(data_dir / "BLACKLIST.pkl", audit_days)
        untradable = restrictions_on_days(data_dir / "UNTRADABLE.pkl", audit_days)
        daily_amount = load_daily_amount(data_dir / "daily_amount.pkl", prices.index, assets)
        assert daily_amount.notna().sum().sum() > 100_000

        daily_returns = prices.pct_change(fill_method=None)
        week_end_prices = (
            prices.loc[pd.Series(prices.index).groupby(prices.index.to_period("W-FRI")).last().to_numpy()]
            .set_axis(pd.Index(prices.index.to_period("W-FRI").unique().end_time.normalize()))
        )
        weekly_returns = week_end_prices.pct_change(fill_method=None)
        self.signal_close = signal_close
        self.returns = returns
        self.daily_amount = daily_amount
        self.market_cap = market_cap
        self.blacklist = blacklist
        self.untradable = untradable
        self.assets = assets
        self.prices = prices
        self.daily_returns = daily_returns
        self.weekly_returns = weekly_returns
        self.last_close = last_close

    def at(self, month):
        as_of = self.signal_close.loc[month]
        monthly_history = self.returns.loc[month - RISK_MONTHS:month - 1]
        recent_amount = self.daily_amount.loc[:as_of].tail(21)
        previous_cap = self.market_cap.loc[month - 1]
        blocked = self.blacklist.get(as_of, pd.Index([])).union(self.untradable.get(as_of, pd.Index([])))
        eligible = (
            self.prices.loc[as_of].notna()
            & previous_cap.gt(0)
            & monthly_history.tail(12).notna().all(axis=0)
            & ~self.assets.isin(blocked)
        )
        eligible_assets = self.assets[eligible]
        assert len(eligible_assets) >= MIN_FACTOR_PAIRS
        monthly_history = monthly_history.loc[:, eligible_assets]
        pca_features, _ = pca_exposures(monthly_history)

        daily = self.daily_returns.loc[:as_of].tail(63).loc[:, eligible_assets]
        weekly = self.weekly_returns.loc[:as_of].tail(12).loc[:, eligible_assets]
        mean_amount = recent_amount.loc[:, eligible_assets].mean().where(
            recent_amount.loc[:, eligible_assets].count().ge(15)
        )
        prior_close = self.last_close.loc[month - 1]
        raw = pd.DataFrame({
            "log_size": np.log(previous_cap.loc[eligible_assets]),
            "log_amount_21d": np.log1p(mean_amount.where(mean_amount.ge(0))),
            "return_5d": (1 + daily.tail(5)).prod(min_count=5) - 1,
            "volatility_63d": daily.std().where(daily.count().ge(50)),
            "momentum_8w": (1 + weekly.tail(8)).prod(min_count=8) - 1,
            "volatility_12w": weekly.std().where(weekly.count().ge(10)),
            "momentum_12_1m": (1 + monthly_history.iloc[-12:-1]).prod(min_count=11) - 1,
            "lagged_month_return": monthly_history.iloc[-1],
            "return_month_to_signal": (
                self.prices.loc[as_of, eligible_assets] / self.prices.loc[prior_close, eligible_assets] - 1
            ),
        }).join(pca_features).replace([np.inf, -np.inf], np.nan)

        return raw
