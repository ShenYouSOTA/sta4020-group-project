"""Covariance rescaling, blending and stock covariance construction."""

import numpy as np

from ._validation import _array, _covariance
from .stable_risk import shrink_covariance


def _correlation(covariance):
    matrix = _covariance(covariance)
    variance = matrix.diagonal()
    if np.any(variance <= 0):
        raise ValueError("correlation requires positive covariance diagonal")
    return matrix / np.sqrt(np.outer(variance, variance))


def _rescale(correlation, forecast_volatility):
    volatility = _array(forecast_volatility, 1, "forecast_volatility")
    if len(volatility) != len(correlation) or np.any(volatility < 0):
        raise ValueError("forecast_volatility must match and be nonnegative")
    return _covariance(correlation * np.outer(volatility, volatility))


def rescale_covariance(
    covariance, forecast_volatility, method="factor_model", *, w=0.5
):
    """Keep or modify stable correlation and apply forecast volatilities."""
    correlation = _correlation(covariance)
    if method == "constant_correlation":
        size = len(correlation)
        off_diagonal = ~np.eye(size, dtype=bool)
        rho = correlation[off_diagonal].mean() if size > 1 else 1.0
        correlation = np.full_like(correlation, rho)
        np.fill_diagonal(correlation, 1.0)
    elif method == "shrinkage":
        correlation = shrink_covariance(correlation, method="scaled_identity", w=w)
    elif method not in ("factor_model", "historical_average"):
        raise ValueError(f"unknown correlation method: {method}")
    return _rescale(correlation, forecast_volatility)


def blend_risk(stable_estimate, dynamic_estimate, stable_weight=0.5):
    """Blend covariance matrices or specific-variance vectors."""
    stable = np.asarray(stable_estimate, dtype=float)
    if stable.ndim == 2:
        stable = _covariance(stable, "stable_estimate")
        dynamic = _covariance(dynamic_estimate, "dynamic_estimate")
    elif stable.ndim == 1:
        stable = _array(stable, 1, "stable_estimate")
        dynamic = _array(dynamic_estimate, 1, "dynamic_estimate")
        if np.any(stable < 0) or np.any(dynamic < 0):
            raise ValueError("specific variances must be nonnegative")
    else:
        raise ValueError("estimates must be matrices or variance vectors")
    if stable.shape != dynamic.shape or not stable.size:
        raise ValueError("estimates must have matching nonempty shapes")
    weight = np.asarray(stable_weight, dtype=float)
    vector_allowed = stable.ndim == 1 and weight.shape == stable.shape
    if weight.ndim != 0 and not vector_allowed:
        raise ValueError("per-stock weights apply only to variance vectors")
    if not np.isfinite(weight).all() or np.any((weight < 0) | (weight > 1)):
        raise ValueError("stable_weight must lie between zero and one")
    result = weight * stable + (1 - weight) * dynamic
    return _covariance(result) if result.ndim == 2 else result


def compute_asset_covariance(exposures, factor_covariance, specific_variance):
    """Combine factor covariance with diagonal specific variance."""
    exposures = _array(exposures, 2, "exposures")
    factors = _covariance(factor_covariance, "factor_covariance")
    specific = _array(specific_variance, 1, "specific_variance")
    if exposures.shape != (len(specific), len(factors)) or not len(specific):
        raise ValueError("exposures must match stocks and factors")
    if np.any(specific < 0):
        raise ValueError("specific variances must be nonnegative")
    return _covariance(exposures @ factors @ exposures.T + np.diag(specific))
