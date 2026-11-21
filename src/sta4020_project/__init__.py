"""Shared and Part 4 code for the STA4020 final project."""

from .contracts import (
    DEFAULT_EXPECTED_VARIANT,
    MIN_ASSETS,
    PERIODS_PER_YEAR,
    Paths,
    audit,
    resolve_expected_returns,
    project_root,
    read_actual,
    read_covariance_panel,
    read_expected,
    read_universe,
    read_weights,
    target_dates,
    weights_to_wide,
)
from . import attribution, backtest, contracts, metrics, report, stats

__all__ = [
    "DEFAULT_EXPECTED_VARIANT",
    "MIN_ASSETS",
    "PERIODS_PER_YEAR",
    "Paths",
    "audit",
    "attribution",
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
