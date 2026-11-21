import math

import numpy as np
import pandas as pd
import pytest

from sta4020_project import metrics


def series(values, start="2024-01-31"):
    index = pd.date_range(start, periods=len(values), freq="ME")
    return pd.Series(values, index=index)


def test_annualized_return_compounds_geometrically():
    returns = series([0.01] * 12)
    assert metrics.annualized_return(returns) == pytest.approx(1.01 ** 12 - 1)


def test_annualized_volatility_scales_by_square_root_of_periods():
    returns = series([0.01, -0.01] * 6)
    expected = returns.std(ddof=1) * math.sqrt(12)
    assert metrics.annualized_volatility(returns) == pytest.approx(expected)


def test_max_drawdown_is_the_worst_peak_to_trough_move():
    returns = series([0.10, -0.20, -0.10, 0.30])
    curve = metrics.wealth_index(returns)
    worst = (curve / curve.cummax() - 1.0).min()
    assert metrics.max_drawdown(returns) == pytest.approx(worst)


def test_sharpe_is_zero_when_returns_have_no_dispersion():
    returns = series([0.01] * 12)
    assert not np.isfinite(metrics.sharpe_ratio(returns))


def test_turnover_counts_half_the_gross_trading():
    previous = pd.Series({"a": 0.5, "b": 0.5})
    current = pd.Series({"a": 0.8, "b": 0.2})
    assert metrics.turnover(current, previous) == pytest.approx(0.3)


def test_concentration_reports_effective_number_of_holdings():
    weights = pd.Series({"a": 0.5, "b": 0.5})
    values = metrics.concentration(weights)
    assert values["effective_n"] == pytest.approx(2.0)
    assert values["hhi"] == pytest.approx(0.5)


def test_summary_contains_the_four_required_metrics():
    summary = metrics.summary(series([0.01, -0.02, 0.03, 0.0]))
    for key in ("annualized_return", "annualized_volatility", "sharpe_ratio", "max_drawdown"):
        assert key in summary
