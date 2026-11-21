import numpy as np
import pytest

from risk_model.integration import (
    blend_risk,
    compute_asset_covariance,
    rescale_covariance,
)


@pytest.mark.parametrize(
    "method",
    ["factor_model", "historical_average", "constant_correlation", "shrinkage"],
)
def test_rescaling_at_stock_and_factor_levels(method):
    covariance = np.array([[4, 1, 0.4], [1, 9, -0.3], [0.4, -0.3, 1]])
    volatility = np.array([1, 2, 3.0])
    scale = np.sqrt(np.outer(covariance.diagonal(), covariance.diagonal()))
    correlation = covariance / scale
    if method == "constant_correlation":
        rho = correlation[np.triu_indices(3, 1)].mean()
        correlation = np.full((3, 3), rho)
        np.fill_diagonal(correlation, 1)
    elif method == "shrinkage":
        correlation = (np.eye(3) + correlation) / 2
    result = rescale_covariance(covariance, volatility, method)
    np.testing.assert_allclose(
        result, np.diag(volatility) @ correlation @ np.diag(volatility)
    )
    np.testing.assert_allclose(result.diagonal(), volatility ** 2)
    assert np.linalg.eigvalsh(result).min() > 0
    np.testing.assert_allclose(rescale_covariance([[2]], [3], method), [[9]])


def test_blending_and_covariance_assembly():
    stable = np.array([[1.0, 0.3], [0.3, 2]])
    dynamic = 2 * stable
    np.testing.assert_allclose(blend_risk(stable, dynamic), 1.5 * stable)
    np.testing.assert_array_equal(blend_risk(stable, dynamic, 0), dynamic)
    np.testing.assert_array_equal(blend_risk(stable, dynamic, 1), stable)
    np.testing.assert_allclose(blend_risk([1, 2], [3, 5], [0.2, 0.8]), [2.6, 2.6])
    exposure = np.array([[1, 1], [1, 0], [1, -1]])
    specific = np.array([0.1, 0.2, 0.3])
    expected = exposure @ stable @ exposure.T + np.diag(specific)
    np.testing.assert_allclose(
        compute_asset_covariance(exposure, stable, specific), expected
    )
    np.testing.assert_allclose(
        compute_asset_covariance(exposure, dynamic, specific),
        exposure @ dynamic @ exposure.T + np.diag(specific),
    )
    with pytest.raises(ValueError):
        blend_risk(stable, dynamic, [0.2, 0.8])
    with pytest.raises(ValueError):
        rescale_covariance([[1, 2], [2, 1]], [1, 1])
