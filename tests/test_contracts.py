import numpy as np
import pandas as pd
import pytest

from sta4020_project import contracts


def wide(values, dates, columns):
    return pd.DataFrame(values, index=pd.to_datetime(dates), columns=columns)


def test_target_dates_maps_to_first_strictly_later_month():
    origins = pd.to_datetime(["2024-01-31", "2024-02-29"])
    realised = pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-29"])
    mapping = contracts.target_dates(origins, realised)
    assert mapping.loc[pd.Timestamp("2024-01-31")] == pd.Timestamp("2024-02-29")
    assert mapping.loc[pd.Timestamp("2024-02-29")] == pd.Timestamp("2024-03-29")


def test_target_dates_rejects_origins_without_a_realised_month():
    origins = pd.to_datetime(["2024-01-31", "2024-05-31"])
    realised = pd.to_datetime(["2024-01-31", "2024-02-29"])
    with pytest.raises(ValueError):
        contracts.target_dates(origins, realised)


def test_weights_to_wide_splits_by_model_and_normalises_index():
    raw = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-31"] * 2 + ["2024-01-31"] * 2),
        "Model": ["A", "A", "B", "B"],
        "Asset": ["x", "y", "x", "y"],
        "Weight": [0.3, 0.7, 0.5, 0.5],
    })
    panels = contracts.weights_to_wide(raw)
    assert set(panels) == {"A", "B"}
    assert panels["A"].loc[pd.Timestamp("2024-01-31"), "x"] == pytest.approx(0.3)
    assert np.allclose(panels["B"].sum(axis=1), 1.0)


def test_audit_flags_weights_that_do_not_sum_to_one():
    assets = ["a", "b"]
    origins = pd.to_datetime(["2024-01-31"])
    expected = wide([[0.1, 0.2]], origins, assets)
    actual = wide([[0.05, 0.1]], pd.to_datetime(["2024-02-29"]), assets)
    weights = pd.DataFrame({"Date": pd.to_datetime(["2024-01-31"] * 2), "Model": ["A", "A"],
                            "Asset": ["a", "b"], "Weight": [0.4, 0.4]})
    report = contracts.audit(expected, actual, weights=weights)
    assert not report.ok
    assert any("sum" in issue.lower() for issue in report.issues)


def test_audit_accepts_a_clean_panel():
    assets = [f"s{i:02d}" for i in range(20)]
    origins = pd.to_datetime(["2024-01-31"])
    expected = wide([np.full(20, 0.01)], origins, assets)
    actual = wide([np.full(20, 0.005)], pd.to_datetime(["2024-02-29"]), assets)
    weights = pd.DataFrame({
        "Date": pd.to_datetime(["2024-01-31"] * 20),
        "Model": ["A"] * 20,
        "Asset": assets,
        "Weight": [0.05] * 20,
    })
    report = contracts.audit(expected, actual, weights=weights)
    assert report.ok, report.issues


def test_resolve_expected_returns_prefers_the_current_panel(tmp_path):
    part1 = tmp_path / "artifacts" / "part1"
    part1.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (part1 / "P1_Expected_Returns.csv").write_text("Date,a\n2024-01-31,0.01\n", encoding="utf-8")
    assert contracts.resolve_expected_returns(root=tmp_path).name == "P1_Expected_Returns.csv"
    (part1 / "P1_Validated_Expected_Returns.csv").write_text("Date,a\n2024-01-31,0.02\n",
                                                             encoding="utf-8")
    resolved = contracts.resolve_expected_returns(root=tmp_path)
    assert resolved.name == "P1_Expected_Returns.csv"
    legacy = contracts.resolve_expected_returns(variant="validated", root=tmp_path)
    assert legacy.name == "P1_Validated_Expected_Returns.csv"
    assert contracts.resolve_expected_returns(legacy, root=tmp_path) == legacy
    assert contracts.resolve_expected_returns(variant="raw", root=tmp_path).name == \
        "P1_Expected_Returns.csv"
