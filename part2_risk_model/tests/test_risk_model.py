from dataclasses import replace

import numpy as np
import pytest

from risk_model import forecast_risk
from risk_model.dynamic_risk import estimate_dynamic_variance
from risk_model.factor_model import fit_factor_model
from risk_model.integration import (
    blend_risk,
    compute_asset_covariance,
    rescale_covariance,
)
from risk_model.stable_risk import (
    estimate_factor_covariance,
    estimate_specific_variance,
    shrink_covariance,
    shrink_specific_variance,
)


@pytest.mark.parametrize("options", [
    {},
    {"dynamic_variance": {"method": "ewma"},
     "rescaling": {"method": "constant_correlation"}},
    {"rescaling_level": "stock", "dynamic_variance": {"method": "ewma"},
     "covariance_shrinkage": {"method": "ledoit_wolf"}},
    {"integration_method": "blend", "dynamic_variance": {"method": "ewma"},
     "specific_blending": {},
     "factor_blending": {}, "specific_shrinkage": {}},
])
def test_pipeline_and_future_data_isolation(make_panel, options):
    panel, oracle = make_panel(observations=160, stocks=12, seed=23)
    origin = panel.dates[-2]
    forecast = forecast_risk(panel, origin, **options)
    assert forecast.shape == (12, 12)
    assert np.isfinite(forecast).all()
    np.testing.assert_allclose(forecast, forecast.T)
    assert np.linalg.eigvalsh(forecast).min() >= -1e-12
    relative_error = np.linalg.norm(forecast - oracle[-1]) / np.linalg.norm(oracle[-1])
    assert relative_error < 2
    altered_fields = {}
    for field in ("returns", "style_values", "market_caps", "industry_membership"):
        values = getattr(panel, field).copy()
        values[-1] = -999
        altered_fields[field] = values
    altered = replace(panel, **altered_fields)
    np.testing.assert_array_equal(forecast_risk(altered, origin, **options), forecast)


def test_defaults_match_committed_composition(make_panel):
    panel, _ = make_panel(observations=160, stocks=12)
    factors = fit_factor_model(panel)
    stable = estimate_factor_covariance(factors.factor_returns)
    dynamic = estimate_dynamic_variance(factors.factor_returns)
    specific = estimate_dynamic_variance(factors.residuals)
    expected = compute_asset_covariance(
        factors.exposures[-1],
        rescale_covariance(stable, np.sqrt(dynamic.forecast_variance)),
        specific.forecast_variance,
    )
    actual = forecast_risk(panel, panel.dates[-1])
    empty = forecast_risk(
        panel, panel.dates[-1], factor_covariance={}, dynamic_variance={}, rescaling={}
    )
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(empty, expected)


@pytest.mark.parametrize("level", ["factor", "stock"])
@pytest.mark.parametrize("method", [
    "factor_model", "historical_average", "constant_correlation", "shrinkage",
])
def test_rescaling_and_partial_overrides(make_panel, level, method):
    panel, _ = make_panel(observations=48, stocks=12)
    factors = fit_factor_model(panel)
    history = factors.factor_returns if level == "factor" else panel.returns
    source = np.cov(history, rowvar=False)
    factor_options = None
    if method == "factor_model":
        factor_options = {"eigenfactor_adjustment": False}
        source = estimate_factor_covariance(factors.factor_returns, **factor_options)
        if level == "stock":
            source = compute_asset_covariance(
                factors.exposures[-1], source,
                estimate_specific_variance(factors.residuals),
            )
    dynamic_options = {"method": "ewma", "lambda_": 0.81}
    rescaling = {"method": method}
    if method == "shrinkage":
        rescaling["w"] = 0.3
    dynamic = estimate_dynamic_variance(history, **dynamic_options)
    expected = rescale_covariance(
        source, np.sqrt(dynamic.forecast_variance), **rescaling
    )
    if level == "factor":
        specific = estimate_dynamic_variance(factors.residuals, **dynamic_options)
        expected = compute_asset_covariance(
            factors.exposures[-1], expected, specific.forecast_variance
        )
    actual = forecast_risk(
        panel, panel.dates[-1], rescaling_level=level, factor_covariance=factor_options,
        dynamic_variance=dynamic_options, rescaling=rescaling,
    )
    np.testing.assert_allclose(actual, expected)


