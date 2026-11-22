"""Unit tests for shared descriptor subset caching and Part 3 portfolio construction."""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest

from sta4020_project.pipeline.sample import load_part3_module
from sta4020_project.shared import descriptors as desc_mod
from sta4020_project.shared.contracts import project_root
from sta4020_project.shared.tradability import active_mask


def test_descriptor_subset_cache_reuses_compact_file(tmp_path, monkeypatch):
    dates = pd.to_datetime(["2024-01-31", "2024-02-29"])
    assets = ["000001.SZ", "000002.SZ"]
    idx = pd.MultiIndex.from_product([dates, assets], names=["date", "asset"])
    payload = {
        "mktcap": pd.Series([100.0, 200.0, 110.0, 210.0], index=idx),
        "turnover_252": pd.Series([0.5, 0.8, 0.6, 0.9], index=idx),
        "unused_huge_field": pd.Series([1.0, 2.0, 3.0, 4.0], index=idx),
    }
    raw_pickle = tmp_path / "descriptors.pkl"
    with raw_pickle.open("wb") as handle:
        pickle.dump(payload, handle)

    cache_dir = tmp_path / "cache"
    desc_mod._MEMORY_CACHE.clear()
    read_calls = 0
    original_read = desc_mod._read_full_pickle

    def counting_read(data_dir, extracted_path):
        nonlocal read_calls
        read_calls += 1
        return original_read(data_dir, extracted_path)

    monkeypatch.setattr(desc_mod, "_read_full_pickle", counting_read)

    first = desc_mod.descriptor_fields(tmp_path, raw_pickle, dates, assets, ["mktcap"], cache_dir=cache_dir)
    assert read_calls == 1
    assert first["mktcap"].loc[dates[0], "000001.SZ"] == pytest.approx(100.0)

    # Second call in memory cache hits 0 full reads; clearing memory cache still hits disk subset cache!
    second = desc_mod.descriptor_fields(tmp_path, raw_pickle, dates, assets, ["turnover_252"], cache_dir=cache_dir)
    assert read_calls == 1
    assert second["turnover_252"].loc[dates[1], "000002.SZ"] == pytest.approx(0.9)

    desc_mod._MEMORY_CACHE.clear()
    third = desc_mod.descriptor_fields(tmp_path, raw_pickle, dates, assets, ["mktcap", "turnover_252"], cache_dir=cache_dir)
    assert read_calls == 1
    pd.testing.assert_frame_equal(third["mktcap"], first["mktcap"])


def test_active_mask_applies_configurable_delistings():
    dates = pd.to_datetime(["2023-04-30", "2023-05-31", "2023-06-30"])
    assets = ["300330.SZ", "000001.SZ"]
    mask = active_mask(dates, assets)
    assert mask.loc[dates[0], "300330.SZ"]
    assert not mask.loc[dates[1], "300330.SZ"]
    assert mask["000001.SZ"].all()


def test_part3_optimizers_and_dict_covariance_respect_constraints(tmp_path):
    part3 = load_part3_module(project_root())
    rng = np.random.default_rng(7)
    n = 20
    assets = [f"A{i:02d}" for i in range(n)]
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    realised_dates = pd.to_datetime(["2024-02-29", "2024-03-31"])

    expected = pd.DataFrame(rng.normal(0.01, 0.02, (2, n)), index=origins, columns=assets)
    actual = pd.DataFrame(rng.normal(0.005, 0.03, (2, n)), index=realised_dates, columns=assets)
    factor = rng.normal(0, 0.04, (n, 3))
    sigma = factor @ factor.T + np.diag(rng.uniform(0.002, 0.01, n))
    cov_dict = {origin: sigma for origin in origins}

    weights_df, returns_df, forecasts_df = part3.build_portfolios(
        expected, actual, cov_dict, risk_aversion=5.0, max_weight=0.10
    )
    assert set(weights_df["Model"]) == set(part3.MODELS)
    assert weights_df["Weight"].min() >= -1e-12
    assert weights_df["Weight"].max() <= 0.10 + 1e-8
    sums = weights_df.groupby(["Date", "Model"])["Weight"].sum()
    np.testing.assert_allclose(sums.to_numpy(), 1.0, atol=1e-8)
    assert len(returns_df) == 2 * len(part3.MODELS)
    assert len(forecasts_df) == 2 * len(part3.MODELS)
