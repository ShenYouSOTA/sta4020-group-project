#!/usr/bin/env python3
"""Validate the CSV artifacts that Parts 1-3 hand to Part 4.

Run it before every integration: it is the cheapest way to catch a date
convention or a unit mistake before it becomes a wrong Sharpe ratio.

Examples:
    .venv/bin/python scripts/check_artifacts.py
    .venv/bin/python scripts/check_artifacts.py --sample
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from sta4020_project import contracts  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=None)
    parser.add_argument("--actual", type=Path, default=None)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--covariance", type=Path, default=None)
    parser.add_argument("--sample", action="store_true", help="validate artifacts/sample instead")
    arguments = parser.parse_args(argv)

    paths = contracts.Paths()
    if arguments.sample:
        expected_path = PROJECT / "artifacts" / "sample" / "P1_Expected_Returns.csv"
        actual_path = PROJECT / "artifacts" / "sample" / "Actual_Returns.csv"
        weights_path = None
        covariance_path = PROJECT / "artifacts" / "sample" / "P2_Covariance.csv"
    else:
        expected_path = arguments.expected or contracts.resolve_expected_returns()
        actual_path = arguments.actual or paths.actual_returns
        weights_path = arguments.weights or paths.weights
        covariance_path = arguments.covariance or paths.covariance

    missing = [name for name, path in (("expected", expected_path), ("actual", actual_path))
               if path is None or not Path(path).exists()]
    if missing:
        print(f"missing required artifact(s): {', '.join(missing)}")
        return 2

    expected = contracts.read_wide(expected_path, label="expected returns")
    actual = contracts.read_wide(actual_path, label="realised returns")
    weights = contracts.read_weights(weights_path) if weights_path and Path(weights_path).exists() else None
    assets = [column for column in expected.columns if column in actual.columns]
    covariance = None
    if covariance_path and Path(covariance_path).exists():
        try:
            covariance = contracts.read_covariance_panel(covariance_path, assets)
        except ValueError as error:
            print(f"covariance panel rejected: {error}")
            covariance = {}

    raw_path = PROJECT / "artifacts" / "part1" / "P1_Expected_Returns.csv"
    if Path(expected_path).name == "P1_Validated_Expected_Returns.csv" and raw_path.exists():
        raw = contracts.read_wide(raw_path, label="raw forecast")
        common = [column for column in expected.columns if column in raw.columns]
        gap = (expected[common] - raw[common]).abs().to_numpy().mean()
        print(f"using the validated forecast panel; mean absolute difference from the raw "
              f"panel is {gap:.5f} per month (see the TODO in contracts.py)")

    report = contracts.audit(expected, actual, weights=weights, covariance=covariance or None)
    print(report.summary())
    print()
    print(f"expected: {expected_path}  shape={expected.shape}")
    print(f"realised: {actual_path}  shape={actual.shape}")
    print(f"assets in both files: {len(assets)}")
    if weights is not None:
        print(f"weights:  {weights_path}  models={sorted(weights['Model'].unique())}")
    else:
        print("weights:  not found (Part 3 has not produced Portfolio_Weights.csv yet)")
    if covariance is not None:
        print(f"covariance: {covariance_path}  origins={len(covariance)}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