@pytest.mark.parametrize("method", [
    "factor_model", "scaled_identity", "constant_correlation", "ledoit_wolf",
])
@pytest.mark.parametrize("correlation", ["factor_model", "historical_average",
                                         "constant_correlation", "shrinkage"])
def test_stock_shrinkage(make_panel, method, correlation):
    panel, _ = make_panel(observations=48)
    options = {} if method == "factor_model" else {"method": method, "w": 0.3}
    extra, target = {}, None
    if method == "factor_model":
        extra = {
            "factor_covariance": {"simulations": 40},
            "specific_shrinkage": {"q": 0.7},
        }
        factors = fit_factor_model(panel)
        target = compute_asset_covariance(
            factors.exposures[-1],
            estimate_factor_covariance(factors.factor_returns, simulations=40),
            shrink_specific_variance(
                estimate_specific_variance(factors.residuals),
                panel.market_caps[-1], q=0.7,
            ),
        )
    shrunk = shrink_covariance(
        np.cov(panel.returns, rowvar=False), target_covariance=target,
        returns=panel.returns, **options,
    )
    dynamic = estimate_dynamic_variance(panel.returns, method="ewma")
    expected = rescale_covariance(
        shrunk, np.sqrt(dynamic.forecast_variance), method=correlation
    )
    actual = forecast_risk(
        panel, panel.dates[-1], rescaling_level="stock",
        dynamic_variance={"method": "ewma"}, covariance_shrinkage=options,
        rescaling={"method": correlation}, **extra,
    )
    np.testing.assert_allclose(actual, expected)


@pytest.mark.parametrize("weight", [0, 0.35, 1])
def test_blending_stable_baselines(make_panel, weight):
    panel, _ = make_panel(observations=48)
    factors = fit_factor_model(panel)
    stable = estimate_factor_covariance(factors.factor_returns, simulations=40)
    baseline = shrink_specific_variance(
        estimate_specific_variance(factors.residuals), panel.market_caps[-1]
    )
    dynamic = estimate_dynamic_variance(factors.factor_returns, method="ewma")
    covariance = rescale_covariance(
        stable, np.sqrt(dynamic.forecast_variance)
    )
    specific = estimate_dynamic_variance(factors.residuals, method="ewma")
    expected = compute_asset_covariance(
        factors.exposures[-1], blend_risk(stable, covariance, stable_weight=weight),
        blend_risk(baseline, specific.forecast_variance),
    )
    actual = forecast_risk(
        panel, panel.dates[-1], integration_method="blend", rescaling_level="stock",
        factor_covariance={"simulations": 40},
        dynamic_variance={"method": "ewma"}, rescaling={"method": "historical_average"},
        factor_blending={"stable_weight": weight},
        specific_blending={}, specific_shrinkage={},
    )
    np.testing.assert_allclose(actual, expected)


@pytest.mark.parametrize("options, message", [
    ({"rescaling_level": "invalid"}, "rescaling_level"),
    ({"integration_method": "invalid"}, "integration_method"),
])
def test_incompatible_options(make_panel, options, message):
    panel, _ = make_panel(observations=24)
    with pytest.raises(ValueError, match=message):
        forecast_risk(panel, panel.dates[-1], **options)


@pytest.mark.parametrize("selected, unused", [
    ({}, {"specific_shrinkage": {"q": 0.7}, "covariance_shrinkage": {},
          "factor_blending": {"stable_weight": 1}, "specific_blending": {"stable_weight": 1}}),
    ({"rescaling": {"method": "historical_average"}},
     {"factor_covariance": {"a": 2}, "specific_shrinkage": {"q": 0.7}}),
    ({"rescaling_level": "stock", "covariance_shrinkage": {"method": "ledoit_wolf"}},
     {"factor_covariance": {"a": 2}, "specific_shrinkage": {"q": 0.7}}),
])
def test_unused_stable_settings_are_ignored(make_panel, selected, unused):
    panel, _ = make_panel(observations=48, stocks=12)
    options = {"dynamic_variance": {"method": "ewma"}, **selected}
    expected = forecast_risk(panel, panel.dates[-1], **options)
    actual = forecast_risk(panel, panel.dates[-1], **options, **unused)
    np.testing.assert_array_equal(actual, expected)
