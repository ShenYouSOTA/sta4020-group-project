"""Construct and fit the eight-style Part 2 risk model (Implementation A)."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
from risk_model.factor_model import RiskPanel, fit_factor_model
from risk_model.integration import compute_asset_covariance
from risk_model.stable_risk import estimate_factor_covariance, estimate_specific_variance

from ..shared.descriptors import descriptor_fields
from ..shared.market_data import monthly_panel, monthly_risk_free
from ..shared.tradability import DELISTED_ASSET, DELISTED_FROM
from .risk import restore_delisted_asset

STYLES = {
    "size": ("mktcap",),
    "value": ("book_value_to_total_mktcap_mrq", "net_profit_to_total_mktcap_ttm"),
    "momentum": ("momentum_academic_252_21",),
    "reversal": ("momentum_21",),
    "residual_volatility": ("idios_vol_ff3_21",),
    "liquidity": ("turnover_252",),
    "quality": ("return_on_invested_capital_ttm", "gross_profit_to_asset_ttm", "accrual_to_asset_ttm"),
    "leverage": ("total_liab_to_total_asset_mrq",),
}

STYLE_FIELD_NAMES = tuple(sorted({field for components in STYLES.values() for field in components}))


def transform_component(frame: pd.DataFrame, *, log: bool, reverse: bool, standardize: bool) -> pd.DataFrame:
    frame = frame.where(np.isfinite(frame))
    if log:
        frame = np.log(frame.where(frame > 0))
    center = frame.median(axis=1)
    cutoff = frame.sub(center, axis=0).abs().median(axis=1) * (5 * 1.4826)
    # A zero MAD cannot estimate tail width.
    cutoff = cutoff.where(cutoff > 0, np.inf)
    frame = frame.clip(lower=center - cutoff, upper=center + cutoff, axis=0)
    if standardize:
        dispersion = frame.std(axis=1, ddof=1)
        frame = frame.sub(frame.mean(axis=1), axis=0).div(dispersion.where(dispersion > 0), axis=0)
    return -frame if reverse else frame


def build_styles(fields: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    styles = {}
    for name, fields_for_style in STYLES.items():
        components = [
            transform_component(
                fields[field],
                log=field in {"mktcap", "turnover_252"},
                reverse=field in {"momentum_21", "accrual_to_asset_ttm"},
                standardize=len(fields_for_style) > 1,
            )
            for field in fields_for_style
        ]
        styles[name] = pd.concat(components).groupby(level=0).mean()
    return styles


def load_risk_panel(data_dir, returns: pd.DataFrame, extracted_path=None):
    dates, assets = returns.index, returns.columns
    fields = descriptor_fields(data_dir, extracted_path, dates, assets, STYLE_FIELD_NAMES)
    caps = monthly_panel(pd.read_pickle(data_dir / "mcap.pkl"), dates, assets)
    observed = fields["mktcap"].notna()
    if not np.allclose(fields["mktcap"].to_numpy()[observed], caps.to_numpy()[observed], rtol=1e-6, atol=0):
        raise ValueError("descriptors['mktcap'] diverges from data/mcap.pkl beyond 1e-6")
    delisted = dates >= DELISTED_FROM
    if DELISTED_ASSET in assets:
        caps.loc[delisted, DELISTED_ASSET] = np.nan
        caps[DELISTED_ASSET] = caps[DELISTED_ASSET].ffill()
        for frame in fields.values():
            frame.loc[delisted, DELISTED_ASSET] = np.nan

    styles = build_styles(fields)
    if DELISTED_ASSET in assets:
        for style in styles.values():
            style[DELISTED_ASSET] = style[DELISTED_ASSET].ffill().where(delisted, style[DELISTED_ASSET])
    missing = {name: style.isna().mean(axis=1) for name, style in styles.items()}
    filled = [style.T.fillna(style.median(axis=1)).T.to_numpy() for style in styles.values()]

    risk_free = monthly_risk_free(data_dir / "risk_free.csv", dates)
    if not isinstance(risk_free, pd.Series):
        raise ValueError("valid daily risk-free data is required for the factor model")
    panel = RiskPanel(
        dates=dates.to_numpy(), asset_ids=assets.to_numpy(),
        returns=returns.sub(risk_free, axis=0).to_numpy(),
        style_values=np.stack(filled, axis=-1), style_ids=np.array(list(STYLES)),
        industry_membership=np.full(returns.shape, "Market"), industry_ids=np.array(["Market"]),
        market_caps=caps.to_numpy(),
    )
    return panel, pd.DataFrame(missing).rename_axis("Date")


def factor_covariances(panel, origins):
    """Use expanding factor and residual sample estimates through each origin."""
    assets = pd.Index(panel.asset_ids)
    before = panel.dates < DELISTED_FROM.to_datetime64()
    has_delisting = DELISTED_ASSET in assets and np.any(~before)
    split = int(before.sum()) if has_delisting else len(panel.dates)
    early = fit_factor_model(replace(
        panel, dates=panel.dates[:split], returns=panel.returns[:split],
        style_values=panel.style_values[:split], market_caps=panel.market_caps[:split],
        industry_membership=panel.industry_membership[:split],
    ))
    if has_delisting:
        active = np.asarray(assets != DELISTED_ASSET)
        start = split - 1
        later = fit_factor_model(replace(
            panel, dates=panel.dates[start:], asset_ids=panel.asset_ids[active],
            returns=panel.returns[start:, active], market_caps=panel.market_caps[start:, active],
            style_values=panel.style_values[start:, active],
            industry_membership=panel.industry_membership[start:, active],
        ))
        factors = np.concatenate([early.factor_returns, later.factor_returns])
        active_residuals = np.concatenate([early.residuals[:, active], later.residuals])
        frozen = early.residuals[:, ~active].var(ddof=1)

    for origin in origins:
        i = int(panel.dates.searchsorted(origin.to_datetime64()))
        if i < 2:
            raise ValueError(f"need at least three observations at {origin.date()}")
        if i < split:
            exposures, factor_returns, residuals = early.exposures[i], early.factor_returns, early.residuals
        else:
            exposures, factor_returns, residuals = later.exposures[i - start], factors, active_residuals
        factor_covariance = estimate_factor_covariance(factor_returns[:i], eigenfactor_adjustment=False)
        specific_variances = estimate_specific_variance(residuals[:i])
        covariance = compute_asset_covariance(exposures, factor_covariance, specific_variances)
        yield covariance if i < split else restore_delisted_asset(covariance, assets, frozen)
