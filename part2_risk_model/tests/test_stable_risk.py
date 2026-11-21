import numpy as np
import pytest
from scipy.special import gammaln
from sklearn.covariance import ledoit_wolf

from risk_model.stable_risk import (
    estimate_factor_covariance,
    estimate_specific_variance,
    shrink_covariance,
    shrink_specific_variance,
)


def test_sample_estimates_and_covariance_shrinkage():
    returns = np.random.default_rng(4).normal(size=(80, 3))
    sample = np.cov(returns, rowvar=False)
    np.testing.assert_allclose(
        estimate_factor_covariance(returns, eigenfactor_adjustment=False), sample
    )
    np.testing.assert_allclose(estimate_specific_variance(returns), np.diag(sample))
    identity = np.eye(3) * np.trace(sample) / 3
    target = np.diag([1.0, 2.0, 3.0])
    np.testing.assert_allclose(
        shrink_covariance(sample, target_covariance=target), (sample + target) / 2
    )
    np.testing.assert_allclose(
        shrink_covariance(sample, "scaled_identity", w=0.3),
        0.7 * sample + 0.3 * identity,
    )
    correlation = np.corrcoef(returns, rowvar=False)
    rho = correlation[np.triu_indices(3, 1)].mean()
    constant = rho * np.sqrt(np.outer(sample.diagonal(), sample.diagonal()))
    np.fill_diagonal(constant, sample.diagonal())
    np.testing.assert_allclose(
        shrink_covariance(sample, "constant_correlation", w=1), constant
    )
    np.testing.assert_allclose(
        shrink_covariance(sample, "scaled_identity", w=0), sample
    )
    expected, _ = ledoit_wolf(returns)
    np.testing.assert_allclose(
        shrink_covariance(sample, "ledoit_wolf", returns=returns), expected * 80 / 79
    )
    with pytest.raises(ValueError):
        shrink_covariance(sample)
    with pytest.raises(ValueError):
        shrink_covariance(sample, "ledoit_wolf", returns=returns * 2)


def test_eigenfactor_adjustment_and_singular_covariance():
    series = np.random.default_rng(5).normal(size=(40, 1))
    sample = series.var(ddof=1)
    adjusted = estimate_factor_covariance(series)
    freedom = len(series) - 1
    expected_ratio = np.exp(
        0.5 * np.log(freedom / 2)
        + gammaln((freedom - 1) / 2) - gammaln(freedom / 2)
    ) ** 2
    np.testing.assert_allclose(adjusted[0, 0] / sample, expected_ratio, rtol=0.04)
    np.testing.assert_array_equal(adjusted, estimate_factor_covariance(series))
    singular = np.column_stack((series, 2 * series))
    matrix = estimate_factor_covariance(singular, simulations=100, a=1.5)
    np.testing.assert_allclose(matrix @ [2, -1], 0, atol=1e-12)
    assert np.linalg.eigvalsh(matrix)[-1] > 0


def test_bayesian_shrinkage_of_volatility():
    caps = np.arange(1, 21, dtype=float)
    volatility = np.tile([1.0, 3.0], 10)
    expected = []
    for pair in range(10):
        group = slice(2 * pair, 2 * pair + 2)
        prior = np.average(volatility[group], weights=caps[group])
        dispersion = np.sqrt(np.mean((volatility[group] - prior) ** 2))
        weight = np.abs(volatility[group] - prior)
        weight /= dispersion + weight
        expected.extend((weight * prior + (1 - weight) * volatility[group]) ** 2)
    np.testing.assert_allclose(
        shrink_specific_variance(volatility ** 2, caps), expected
    )
    np.testing.assert_allclose(
        shrink_specific_variance(volatility ** 2, caps, q=0), volatility ** 2
    )
    np.testing.assert_array_equal(
        shrink_specific_variance(np.ones(20), caps), np.ones(20)
    )
