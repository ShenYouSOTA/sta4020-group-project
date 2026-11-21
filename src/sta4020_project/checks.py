"""Pre-flight checks: raw data present, and the inter-part CSVs well formed.

Both are exposed as console scripts by pyproject.toml, so they run as
`uv run sta4020-check-data` and `uv run sta4020-check-artifacts` without any
working directory assumption: paths are resolved from the project root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import contracts

REQUIRED_DATA = {
    "monthly_returns.pkl": "monthly returns panel",
    "mcap.pkl": "month-end market capitalisation",
    "daily_amount.pkl": "daily traded value",
    "BLACKLIST.pkl": "blacklisted stocks",
    "UNTRADABLE.pkl": "untradable stocks",
    "FF5.csv": "Fama-French five factors",
    "risk_free.csv": "daily risk-free rate",
    "zz500.pk": "CSI 500 daily bars",
}
OPTIONAL_DATA = {
    "price.h5": "daily adjusted prices (needed only for the daily frequency route)",
}


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def check_data(argv: list[str] | None = None) -> int:
    """Verify that the raw data files are where the pipeline expects them."""
    data = contracts.Paths().root / "data"
    missing = []
    print(f"data directory: {data}")
    for name, description in REQUIRED_DATA.items():
        path = data / name
        if path.exists():
            print(f"  ok       {name:<22} {human(path.stat().st_size):>9}  {description}")
        else:
            print(f"  MISSING  {name:<22} {'':>9}  {description}")
            missing.append(name)
    for name, description in OPTIONAL_DATA.items():
        path = data / name
        state = "ok      " if path.exists() else "missing "
        size = human(path.stat().st_size) if path.exists() else ""
        print(f"  {state} {name:<22} {size:>9}  {description} (optional)")

    if missing:
        print()
        print(f"{len(missing)} required file(s) missing.  Copy the raw data into data/;")
        print("see data/README.md for the expected layout.  A fresh clone never has them,")
        print("because the files are 530 MB and excluded from git.")
        return 1
    print()
    print("all required data files are present")
    return 0


def check_artifacts(argv: list[str] | None = None) -> int:
    """Validate the CSV artifacts that Parts 1-3 hand to Part 4."""
    parser = argparse.ArgumentParser(description=check_artifacts.__doc__)
    parser.add_argument("--expected", type=Path, default=None)
    parser.add_argument("--actual", type=Path, default=None)
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--covariance", type=Path, default=None)
    parser.add_argument("--sample", action="store_true", help="validate artifacts/sample instead")
    arguments = parser.parse_args(argv)

    paths = contracts.Paths()
    root = paths.root
    if arguments.sample:
        expected_path = root / "artifacts" / "sample" / "P1_Expected_Returns.csv"
        actual_path = root / "artifacts" / "sample" / "Actual_Returns.csv"
        weights_path = None
        covariance_path = root / "artifacts" / "sample" / "P2_Covariance.csv"
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
    weights = (contracts.read_weights(weights_path)
               if weights_path and Path(weights_path).exists() else None)
    assets = [column for column in expected.columns if column in actual.columns]
    covariance = None
    if covariance_path and Path(covariance_path).exists():
        try:
            covariance = contracts.read_covariance_panel(covariance_path, assets)
        except ValueError as error:
            print(f"covariance panel rejected: {error}")
            covariance = {}

    raw_path = root / "artifacts" / "part1" / "P1_Expected_Returns.csv"
    if Path(expected_path).name == "P1_Validated_Expected_Returns.csv" and raw_path.exists():
        raw = contracts.read_wide(raw_path, label="raw forecast")
        common = [column for column in expected.columns if column in raw.columns]
        gap = (expected[common] - raw[common]).abs().to_numpy().mean()
        print("using the validated forecast panel; mean absolute difference from the raw "
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
    sys.exit(check_data())
