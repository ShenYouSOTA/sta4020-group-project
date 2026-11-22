import numpy as np
import pandas as pd
import pytest

from sta4020_project import attribution, contracts


def wide(values, dates, assets):
    return pd.DataFrame(values, index=pd.to_datetime(dates), columns=assets)


def test_gap_decomposes_exactly_into_signal_and_timing():
    assets = [f"s{i}" for i in range(4)]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    expected = wide([[0.01, 0.02, 0.03, 0.04], [0.04, 0.03, 0.02, 0.01]], origins, assets)
    realised = wide([[0.02, 0.01, 0.05, 0.00], [0.01, 0.05, 0.00, 0.02]],
                    ["2024-02-29", "2024-03-29"], assets)
    weights = pd.DataFrame(
        [[0.4, 0.3, 0.2, 0.1], [0.1, 0.2, 0.3, 0.4]], index=origins, columns=assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    frame = attribution.decompose(weights, expected, realised, mapping)
    assert np.allclose(frame["gap"], frame["signal"] + frame["timing"], atol=1e-12)


def test_equal_weight_has_no_gap_because_its_tilt_is_zero():
    assets = [f"s{i}" for i in range(4)]
    origins = pd.to_datetime(["2024-01-31"])
    expected = wide([[0.01, 0.02, 0.03, 0.04]], origins, assets)
    realised = wide([[0.02, 0.01, 0.05, 0.00]], ["2024-02-29"], assets)
    weights = pd.DataFrame([[0.25] * 4], index=origins, columns=assets)
    mapping = contracts.target_dates(weights.index, realised.index)
    frame = attribution.decompose(weights, expected, realised, mapping)
    assert frame["gap"].iloc[0] == pytest.approx(0.0, abs=1e-12)


def test_weight_diagnostics_are_one_row_per_origin():
    assets = [f"s{i}" for i in range(4)]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    expected = wide([[0.01] * 4, [0.02] * 4], origins, assets)
    weights = pd.DataFrame([[0.25] * 4, [0.4, 0.3, 0.2, 0.1]], index=origins, columns=assets)
    mapping = contracts.target_dates(weights.index, pd.to_datetime(["2024-02-29", "2024-03-29"]))
    frame = attribution.weight_diagnostics(weights, expected, mapping)
    assert len(frame) == 2
    assert np.isnan(frame["turnover"].iloc[0])          # nothing traded before the first origin
    assert frame["turnover"].iloc[1] == pytest.approx(0.2)


def test_attribution_uses_the_benchmark_weights_on_eligible_assets():
    origin = pd.to_datetime(["2024-01-31"])
    target = pd.to_datetime(["2024-02-29"])
    assets = ["a", "b", "excluded"]
    expected = wide([[0.02, 0, 0.1]], origin, assets)
    realised = wide([[0.04, 0, 0.3]], target, assets)
    weights = wide([[1, 0, 0]], origin, assets)
    benchmark = wide([[0.5, 0.5, 0]], origin, assets)
    frame = attribution.decompose(weights, expected, realised, contracts.target_dates(origin, target),
                                  benchmark_weights=benchmark)
    assert frame.iloc[0]["benchmark"] == pytest.approx(0.02)
    assert frame.iloc[0]["gap"] == pytest.approx(0.02)
