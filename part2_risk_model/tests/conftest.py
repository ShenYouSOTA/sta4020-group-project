import matplotlib
import numpy as np
import pytest

from risk_model.factor_model import RiskPanel

matplotlib.use("Agg")


def _make_panel(observations=256, stocks=20, seed=23):
    """Generate Gaussian factor/specific shocks with GARCH variances."""
    rng = np.random.default_rng(seed)
    industries, styles = 2, 2
    membership = np.broadcast_to(
        np.arange(stocks) % industries, (observations, stocks)
    ).copy()
    caps = np.broadcast_to(np.exp(rng.normal(5, 0.5, stocks)), membership.shape).copy()
    raw_styles = rng.normal(size=(observations, stocks, styles))
    dummies = membership[..., None] == np.arange(industries)
    weights = caps[0] / caps[0].sum()
    normalized = (
        raw_styles - np.sum(raw_styles * weights[None, :, None], axis=1, keepdims=True)
    ) / raw_styles.std(axis=1, ddof=1, keepdims=True)
    exposures = np.concatenate(
        (np.ones((observations, stocks, 1)), dummies, normalized), axis=2
    )
    shares = weights @ dummies[0]
    constraint = np.zeros((5, 4))
    constraint[0, 0] = 1
    constraint[1, 1] = 1
    constraint[2, 1] = -shares[0] / shares[1]
    constraint[3:, 2:] = np.eye(styles)
    baseline = np.r_[
        np.array([0.012, 0.007, 0.005, 0.006]) ** 2,
        np.linspace(0.01, 0.018, stocks) ** 2,
    ]
    variance = baseline.copy()
    returns = np.empty((observations, stocks))
    oracle = np.empty((observations, stocks, stocks))
    for t in range(observations):
        exposure = exposures[max(t - 1, 0)]
        factor_covariance = (constraint * variance[:4]) @ constraint.T
        oracle[t] = exposure @ factor_covariance @ exposure.T + np.diag(variance[4:])
        shocks = rng.normal(size=len(variance)) * np.sqrt(variance)
        returns[t] = exposure @ constraint @ shocks[:4] + shocks[4:]
        variance = 0.05 * baseline + 0.05 * shocks ** 2 + 0.9 * variance
    dates = np.datetime64("2020-01-01") + np.arange(observations)
    panel = RiskPanel(
        dates, np.arange(stocks), returns, raw_styles, np.arange(styles),
        membership, np.arange(industries), caps,
    )
    return panel, oracle


@pytest.fixture
def make_panel():
    """Provide a seeded synthetic panel factory to tests."""
    return _make_panel
