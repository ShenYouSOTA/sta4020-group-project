from dataclasses import replace

import numpy as np
import pytest

from risk_model.diagnostics import diagnose_pure_factor_portfolios
from risk_model.factor_model import fit_factor_model


def test_factor_construction_and_pure_portfolios(make_panel):
    panel, _ = make_panel(observations=12)
    original = panel.style_values.copy()
    result = fit_factor_model(panel)
    assert result.factor_returns.shape == (11, 5)
    assert result.exposures.shape == (12, 20, 5)
    reconstructed = np.einsum(
        "tnk,tk->tn", result.exposures[:-1], result.factor_returns
    ) + result.residuals
    np.testing.assert_allclose(reconstructed, panel.returns[1:], atol=1e-15)
    cap_weights = panel.market_caps / panel.market_caps.sum(axis=1, keepdims=True)
    shares = cap_weights @ (np.arange(20)[:, None] % 2 == np.arange(2))
    np.testing.assert_allclose(
        np.sum(shares[:-1] * result.factor_returns[:, 1:3], axis=1), 0, atol=1e-15
    )
    np.testing.assert_allclose(
        np.sum(cap_weights[..., None] * result.exposures[:, :, 3:], axis=1),
        0, atol=1e-14,
    )
    np.testing.assert_allclose(result.exposures[:, :, 3:].std(axis=1, ddof=1), 1)
    assert max(diagnose_pure_factor_portfolios(panel, result)) < 1e-12
    np.testing.assert_array_equal(panel.style_values, original)


def test_diagnostic_uses_independent_industry_constraint(make_panel):
    panel, _ = make_panel(observations=10)
    result = fit_factor_model(panel)
    transform = np.eye(5)
    transform[:, 1] += 0.1 * np.array([1, -1, -1, 0, 0])
    wrong = replace(
        result,
        pure_factor_portfolios=transform @ result.pure_factor_portfolios,
        factor_returns=result.factor_returns @ transform.T,
    )
    replication, exposure, neutrality = diagnose_pure_factor_portfolios(panel, wrong)
    assert replication < 1e-12
    assert neutrality < 1e-12
    assert exposure > 0.01


def test_lag_and_unused_diagnostic_fields(make_panel):
    panel, _ = make_panel(observations=10)
    result = fit_factor_model(panel)
    styles = panel.style_values.copy()
    styles[-1] *= np.linspace(1, 3, 20)[:, None]
    altered = fit_factor_model(replace(panel, style_values=styles))
    np.testing.assert_allclose(altered.factor_returns, result.factor_returns)
    assert not np.allclose(altered.exposures[-1], result.exposures[-1])
    ignored = replace(
        panel, dates=None, asset_ids=None, style_values=None, style_ids=None
    )
    assert max(diagnose_pure_factor_portfolios(ignored, result)) < 1e-12


def test_invalid_styles_and_zero_style_case(make_panel):
    panel, _ = make_panel(observations=10)
    with pytest.raises(ValueError, match="dispersion"):
        fit_factor_model(replace(panel, style_values=np.ones_like(panel.style_values)))
    empty = replace(panel, style_values=panel.style_values[:, :, :0], style_ids=[])
    assert fit_factor_model(empty).factor_returns.shape == (9, 3)
