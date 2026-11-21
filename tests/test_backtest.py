import numpy as np
import pandas as pd
import pytest

from sta4020_project import backtest, contracts


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
    assert first == pytest.approx(-0.01)          # full purchase from cash, 100bp
    assert second == pytest.approx(-0.005)        # half the book traded, 100bp


def test_equal_weight_benchmark_has_uniform_weights():
    frame = backtest.equal_weight(pd.to_datetime(["2024-01-31"]), ["a", "b", "c", "d"])
    assert np.allclose(frame.to_numpy(), 0.25)


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
