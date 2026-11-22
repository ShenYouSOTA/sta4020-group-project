"""End-to-end smoke test of the Part 3 -> Part 4 pipeline on mock artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path

from ..part4.cli import evaluate
from ..shared import contracts


def load_part3_module(root: Path):
    """Load part3_portfolio/Part3.py in-process while keeping its standalone location."""
    script = root / "part3_portfolio" / "Part3.py"
    spec = importlib.util.spec_from_file_location("sta4020_part3", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load Part 3 module from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_part3(root: Path, sample: Path, output_dir: Path) -> Path:
    """Run Part 3 on the mock artifacts and return the weights file."""
    part3 = load_part3_module(root)
    written = part3.run_part3(
        sample / "P1_Expected_Returns.csv",
        sample / "P2_Covariance.csv",
        sample / "Actual_Returns.csv",
        output_dir,
    )
    return written["weights"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--tag", type=str, default="sample")
    arguments = parser.parse_args(argv)

    root = contracts.Paths().root
    sample = root / "artifacts" / "sample"
    risk_free_path = root / "data" / "risk_free.csv"
    if not risk_free_path.exists():
        print(f"warning: {risk_free_path.name} not found under data/, assuming zero risk-free rate")
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
            weights_label="scratch run of part3_portfolio/Part3.py on artifacts/sample",
        )
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
