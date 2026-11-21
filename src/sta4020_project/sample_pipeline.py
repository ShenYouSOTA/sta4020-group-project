"""End-to-end smoke test of the Part 3 -> Part 4 pipeline on the mock artifacts.

The mock data in artifacts/sample is the fake 20 stock, 24 month panel that
shipped inside the Part 3 zip.  It is the only data where all four parts exist,
so it is what proves the hand-off works before the real Part 1 and Part 2
outputs are available.

Part 3 is invoked through its command line with explicit paths, so the test does
not depend on a working directory either.

Usage:
    uv run sta4020-sample [--cost-bps 10] [--tag sample]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from . import contracts
from .cli import evaluate


def run_part3(root: Path, sample: Path, output_dir: Path) -> Path:
    """Run Part 3 on the mock artifacts and return the weights file."""
    command = [
        sys.executable,
        str(root / "part3_portfolio" / "Part3.py"),
        "--expected", str(sample / "P1_Expected_Returns.csv"),
        "--covariance", str(sample / "P2_Covariance.csv"),
        "--actual", str(sample / "Actual_Returns.csv"),
        "--output-dir", str(output_dir),
    ]
    subprocess.run(command, check=True)
    return output_dir / "Portfolio_Weights.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--tag", type=str, default="sample")
    arguments = parser.parse_args(argv)

    root = contracts.Paths().root
    sample = root / "artifacts" / "sample"
    risk_free_path = root / "data" / "risk_free.csv"
    if not risk_free_path.exists():
        print(f"warning: {risk_free_path.name} not found under data/, "
              f"so Sharpe ratios assume a zero risk-free rate")
        risk_free_path = None

    with tempfile.TemporaryDirectory(prefix="sta4020-sample-") as temporary:
        weights = run_part3(root, sample, Path(temporary))
        written = evaluate(
            weights,
            sample / "P1_Expected_Returns.csv",
            sample / "Actual_Returns.csv",
            root / "part4_evaluation" / "reports" / arguments.tag,
            risk_free_path=risk_free_path,
            cost_bps=arguments.cost_bps,
            cost_levels=(0.0, 10.0, 30.0, 50.0),
            weights_label="scratch run of part3_portfolio/Part3.py on artifacts/sample "
                          "(weights written to a temporary directory)",
        )
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
