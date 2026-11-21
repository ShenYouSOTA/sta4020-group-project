#!/usr/bin/env python3
"""End-to-end smoke test of the Part 3 -> Part 4 pipeline on the mock artifacts.

The mock data in artifacts/sample is the fake 20 stock, 24 month panel that
shipped inside the Part 3 zip. It is the only data where all four parts exist,
so it is what proves the hand-off works before the real Part 1 and Part 2
outputs are available.

Usage:
    .venv/bin/python scripts/run_sample_pipeline.py [--cost-bps 10]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from sta4020_project.cli import evaluate  # noqa: E402


def run_part3(workdir: Path) -> Path:
    """Run the unmodified Part 3 script inside a scratch directory."""
    shutil.copy(PROJECT / "part3_portfolio" / "Part3.py", workdir / "Part3.py")
    for name in ("P1_Expected_Returns.csv", "P2_Covariance.csv", "Actual_Returns.csv"):
        shutil.copy(PROJECT / "artifacts" / "sample" / name, workdir / name)
    subprocess.run([sys.executable, "Part3.py"], cwd=workdir, check=True)
    return workdir / "Part3_Results" / "Portfolio_Weights.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--tag", type=str, default="sample")
    arguments = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="sta4020-sample-") as temporary:
        workdir = Path(temporary)
        weights = run_part3(workdir)
        written = evaluate(
            weights,
            PROJECT / "artifacts" / "sample" / "P1_Expected_Returns.csv",
            PROJECT / "artifacts" / "sample" / "Actual_Returns.csv",
            PROJECT / "part4_evaluation" / "reports" / arguments.tag,
            risk_free_path=PROJECT / "data" / "risk_free.csv",
            cost_bps=arguments.cost_bps,
            cost_levels=(0.0, 10.0, 30.0, 50.0),
        )
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
