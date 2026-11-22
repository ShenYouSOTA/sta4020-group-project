"""Broad monthly factor fits and fixed-universe covariance forecasts (Implementation B)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from risk_model.factor_model import factor_holdings
from risk_model.integration import compute_asset_covariance
from risk_model.stable_risk import estimate_factor_covariance

from ..shared.descriptors import descriptor_fields
from ..shared.market_data import monthly_panel, monthly_risk_free
from ..shared.tradability import DELISTED_ASSET, DELISTED_FROM
from .risk import write_covariances
from .styles import STYLE_FIELD_NAMES, build_styles


@dataclass
class BroadHistory:
    factors: pd.DataFrame
    residuals: pd.DataFrame
    exposures: np.ndarray
    coverage: pd.DataFrame


def estimate_history(returns, caps, styles, fixed_assets, specific_start, *, max_names: int = 800) -> BroadHistory:
    """Normalize using the formation sample, before filtering for observed labels."""
    dates = returns.index
    positions = returns.columns.get_indexer(fixed_assets)
    if (positions < 0).any() or not caps.index.equals(dates) or not caps.columns.equals(returns.columns):
        raise ValueError("broad panel and fixed assets are misaligned")
    values = returns.to_numpy()
    caps = caps.to_numpy()
    exposures, factors, residuals, coverage = [], [], [], []
    factor_names = ["market", "industry", *styles]
    for i, date in enumerate(dates):
        raw = np.column_stack([frame.iloc[i].to_numpy() for frame in styles.values()])
        eligible = np.isfinite(raw).all(axis=1) & np.isfinite(caps[i]) & (caps[i] > 0)
        if DELISTED_ASSET in returns and date >= DELISTED_FROM:
            eligible[returns.columns.get_loc(DELISTED_ASSET)] = False
        available = np.flatnonzero(eligible)
        ordered = np.argsort(-caps[i, available], kind="stable")
        selected = available[ordered[:max_names]]
        if len(selected) < 100:
            raise ValueError(f"{date:%Y-%m}: only {len(selected)} assets with complete styles")
        reference = raw[selected]
        center = np.average(reference, weights=caps[i, selected], axis=0)
        scale = reference.std(axis=0, ddof=1)
        if (scale <= 0).any():
            raise ValueError(f"{date:%Y-%m}: style dispersion is zero")
        fixed = raw[positions]
        missing = ~np.isfinite(fixed)
        filled = np.where(missing, np.median(reference, axis=0), fixed)
        fixed_exposure = np.column_stack([np.ones((len(positions), 2)), (filled - center) / scale])
        exposures.append(fixed_exposure)
        audit = {
            "Formation": date, "Realization": pd.NaT,
            "CompleteStyleNames": len(available), "SelectedAtFormation": len(selected),
            "WithRealizedReturn": np.nan,
            **{f"Missing_{name}": count for name, count in zip(styles, missing.sum(axis=0), strict=True)},
        }
        coverage.append(audit)
        if i == len(dates) - 1:
            break
        realized = dates[i + 1]
        fit = selected[np.isfinite(values[i + 1, selected])]
        if DELISTED_ASSET in returns and realized >= DELISTED_FROM:
            fit = fit[fit != returns.columns.get_loc(DELISTED_ASSET)]
        if len(fit) < 100:
            raise ValueError(f"{realized:%Y-%m}: only {len(fit)} realized assets for WLS")
        dummies = np.ones((len(fit), 1))
        design = np.column_stack([np.ones(len(fit)), dummies, (raw[fit] - center) / scale])
        factor = factor_holdings(design, caps[i, fit], dummies) @ values[i + 1, fit]
        factors.append(factor)
        residual = values[i + 1, positions] - fixed_exposure @ factor
        if realized >= DELISTED_FROM and DELISTED_ASSET in fixed_assets:
            residual[fixed_assets.get_loc(DELISTED_ASSET)] = np.nan
        if realized < specific_start:
            residual[:] = np.nan
        residuals.append(residual)
        audit.update(Realization=realized, WithRealizedReturn=len(fit))
    return BroadHistory(
        pd.DataFrame(factors, index=dates[1:].rename("Realization"), columns=factor_names),
        pd.DataFrame(residuals, index=dates[1:].rename("Realization"), columns=fixed_assets),
        np.stack(exposures), pd.DataFrame(coverage),
    )


def load_history(data_dir, descriptors, origins, fixed_assets, specific_start, broad_start) -> BroadHistory:
    dates = pd.date_range(broad_start, origins[-1] + pd.offsets.MonthEnd(), freq="ME")
    raw_returns = pd.read_pickle(data_dir / "monthly_returns.pkl")
    assets = raw_returns.columns[raw_returns.columns.str.fullmatch(r"\d{6}\.(SH|SZ)")].sort_values()
    returns = monthly_panel(raw_returns, dates, assets)
    caps = monthly_panel(pd.read_pickle(data_dir / "mcap.pkl"), dates, assets)
    fields = descriptor_fields(data_dir, descriptors, dates, assets, STYLE_FIELD_NAMES)
    common = np.isfinite(fields["mktcap"]) & np.isfinite(caps)
    if not np.allclose(fields["mktcap"].to_numpy()[common], caps.to_numpy()[common], rtol=1e-6, atol=0):
        raise ValueError("descriptors['mktcap'] diverges from data/mcap.pkl beyond 1e-6")
    # Remove carried quotes after delisting before cross-sectional transforms.
    if DELISTED_ASSET in assets:
        for field in fields.values():
            field.loc[dates >= DELISTED_FROM, DELISTED_ASSET] = np.nan
    styles = build_styles(fields)
    risk_free = monthly_risk_free(data_dir / "risk_free.csv", dates)
    if not isinstance(risk_free, pd.Series):
        raise ValueError("valid daily risk-free data is required for the factor model")
    return estimate_history(returns.sub(risk_free, axis=0), caps, styles, fixed_assets, specific_start)


def forecast_components(history: BroadHistory, origins):
    """Use only factor and residual returns realized by each forecast origin."""
    dates = pd.DatetimeIndex(history.coverage["Formation"])
    for origin in origins:
        i = dates.get_loc(origin)
        available_factors = history.factors.loc[:origin]
        available_residuals = history.residuals.loc[:origin]
        factor_covariance = estimate_factor_covariance(
            available_factors.to_numpy(), eigenfactor_adjustment=False)
        specific = available_residuals.var(ddof=1).to_numpy()
        exposure = history.exposures[i].copy()
        if origin >= DELISTED_FROM and DELISTED_ASSET in available_residuals:
            exposure[available_residuals.columns.get_loc(DELISTED_ASSET)] = 0.0
        if not np.isfinite(specific).all() or (specific <= 0).any():
            raise ValueError(f"{origin:%Y-%m}: nonpositive or missing specific variance")
        yield exposure, factor_covariance, specific


def write_broad_risk(path, history: BroadHistory, origins, assets) -> None:
    components = list(forecast_components(history, origins))
    write_covariances(path, origins, assets,
                      (compute_asset_covariance(*parts) for parts in components))
    exposures, factor_covariances, specific = map(np.stack, zip(*components, strict=True))
    np.savez_compressed(path.with_suffix(".components.npz"), origins=origins.to_numpy(),
                        assets=np.asarray(assets, dtype=str), exposures=exposures,
                        factor_covariances=factor_covariances, specific_variances=specific)
    rows = []
    for origin in origins:
        factor_index = history.factors.loc[:origin].index
        residual_counts = history.residuals.loc[:origin].count()
        if factor_index[-1] != origin:
            raise ValueError(f"{origin:%Y-%m}: factor history stops before the origin")
        rows.append({"Origin": origin, "FirstFactorRealization": factor_index[0],
                     "LastFactorRealization": factor_index[-1], "FactorMonths": len(factor_index),
                     "MinSpecificMonths": residual_counts.min(),
                     "MaxSpecificMonths": residual_counts.max()})
    pd.DataFrame(rows).to_csv(path.with_suffix(".history.csv"), index=False)
    history.factors.to_csv(path.with_suffix(".factors.csv"))
    history.coverage.to_csv(path.with_suffix(".coverage.csv"), index=False)
