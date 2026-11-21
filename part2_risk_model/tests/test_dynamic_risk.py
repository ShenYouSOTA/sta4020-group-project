from types import SimpleNamespace

import numpy as np
import pytest
from scipy import stats

from risk_model import dynamic_risk
from risk_model.dynamic_risk import (
    _negative_loglikelihood,
    _variance_path,
    estimate_dynamic_variance,
)


def test_variance_recursions_and_ewma_forecast():
    innovations = np.array([1.0, -2.0, 0.5, 1.5])
    np.testing.assert_allclose(
        _variance_path(innovations, 0.2, 0.1, 0.5, 2), [2, 1.3, 1.25, 0.85]
    )
    np.testing.assert_allclose(
        _variance_path(innovations, 0.2, 0.1, 0, 2), [2, 0.3, 0.6, 0.225]
    )
    returns = innovations[:, None]
    centered = innovations - innovations.mean()
    variance = innovations.var(ddof=1)
    expected_residuals = []
    for value in centered:
        expected_residuals.append(value / np.sqrt(variance))
        variance = 0.94 * variance + 0.06 * value ** 2
    result = estimate_dynamic_variance(returns, "ewma")
    np.testing.assert_allclose(result.forecast_variance, [variance])
    np.testing.assert_allclose(result.standardized_residuals[:, 0], expected_residuals)
    assert result.degrees_of_freedom is None


@pytest.mark.parametrize("student_t", [False, True])
@pytest.mark.parametrize("garch", [False, True])
def test_full_likelihood_matches_scipy_densities(garch, student_t):
    series = np.array([1.0, -0.2, 0.7, -1.0])
    parameters = [0.1, 0.2, 0.1] + ([0.5] if garch else [])
    if student_t:
        parameters.append(7.0)
    errors = series - 0.1
    variance = [1.0]
    for error in errors[:-1]:
        variance.append(0.2 + 0.1 * error ** 2 + (0.5 if garch else 0) * variance[-1])
    scale = np.sqrt(variance)
    if student_t:
        expected = stats.t.logpdf(errors, 7, scale=scale * np.sqrt(5 / 7))
    else:
        expected = stats.norm.logpdf(errors, scale=scale)
    np.testing.assert_allclose(
        _negative_loglikelihood(parameters, series, garch, student_t), -expected.sum()
    )


@pytest.mark.parametrize("method", ["arch", "garch"])
@pytest.mark.parametrize("distribution", ["gaussian", "student_t"])
def test_fitted_models_and_units(method, distribution):
    series = np.random.default_rng(17).standard_t(8, size=(256, 1)) * 0.01
    result = estimate_dynamic_variance(series, method, distribution=distribution)
    assert result.forecast_variance.shape == (1,)
    assert result.standardized_residuals.shape == series.shape
    assert 0.5 < result.standardized_residuals.var() < 2
    if distribution == "student_t":
        assert result.degrees_of_freedom[0] > 2
    else:
        assert result.degrees_of_freedom is None
    scaled = estimate_dynamic_variance(
        100 * series + 2, method, distribution=distribution
    )
    np.testing.assert_allclose(
        scaled.forecast_variance, result.forecast_variance * 1e4, rtol=2e-3
    )
    np.testing.assert_allclose(
        scaled.standardized_residuals, result.standardized_residuals, atol=2e-3
    )


def test_failed_fit_and_constant_series(monkeypatch):
    with pytest.raises(ValueError, match="positive"):
        estimate_dynamic_variance(np.ones((20, 1)))
    monkeypatch.setattr(
        dynamic_risk, "minimize", lambda *args, **kwargs: SimpleNamespace(
            success=False, fun=np.inf, message="test failure"
        ),
    )
    with pytest.raises(ValueError, match="series 0.*test failure"):
        estimate_dynamic_variance(np.arange(20.0)[:, None])
