from dataclasses import replace

import numpy as np

from . import dynamic_risk as dynamic, integration, stable_risk as stable
from .factor_model import fit_factor_model
from ._validation import _dates


def forecast_risk(
    panel, as_of, *, factor_covariance=None, covariance_shrinkage=None,
    specific_shrinkage=None, dynamic_variance=None, integration_method="rescale",
    rescaling_level="factor", rescaling=None, factor_blending=None, specific_blending=None,
):
    """Estimate stable risk, then either rescale or blend with dynamic forecasts."""
    blending = integration_method == "blend"
    level = "factor" if blending else rescaling_level
    if level not in ("factor", "stock") or integration_method not in ("rescale", "blend"):
        raise ValueError("unsupported integration_method or rescaling_level")
    rescaling = {} if blending else (rescaling or {})
    panel = _truncate_panel(panel, as_of)
    factors, stable_cov, specific_var = _estimate_stable_risk(
        panel, level, factor_covariance, covariance_shrinkage,
        specific_shrinkage, rescaling, blending,
    )
    variance, specific = _estimate_dynamic_risk(panel, factors, level, dynamic_variance)
    if level == "stock":
        stock_covariance = integration.rescale_covariance(stable_cov, np.sqrt(variance), **rescaling)
        return stock_covariance
    # Blending needs this (K,K) dynamic input, built with fixed stable factor correlation.
    dynamic_factor_cov = integration.rescale_covariance(stable_cov, np.sqrt(variance), **rescaling)
    factor_cov = dynamic_factor_cov
    if blending:
        factor_cov = integration.blend_risk(stable_cov, dynamic_factor_cov, **(factor_blending or {}))
        specific = integration.blend_risk(specific_var, specific, **(specific_blending or {}))
    return integration.compute_asset_covariance(factors.exposures[-1], factor_cov, specific)


def _truncate_panel(panel, as_of):
    dates = _dates(panel.dates)
    cutoff = np.datetime64(as_of, "ns")
    if np.isnat(cutoff):
        raise ValueError("as_of must be a valid date")
    count = int(np.searchsorted(dates, cutoff, side="right"))
    histories = {}
    for field in ("returns", "style_values", "industry_membership", "market_caps"):
        values = np.asarray(getattr(panel, field))
        if values.ndim == 0 or len(values) != len(dates):
            raise ValueError(f"{field} must share the panel date axis")
        histories[field] = values[:count]
    return replace(panel, dates=dates[:count], **histories)


def _estimate_stable_risk(
    panel, level, factor_options, covariance_shrinkage, specific_shrinkage, correlation, blending,
):
    # 1. Select a stable estimate at the required matrix dimension.
    stock_shrinkage = covariance_shrinkage if level == "stock" else None
    options = stock_shrinkage if stock_shrinkage is not None else correlation
    use_factor_model = (options or {}).get("method", "factor_model") == "factor_model"
    # 2. Estimate the required factor and specific components.
    factors = None
    if level == "factor" or use_factor_model:
        factors = fit_factor_model(panel)
    factor_cov = None
    if use_factor_model:
        factor_cov = stable.estimate_factor_covariance(
            factors.factor_returns, **(factor_options or {})
        )
    specific_var = None
    if (level == "stock" and use_factor_model) or blending:
        specific_var = stable.estimate_specific_variance(factors.residuals)
        if specific_shrinkage is not None:
            specific_var = stable.shrink_specific_variance(
                specific_var, panel.market_caps[-1], **specific_shrinkage
            )
    # 3. Select the stable covariance input: (K,K) factors or (N,N) stocks.
    stable_cov = factor_cov
    if level == "stock" and use_factor_model:
        stable_cov = integration.compute_asset_covariance(
            factors.exposures[-1], factor_cov, specific_var
        )
    if stock_shrinkage is not None:
        stable_cov = stable.shrink_covariance(
            stable._sample_covariance(panel.returns), target_covariance=stable_cov,
            returns=panel.returns, **stock_shrinkage,
        )
    elif not use_factor_model:
        history = panel.returns if level == "stock" else factors.factor_returns
        stable_cov = stable._sample_covariance(history)
    return factors, stable_cov, specific_var


def _estimate_dynamic_risk(panel, factors, level, options):
    histories = [panel.returns] if level == "stock" else [factors.factor_returns, factors.residuals]
    variances = [
        dynamic.estimate_dynamic_variance(history, **(options or {})).forecast_variance
        for history in histories
    ]
    return (variances[0], None) if level == "stock" else variances
