"""STA4020 final project: shared kernel, Part 1/2/4 domains, and pipeline orchestration."""

from .part4 import attribution, backtest, metrics, report, stats
from .shared import contracts
from .shared.contracts import (
    DEFAULT_EXPECTED_VARIANT,
    MIN_ASSETS,
    PERIODS_PER_YEAR,
    Paths,
    audit,
    project_root,
    read_actual,
    read_covariance_panel,
    read_expected,
    read_universe,
    read_weights,
    resolve_expected_returns,
    target_dates,
    weights_to_wide,
)

__all__ = [
    "DEFAULT_EXPECTED_VARIANT",
    "MIN_ASSETS",
    "PERIODS_PER_YEAR",
    "Paths",
    "attribution",
    "audit",
    "backtest",
    "contracts",
    "metrics",
    "project_root",
    "read_actual",
    "read_covariance_panel",
    "read_expected",
    "read_universe",
    "read_weights",
    "report",
    "resolve_expected_returns",
    "stats",
    "target_dates",
    "weights_to_wide",
]
