import numpy as np
import pandas as pd
import pytest

from sta4020_project import backtest, contracts
from sta4020_project.part4.backtest import ExecutionMode, execute_rebalance


def panel(values, dates, assets):
    return pd.DataFrame(values, index=pd.to_datetime(dates), columns=assets)


def test_backtest_without_costs_reproduces_the_weighted_return():
    assets = ["a", "b"]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    realised = panel([[0.10, 0.00], [0.00, 0.10]], ["2024-02-29", "2024-03-29"], assets)
    weights = panel([[0.5, 0.5], [0.0, 1.0]], origins, assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    result = backtest.run_backtest(weights, realised, mapping, name="demo", cost_bps=0.0)
    assert result.returns.loc[pd.Timestamp("2024-02-29")] == pytest.approx(0.05)
    assert result.returns.loc[pd.Timestamp("2024-03-29")] == pytest.approx(0.10)


def test_transaction_costs_are_charged_on_the_traded_notional():
    assets = ["a", "b"]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    realised = panel([[0.0, 0.0], [0.0, 0.0]], ["2024-02-29", "2024-03-29"], assets)
    weights = panel([[0.5, 0.5], [1.0, 0.0]], origins, assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    result = backtest.run_backtest(weights, realised, mapping, cost_bps=100.0)
    first = result.returns.iloc[0]
    second = result.returns.iloc[1]
    assert first == pytest.approx(-0.01)
    assert second == pytest.approx(-0.005)


def test_equal_weight_benchmark_has_uniform_weights():
    frame = backtest.equal_weight(pd.to_datetime(["2024-01-31"]), ["a", "b", "c", "d"])
    assert np.allclose(frame.to_numpy(), 0.25)


def test_turnover_uses_holdings_at_the_rebalance_close():
    assets = ["a", "b"]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    realised = panel([[0.20, 0.00], [0.00, 0.50]], ["2024-02-29", "2024-03-31"], assets)
    weights = panel([[0.5, 0.5], [0.5, 0.5]], origins, assets)
    mapping = contracts.target_dates(origins, realised.index)
    result = backtest.run_backtest(weights, realised, mapping, cost_bps=10)
    assert result.turnovers.iloc[1] == pytest.approx(0.60 / 1.10 - 0.50)


def test_run_models_always_adds_the_benchmark():
    assets = [f"s{i}" for i in range(20)]
    origins = pd.to_datetime(["2024-01-31"])
    realised = panel([np.zeros(20)], ["2024-02-29"], assets)
    weights = panel([[1.0] + [0.0] * 19], origins, assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    results = backtest.run_models({"A": weights}, realised, mapping, cost_bps=0.0)
    assert set(results) == {"A", "1/N"}


def test_backtest_rejects_weights_that_do_not_sum_to_one():
    assets = ["a", "b"]
    origins = pd.to_datetime(["2024-01-31"])
    realised = panel([[0.0, 0.0]], ["2024-02-29"], assets)
    weights = panel([[0.2, 0.2]], origins, assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    with pytest.raises(ValueError, match="sum"):
        backtest.run_backtest(weights, realised, mapping)


def test_frozen_execution_funds_both_sides_and_preserves_old_holding():
    previous = np.array([0.30, 0.70, 0.0])
    target = np.array([0.0, 0.0, 1.0])
    rates = 0.001
    weights, turnover, fee = execute_rebalance(target, previous, np.array([True, False, False]), rates)
    expected_fee = 1.40 * rates / (1 + rates)
    np.testing.assert_allclose(fee, expected_fee)
    np.testing.assert_allclose(weights * (1 - fee), [0.30, 0.0, 0.70 - expected_fee])
    np.testing.assert_allclose(turnover, 1.40 - fee)
    np.testing.assert_allclose(weights.sum(), 1.0)


def test_frozen_execution_charges_initial_purchase_and_next_month_returns():
    dates = pd.date_range("2023-01-01", periods=3, freq="ME")
    target = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=dates[:2], columns=["A", "B"])
    realised = pd.DataFrame([[0.20, 0.0], [0.10, -0.30]], index=dates[1:], columns=target.columns)
    blocked = pd.DataFrame([[False, False], [True, False]], index=dates[:2], columns=target.columns)
    result = backtest.run_backtest(
        target, realised, pd.Series(dates[1:], index=dates[:2]),
        cost_bps=10, suspensions=blocked, execution_mode=ExecutionMode.FROZEN_PER_SIDE,
    )
    np.testing.assert_allclose(result.returns, [1.20 / 1.001 - 1, 0.10])
    np.testing.assert_allclose(result.weights, [[1.0, 0.0], [1.0, 0.0]])


def test_immediate_per_side_mode_requires_no_dummy_suspensions():
    dates = pd.date_range("2023-01-01", periods=3, freq="ME")
    target = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=dates[:2], columns=["A", "B"])
    realised = pd.DataFrame([[0.20, 0.0], [0.10, -0.30]], index=dates[1:], columns=target.columns)
    mapping = pd.Series(dates[1:], index=dates[:2])
    explicit = backtest.run_backtest(
        target, realised, mapping, cost_bps=10, execution_mode=ExecutionMode.IMMEDIATE_PER_SIDE
    )
    all_false = pd.DataFrame(False, index=dates[:2], columns=target.columns)
    legacy_style = backtest.run_backtest(target, realised, mapping, cost_bps=10, suspensions=all_false)
    np.testing.assert_allclose(explicit.returns, legacy_style.returns)
    np.testing.assert_allclose(explicit.weights, legacy_style.weights)
