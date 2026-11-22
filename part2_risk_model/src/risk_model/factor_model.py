"""Barra exposures, constrained WLS and pure factor portfolios."""

from dataclasses import dataclass

import numpy as np

from ._validation import _array, _dates, _history, _ids


@dataclass
class RiskPanel:
    dates: np.ndarray
    asset_ids: np.ndarray
    returns: np.ndarray
    style_values: np.ndarray
    style_ids: np.ndarray
    industry_membership: np.ndarray
    industry_ids: np.ndarray
    market_caps: np.ndarray


@dataclass
class FactorResult:
    factor_returns: np.ndarray
    residuals: np.ndarray
    exposures: np.ndarray
    pure_factor_portfolios: np.ndarray


def _panel_arrays(panel):
    returns = _history(panel.returns)
    times, stocks = returns.shape
    dates = _dates(panel.dates)
    assets = _ids(panel.asset_ids, "asset_ids")
    styles = _ids(panel.style_ids, "style_ids", allow_empty=True)
    industries = _ids(panel.industry_ids, "industry_ids")
    values = _array(panel.style_values, 3, "style_values")
    caps = _array(panel.market_caps, 2, "market_caps")
    membership = np.asarray(panel.industry_membership)
    if len(dates) != times or len(assets) != stocks:
        raise ValueError("dates and asset_ids must match returns")
    if values.shape != (times, stocks, len(styles)):
        raise ValueError("style_values must match dates, stocks and style_ids")
    if caps.shape != returns.shape or np.any(caps <= 0):
        raise ValueError("market_caps must match returns and be positive")
    if membership.shape != returns.shape:
        raise ValueError("industry_membership must match returns")
    dummies = membership[..., None] == industries
    if not np.all(dummies.sum(axis=2) == 1):
        raise ValueError("each stock must have one listed industry")
    if np.any(dummies.sum(axis=1) == 0):
        raise ValueError("every industry must be represented on each date")
    return returns, values, caps, dummies.astype(float)


def fit_factor_model(panel):
    """Fit returns[1:] using the preceding rows of raw characteristics."""
    returns, styles, caps, dummies = _panel_arrays(panel)
    times, stocks = returns.shape
    industries = dummies.shape[2]
    style_count = styles.shape[2]
    factors = 1 + industries + style_count
    cap_weights = caps / caps.sum(axis=1, keepdims=True)
    if style_count:
        dispersion = styles.std(axis=1, ddof=1, keepdims=True)
        if np.any(dispersion <= 0) or not np.isfinite(dispersion).all():
            raise ValueError("raw styles must have positive dispersion")
        center = (cap_weights[..., None] * styles).sum(axis=1, keepdims=True)
        styles = (styles - center) / dispersion
    exposures = np.concatenate(
        (np.ones((times, stocks, 1)), dummies, styles), axis=2
    )
    holdings = np.empty((times - 1, factors, stocks))
    fitted = np.empty((times - 1, factors))
    residuals = np.empty((times - 1, stocks))
    for t in range(times - 1):
        holdings[t] = factor_holdings(exposures[t], caps[t], dummies[t])
        fitted[t] = holdings[t] @ returns[t + 1]
        residuals[t] = returns[t + 1] - exposures[t] @ fitted[t]
    return FactorResult(fitted, residuals, exposures, holdings)


def factor_holdings(exposures, caps, dummies):
    """Constrained WLS portfolios for one cross-section with supplied exposures."""
    factors = exposures.shape[1]
    industries = dummies.shape[1]
    style_count = factors - industries - 1
    shares = (caps / caps.sum()) @ dummies
    constraint = np.zeros((factors, factors - 1))
    constraint[:industries, :industries] = np.eye(industries)
    constraint[industries, 1:industries] = -shares[:-1] / shares[-1]
    constraint[industries + 1:, industries:] = np.eye(style_count)
    weights = np.sqrt(caps)
    weights /= weights.sum()
    root_weights = np.sqrt(weights)
    design = root_weights[:, None] * (exposures @ constraint)
    left, singular, right = np.linalg.svd(design, full_matrices=False)
    cutoff = np.finfo(float).eps * max(design.shape) * singular[0]
    if len(singular) != factors - 1 or np.any(singular <= cutoff):
        raise ValueError("constrained design is rank deficient")
    inverse_design = (right.T / singular) @ left.T
    return (constraint @ inverse_design) * root_weights
