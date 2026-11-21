"""One-step EWMA, ARCH(1) and GARCH(1,1) variance estimation."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

from ._validation import _history, _number


@dataclass
class DynamicResult:
    forecast_variance: np.ndarray
    standardized_residuals: np.ndarray
    degrees_of_freedom: np.ndarray | None


def _variance_path(innovations, omega, alpha, beta, initial_variance):
    variance = np.empty(len(innovations))
    variance[0] = initial_variance
    for t in range(1, len(innovations)):
        variance[t] = (
            omega + alpha * innovations[t - 1] ** 2 + beta * variance[t - 1]
        )
    return variance


def _negative_loglikelihood(parameters, series, garch, student_t):
    mean, omega, alpha = parameters[:3]
    beta = parameters[3] if garch else 0.0
    innovations = series - mean
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        variance = _variance_path(innovations, omega, alpha, beta, 1.0)
        if student_t:
            nu = parameters[-1]
            log_density = (
                gammaln((nu + 1) / 2) - gammaln(nu / 2)
                - 0.5 * np.log(np.pi * (nu - 2) * variance)
                - (nu + 1) / 2
                * np.log1p(innovations ** 2 / ((nu - 2) * variance))
            )
        else:
            log_density = -0.5 * (
                np.log(2 * np.pi * variance) + innovations ** 2 / variance
            )
    value = -log_density.sum()
    return float(value) if np.isfinite(value) else np.inf


def _fit_series(series, garch, student_t):
    scale = series.std(ddof=1)
    normalized = (series - series.mean()) / scale
    beta_start = 0.9 if garch else 0.0
    start = [0.0, 1 - 0.05 - beta_start, 0.05]
    bounds = [(None, None), (1e-10, None), (0, 1)]
    if garch:
        start.append(beta_start)
        bounds.append((0, 1))
    if student_t:
        start.append(8.0)
        bounds.append((2 + 1e-6, None))
    if len(series) <= len(start):
        raise ValueError("history must exceed the number of fitted parameters")

    def stationarity(parameters):
        beta = parameters[3] if garch else 0.0
        return 1 - 1e-8 - parameters[2] - beta

    fit = minimize(
        _negative_loglikelihood, start, args=(normalized, garch, student_t),
        method="SLSQP", bounds=bounds,
        constraints=[{"type": "ineq", "fun": stationarity}],
        options={"maxiter": 500, "ftol": 1e-9},
    )
    if not fit.success or not np.isfinite(fit.fun) or stationarity(fit.x) < -1e-9:
        raise ValueError(f"volatility optimization failed: {fit.message}")
    mean, omega, alpha = fit.x[:3]
    beta = fit.x[3] if garch else 0.0
    innovations = normalized - mean
    variance = _variance_path(innovations, omega, alpha, beta, 1.0)
    forecast = omega + alpha * innovations[-1] ** 2 + beta * variance[-1]
    nu = fit.x[-1] if student_t else None
    return forecast * scale ** 2, innovations / np.sqrt(variance), nu


def estimate_dynamic_variance(
    returns, method="garch", *, lambda_=0.94, distribution="student_t"
):
    """Fit each column independently and return only the specified fields."""
    history = _history(returns)
    if method not in ("ewma", "arch", "garch"):
        raise ValueError(f"unknown dynamic method: {method}")
    if method == "ewma":
        decay = _number(lambda_, "lambda_")
        if not 0 < decay < 1:
            raise ValueError("lambda_ must lie strictly between zero and one")
    elif distribution not in ("gaussian", "student_t"):
        raise ValueError(f"unknown innovation distribution: {distribution}")
    student_t = method != "ewma" and distribution == "student_t"
    forecast = np.empty(history.shape[1])
    residuals = np.empty_like(history)
    degrees = np.empty(history.shape[1]) if student_t else None
    for column, series in enumerate(history.T):
        initial = series.var(ddof=1)
        if not np.isfinite(initial) or initial <= 0:
            raise ValueError(f"series {column}: initial variance must be positive")
        try:
            if method == "ewma":
                innovations = series - series.mean()
                variance = _variance_path(innovations, 0, 1 - decay, decay, initial)
                forecast[column] = (
                    decay * variance[-1] + (1 - decay) * innovations[-1] ** 2
                )
                residuals[:, column] = innovations / np.sqrt(variance)
            else:
                value, standardized, nu = _fit_series(
                    series, method == "garch", student_t
                )
                forecast[column], residuals[:, column] = value, standardized
                if student_t:
                    degrees[column] = nu
        except ValueError as error:
            raise ValueError(f"series {column}: {error}") from error
    if not np.isfinite(forecast).all() or np.any(forecast <= 0):
        raise ValueError("variance forecasts must be finite and positive")
    if not np.isfinite(residuals).all():
        raise ValueError("standardized residuals must be finite")
    return DynamicResult(forecast, residuals, degrees)
