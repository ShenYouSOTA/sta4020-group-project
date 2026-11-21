"""Small-sample inference for strategy comparison.

The brief grades interpretation over point estimates, so Part 4 has to say
whether an OOS gap against 1/N is signal or noise.  These helpers are
deliberately small: Memmel's Sharpe difference test, a circular block
bootstrap, and Newey-West t-statistics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 12


def _aligned(a, b) -> tuple[np.ndarray, np.ndarray]:
    left = pd.Series(a, dtype=float)
    right = pd.Series(b, dtype=float)
    frame = pd.concat([left.rename("a"), right.rename("b")], axis=1, join="inner").dropna()
    if len(frame) < 3:
        raise ValueError("need at least three overlapping observations")
    return frame["a"].to_numpy(), frame["b"].to_numpy()


def _erf(value: float) -> float:
    """Abramowitz-Stegun 7.1.26; avoids a SciPy dependency for a p-value."""
    sign = -1.0 if value < 0 else 1.0
    x = abs(value)
    t = 1.0 / (1.0 + 0.3275911 * x)
    poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
    return sign * (1.0 - poly * np.exp(-x * x))


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + _erf(value / np.sqrt(2.0)))


def _two_sided_p(statistic: float) -> float:
    return float(2.0 * (1.0 - _normal_cdf(abs(statistic)))) if np.isfinite(statistic) else float("nan")


def sharpe_difference_test(returns_a, returns_b) -> dict:
    """H0: SR(a) == SR(b), Memmel (2003) corrected Jobson-Korkie statistic."""
    a, b = _aligned(returns_a, returns_b)
    n = len(a)
    sr_a = a.mean() / a.std(ddof=1)
    sr_b = b.mean() / b.std(ddof=1)
    rho = float(np.corrcoef(a, b)[0, 1])
    variance = (2.0 - 2.0 * rho + 0.5 * (sr_a ** 2 + sr_b ** 2) - sr_a * sr_b * rho ** 2) / n
    statistic = float((sr_a - sr_b) / np.sqrt(variance)) if variance > 0 else float("nan")
    scale = np.sqrt(PERIODS_PER_YEAR)
    return {
        "sharpe_a": float(sr_a * scale),
        "sharpe_b": float(sr_b * scale),
        "difference": float((sr_a - sr_b) * scale),
        "z_statistic": statistic,
        "p_value": _two_sided_p(statistic),
        "n": n,
    }


def circular_block_bootstrap_mean(returns, n_boot: int = 4000, block: int = 6, seed: int = 0) -> dict:
    """Percentile interval for the mean return and for the Sharpe ratio."""
    series = pd.Series(returns, dtype=float).dropna().to_numpy()
    n = len(series)
    if n < block + 1:
        raise ValueError("series shorter than one bootstrap block")
    generator = np.random.default_rng(seed)
    means = np.empty(n_boot)
    sharpes = np.empty(n_boot)
    blocks_needed = int(np.ceil(n / block))
    offsets = np.arange(block)
    for i in range(n_boot):
        starts = generator.integers(0, n, size=blocks_needed)
        index = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        sample = series[index]
        means[i] = sample.mean()
        deviation = sample.std(ddof=1)
        sharpes[i] = np.nan if deviation == 0 else sample.mean() / deviation
    deviation = series.std(ddof=1)
    valid = sharpes[~np.isnan(sharpes)]
    return {
        "mean": float(series.mean()),
        "mean_ci": [float(x) for x in np.percentile(means, [2.5, 97.5])],
        "sharpe": float(series.mean() / deviation) * np.sqrt(PERIODS_PER_YEAR) if deviation else float("nan"),
        "sharpe_ci": [float(x) * np.sqrt(PERIODS_PER_YEAR) for x in np.percentile(valid, [2.5, 97.5])],
        "n_boot": n_boot,
        "block": block,
    }


def newey_west_tstat(values, lags: int | None = None) -> dict:
    """t-statistic of the mean with a Newey-West standard error."""
    series = pd.Series(values, dtype=float).dropna().to_numpy()
    n = len(series)
    if n < 3:
        raise ValueError("need at least three observations")
    lags = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0))) if lags is None else int(lags)
    demeaned = series - series.mean()
    long_run = float((demeaned ** 2).mean())
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1.0 - lag / (lags + 1.0)
        long_run += 2.0 * weight * float((demeaned[lag:] * demeaned[:-lag]).mean())
    long_run = max(long_run, 0.0)
    standard_error = float(np.sqrt(long_run / n))
    statistic = float(series.mean() / standard_error) if standard_error > 0 else float("nan")
    return {
        "mean": float(series.mean()),
        "se": standard_error,
        "t_statistic": statistic,
        "p_value": _two_sided_p(statistic),
        "lags": lags,
        "n": n,
    }


def alpha_vs_benchmark(returns, benchmark, periods_per_year: int = PERIODS_PER_YEAR) -> dict:
    """Jensen's alpha on the benchmark, with a Newey-West t-statistic."""
    a, b = _aligned(returns, benchmark)
    design = np.column_stack([np.ones_like(b), b])
    coefficients, *_ = np.linalg.lstsq(design, a, rcond=None)
    residuals = a - design @ coefficients
    n, k = design.shape
    if n <= k:
        raise ValueError("not enough observations for a regression")
    lags = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    bread = np.linalg.inv(design.T @ design)
    meat = np.zeros((k, k))
    for lag in range(0, min(lags, n - 1) + 1):
        weight = 1.0 - lag / (lags + 1.0)
        if lag == 0:
            weighted = design * residuals[:, None]
            moment = weighted.T @ weighted
        else:
            left = design[lag:] * residuals[lag:, None]
            right = design[:-lag] * residuals[:-lag, None]
            moment = left.T @ right
            moment = moment + moment.T
        meat += weight * moment
    covariance = bread @ meat @ bread
    standard_error = float(np.sqrt(np.diag(covariance)[0]))
    alpha = float(coefficients[0])
    return {
        "alpha_period": alpha,
        "alpha_annualized": float((1.0 + alpha) ** periods_per_year - 1.0),
        "t_statistic": float(alpha / standard_error) if standard_error > 0 else float("nan"),
        "beta": float(coefficients[1]),
        "r_squared": float(1.0 - residuals.var(ddof=1) / a.var(ddof=1)),
        "n": int(n),
    }
