from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from sta4020_project.risk import sample_covariances


def test_sample_covariance_freezes_delisted_risk():
    dates = pd.date_range("2023-02-01", periods=5, freq="ME")
    returns = pd.DataFrame({"300330.SZ": [.1, .2, -.3, .4, 0], "active": [.3, -.1, .2, .4, .5]},
                           index=dates)
    first, second = sample_covariances(returns, dates[-2:])
    assert first[0, 0] == second[0, 0] == pytest.approx(returns.iloc[:3, 0].var())
    assert second[0, 1] == second[1, 0] == 0
    assert second[1, 1] == pytest.approx(returns["active"].var())


def test_factor_covariance_ignores_future_rows():
    factor_model = pytest.importorskip("risk_model.factor_model")
    from sta4020_project.styles import factor_covariances

    rng = np.random.default_rng(42)
    dates = pd.date_range("2022-01-01", periods=20, freq="ME")
    returns = rng.normal(0, .05, (20, 15))
    styles = rng.normal(size=(20, 15, 2))
    panel = factor_model.RiskPanel(
        dates.to_numpy(), np.array(["300330.SZ"] + [f"S{i}" for i in range(14)]),
        returns, styles, np.array(["size", "value"]),
        np.full(returns.shape, "Market"), np.array(["Market"]), np.ones(returns.shape),
    )
    for index in (8, 17):
        future_returns, future_styles = returns.copy(), styles.copy()
        future_returns[index + 1:] *= 10
        future_styles[index + 1:] *= -10
        changed = replace(panel, returns=future_returns, style_values=future_styles)
        origin = dates[[index]]
        np.testing.assert_allclose(next(factor_covariances(changed, origin)),
                                   next(factor_covariances(panel, origin)))
