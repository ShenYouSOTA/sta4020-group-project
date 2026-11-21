"""Pure portfolio identities, risk bias and fitted-residual diagnostic plots."""

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from ._validation import _array, _covariance, _history, _ids, _tolerance


def diagnose_pure_factor_portfolios(panel, factor_result):
    """Return maximum replication, exposure and neutrality errors."""
    returns = _history(panel.returns)
    times, stocks = returns.shape
    caps = _array(panel.market_caps, 2, "market_caps")
    membership = np.asarray(panel.industry_membership)
    ids = _ids(panel.industry_ids, "industry_ids")
    holdings = _array(factor_result.pure_factor_portfolios, 3, "holdings")
    exposures = _array(factor_result.exposures, 3, "exposures")
    fitted = _array(factor_result.factor_returns, 2, "factor_returns")
    factors, industries = fitted.shape[1], len(ids)
    if caps.shape != returns.shape or membership.shape != returns.shape:
        raise ValueError("caps and membership must match stock returns")
    if fitted.shape != (times - 1, factors):
        raise ValueError("factor returns must have T-1 rows")
    if holdings.shape != (times - 1, factors, stocks):
        raise ValueError("pure factor portfolios must have shape (T-1,K,N)")
    if exposures.shape != (times, stocks, factors) or factors < industries + 1:
        raise ValueError("exposures must match panel and factor ordering")
    dummies = membership[..., None] == ids
    if np.any(caps <= 0) or not np.all(dummies.sum(axis=2) == 1):
        raise ValueError("positive caps and valid industry membership required")
    if np.any(dummies.sum(axis=1) == 0):
        raise ValueError("every industry must be represented")
    errors = np.zeros(3)
    expected_sum = np.zeros(factors)
    expected_sum[0] = 1
    for t, portfolio in enumerate(holdings):
        shares = caps[t] @ dummies[t] / caps[t].sum()
        expected = np.eye(factors)
        expected[0, 1:industries + 1] = shares
        expected[1:industries + 1, 1:industries + 1] -= shares
        discrepancies = (
            portfolio @ returns[t + 1] - fitted[t],
            portfolio @ exposures[t] - expected,
            portfolio.sum(axis=1) - expected_sum,
        )
        errors = np.maximum(errors, [np.max(np.abs(x)) for x in discrepancies])
    return tuple(float(error) for error in errors)


def compute_bias_statistic(returns, covariance, *, eigenfactor=False):
    """Compute sample standard deviations of returns divided by forecast risk."""
    if not isinstance(eigenfactor, (bool, np.bool_)):
        raise ValueError("eigenfactor must be Boolean")
    series = np.asarray(returns, dtype=float)
    if series.ndim == 1:
        series = _array(series, 1, "returns")
        variances = _array(covariance, 1, "covariance")
        if eigenfactor or series.shape != variances.shape or len(series) < 2:
            raise ValueError("one series needs matching variance history")
        if np.any(variances <= 0):
            raise ValueError("scored variances must be positive")
        return float(np.std(series / np.sqrt(variances), ddof=1))
    series = _history(series)
    matrices = _array(covariance, 3, "covariance")
    times, size = series.shape
    if matrices.shape != (times, size, size):
        raise ValueError("covariance history must match returns")
    standardized = []
    rank = None
    for observations, matrix in zip(series, matrices):
        matrix = _covariance(matrix)
        if eigenfactor:
            values, vectors = np.linalg.eigh(matrix)
            positive = values > _tolerance(matrix)
            values, vectors = values[positive], vectors[:, positive]
            if not len(values) or (rank is not None and len(values) != rank):
                raise ValueError("eigenfactor histories need constant positive rank")
            rank = len(values)
            largest = np.argmax(np.abs(vectors), axis=0)
            signs = np.sign(vectors[largest, np.arange(rank)])
            observations = (vectors * signs).T @ observations
        else:
            values = matrix.diagonal()
        if np.any(values <= 0):
            raise ValueError("scored variances must be positive")
        standardized.append(observations / np.sqrt(values))
    return np.std(standardized, axis=0, ddof=1)


def _acf(series):
    centered = series - series.mean()
    denominator = centered @ centered
    if denominator == 0:
        raise ValueError("ACF is undefined for a constant series")
    return np.correlate(centered, centered, mode="full")[len(series) - 1:] / denominator


def diagnose_standardized_residuals(standardized_residuals, degrees_of_freedom):
    """Return one three-panel diagnostic figure for each fitted series."""
    residuals = _history(standardized_residuals, "standardized_residuals")
    degrees = None
    if degrees_of_freedom is not None:
        degrees = _array(degrees_of_freedom, 1, "degrees_of_freedom")
        if degrees.shape != (residuals.shape[1],) or np.any(degrees <= 2):
            raise ValueError("each series needs fitted degrees of freedom above two")
    figures = []
    for column, series in enumerate(residuals.T):
        linear, squared = _acf(series), _acf(series ** 2)
        if degrees is None:
            quantiles, ordered = stats.probplot(series, dist="norm", fit=False)
        else:
            nu = degrees[column]
            quantiles, ordered = stats.probplot(
                series, dist="t", sparams=(nu,), fit=False
            )
            quantiles *= np.sqrt((nu - 2) / nu)
        figure, axes = plt.subplots(1, 3, figsize=(12, 3.4), layout="constrained")
        for axis, values, title in zip(
            axes[:2], (linear, squared), ("Residual ACF", "Squared residual ACF")
        ):
            axis.vlines(np.arange(len(values)), 0, values, linewidth=0.8)
            axis.axhline(0, color="black", linewidth=0.6)
            axis.set(title=title, xlabel="Lag", ylabel="Autocorrelation")
        axes[2].scatter(quantiles, ordered, s=9)
        axes[2].plot(quantiles, quantiles, color="black", linewidth=0.8)
        axes[2].set(title="Q-Q plot", xlabel="Theoretical quantile", ylabel="Residual")
        figure.suptitle(
            f"Series {column}: mean={series.mean():.3f}, "
            f"variance={series.var(ddof=1):.3f}"
        )
        figures.append(figure)
    return figures
