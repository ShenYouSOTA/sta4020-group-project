"""Stable covariance estimates and the lecture shrinkage methods."""

import numpy as np
from sklearn.covariance import ledoit_wolf_shrinkage

from ._validation import _array, _covariance, _history, _number, _tolerance


def _sample_covariance(returns):
    returns = _history(returns)
    centered = returns - returns.mean(axis=0)
    return centered.T @ centered / (len(returns) - 1)


def estimate_factor_covariance(
    factor_returns, *, eigenfactor_adjustment=True, simulations=1000, a=1.0
):
    """Estimate sample factor covariance, optionally adjusting eigenvalues."""
    returns = _history(factor_returns, "factor_returns")
    sample = _sample_covariance(returns)
    if not isinstance(eigenfactor_adjustment, (bool, np.bool_)):
        raise ValueError("eigenfactor_adjustment must be Boolean")
    if not eigenfactor_adjustment:
        return sample
    if isinstance(simulations, (bool, np.bool_)) or not isinstance(
        simulations, (int, np.integer)
    ) or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    a = _number(a, "a")
    if a <= 0:
        raise ValueError("a must be positive")
    values, vectors = np.linalg.eigh(sample)
    positive = values > _tolerance(sample)
    values, vectors = values[positive], vectors[:, positive]
    if not len(values):
        return sample
    rng = np.random.default_rng(0)
    correction = np.zeros(len(values))
    for _ in range(simulations):
        draws = rng.normal(size=(len(returns), len(values))) * np.sqrt(values)
        simulated = _sample_covariance(draws)
        eigenvalues, rotation = np.linalg.eigh(simulated)
        if np.any(eigenvalues <= _tolerance(simulated)):
            raise ValueError("undefined eigenfactor correction denominator")
        true_variance = (rotation ** 2).T @ values
        correction += np.sqrt(true_variance / eigenvalues)
    correction = a * (correction / simulations - 1) + 1
    adjusted = (vectors * (values * correction ** 2)) @ vectors.T
    return _covariance(adjusted)


def estimate_specific_variance(residuals):
    """Return sample variances without shrinkage."""
    return _history(residuals, "residuals").var(axis=0, ddof=1)


def shrink_covariance(
    sample_covariance, method="factor_model", *, w=0.5,
    target_covariance=None, returns=None
):
    """Shrink a supplied matrix; estimate no factor or specific components."""
    sample = _covariance(sample_covariance, "sample_covariance")
    size = len(sample)
    if method == "ledoit_wolf":
        history = _history(returns)
        expected = _sample_covariance(history)
        if expected.shape != sample.shape or not np.allclose(
            expected, sample, rtol=1e-8, atol=_tolerance(sample)
        ):
            raise ValueError("returns must generate the supplied sample covariance")
        w = ledoit_wolf_shrinkage(history)
        target = np.eye(size) * np.trace(sample) / size
    else:
        w = _number(w, "w", 0, 1)
        if method == "factor_model":
            target = _covariance(target_covariance, "target_covariance")
            if target.shape != sample.shape:
                raise ValueError("target_covariance shape must match sample")
        elif method == "scaled_identity":
            target = np.eye(size) * np.trace(sample) / size
        elif method == "constant_correlation":
            variance = sample.diagonal()
            if np.any(variance <= 0):
                raise ValueError("constant correlation needs positive variances")
            scale = np.sqrt(np.outer(variance, variance))
            correlation = sample / scale
            rho = correlation[~np.eye(size, dtype=bool)].mean() if size > 1 else 1
            target = rho * scale
            np.fill_diagonal(target, variance)
        else:
            raise ValueError(f"unknown covariance shrinkage method: {method}")
    return _covariance(w * target + (1 - w) * sample)


def shrink_specific_variance(specific_variance, market_caps, q=1.0):
    """Bayesian shrinkage of volatility toward size-decile priors."""
    variance = _array(specific_variance, 1, "specific_variance")
    caps = _array(market_caps, 1, "market_caps")
    q = _number(q, "q", 0)
    if variance.shape != caps.shape or len(variance) < 10:
        raise ValueError("Bayesian shrinkage needs at least ten matching stocks")
    if np.any(variance < 0) or np.any(caps <= 0):
        raise ValueError("variances must be nonnegative and caps positive")
    volatility = np.sqrt(variance)
    adjusted = volatility.copy()
    for group in np.array_split(np.argsort(caps, kind="stable"), 10):
        prior = np.average(volatility[group], weights=caps[group])
        distance = np.abs(volatility[group] - prior)
        dispersion = np.sqrt(np.mean((volatility[group] - prior) ** 2))
        denominator = dispersion + q * distance
        weight = np.divide(
            q * distance, denominator, out=np.zeros_like(distance),
            where=denominator > 0,
        )
        adjusted[group] = weight * prior + (1 - weight) * volatility[group]
    return adjusted ** 2
