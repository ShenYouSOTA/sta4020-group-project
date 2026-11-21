import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy import stats

from risk_model.diagnostics import (
    compute_bias_statistic,
    diagnose_standardized_residuals,
)


def test_ordinary_and_eigenfactor_bias():
    returns = np.array([[1, 2], [-1, 0], [2, 1], [0, -2.0]])
    variance = np.array([1, 2, 3, 4.0])
    expected = np.std(returns[:, 0] / np.sqrt(variance), ddof=1)
    assert compute_bias_statistic(returns[:, 0], variance) == expected
    covariance = np.array([[4, 1], [1, 2.0]])
    history = np.broadcast_to(covariance, (4, 2, 2))
    np.testing.assert_allclose(
        compute_bias_statistic(returns, history),
        np.std(returns / np.sqrt(covariance.diagonal()), axis=0, ddof=1),
    )
    values, vectors = np.linalg.eigh(covariance)
    expected = np.std((returns @ vectors) / np.sqrt(values), axis=0, ddof=1)
    np.testing.assert_allclose(
        compute_bias_statistic(returns, history, eigenfactor=True), expected
    )
    singular = np.broadcast_to(np.diag([0, 2.0]), (4, 2, 2))
    np.testing.assert_allclose(
        compute_bias_statistic(returns, singular, eigenfactor=True),
        [returns[:, 1].std(ddof=1) / np.sqrt(2)],
    )
    with pytest.raises(ValueError):
        compute_bias_statistic(returns[:, 0], np.zeros(4))


@pytest.mark.parametrize("degrees", [None, np.array([7.0])])
def test_residual_figures_and_quantiles(degrees):
    residuals = np.random.default_rng(2).standard_t(7, size=(50, 1)) * np.sqrt(5 / 7)
    figures = diagnose_standardized_residuals(residuals, degrees)
    assert len(figures) == 1
    figure = figures[0]
    assert len(figure.axes) == 3
    assert "mean=" in figure._suptitle.get_text()
    assert "variance=" in figure._suptitle.get_text()
    if degrees is None:
        expected, ordered = stats.probplot(residuals[:, 0], dist="norm", fit=False)
    else:
        expected, ordered = stats.probplot(
            residuals[:, 0], dist="t", sparams=(7,), fit=False
        )
        expected *= np.sqrt(5 / 7)
    points = figure.axes[2].collections[0].get_offsets()
    np.testing.assert_allclose(points[:, 0], expected)
    np.testing.assert_allclose(points[:, 1], ordered)
    plt.close(figure)
