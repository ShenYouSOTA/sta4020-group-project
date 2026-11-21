#!/usr/bin/env python3
"""Verify that the raw data files are where the pipeline expects them.

The data directory is not in git, so a fresh clone has no data.  This script
turns that silent failure into a list of what is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"

REQUIRED = {
    "monthly_returns.pkl": "monthly returns panel",
    "mcap.pkl": "month-end market capitalisation",
    "daily_amount.pkl": "daily traded value",
    "BLACKLIST.pkl": "blacklisted stocks",
    "UNTRADABLE.pkl": "untradable stocks",
    "FF5.csv": "Fama-French five factors",
    "risk_free.csv": "daily risk-free rate",
    "zz500.pk": "CSI 500 daily bars",
}
OPTIONAL = {
    "price.h5": "daily adjusted prices (needed only for the daily frequency route)",
}


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main() -> int:
    missing = []
    print(f"data directory: {DATA}")
    for name, description in REQUIRED.items():
        path = DATA / name
        if path.exists():
            print(f"  ok       {name:<22} {human(path.stat().st_size):>9}  {description}")
        else:
            print(f"  MISSING  {name:<22} {'':>9}  {description}")
            missing.append(name)
    for name, description in OPTIONAL.items():
        path = DATA / name
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


if __name__ == "__main__":
    sys.exit(main())
