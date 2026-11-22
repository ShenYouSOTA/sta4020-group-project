"""Artifact contracts shared by all four parts of the STA4020 final project.

The four parts are written by four people, so every hand-off happens through a
CSV file under the artifacts/ directory.  This module is the single source of
truth for those file formats.  Part 3 and Part 4 both import it; a format
change must be made here first and then announced to the group.

Files
-----
artifacts/part1/P1_Expected_Returns.csv  (Part 1 -> Parts 3, 4)
    Wide. First column 'Date' = forecast origin (end of month t).
    One column per asset.  Value = expected SIMPLE return of month t+1.
artifacts/part1/P1_Validated_Expected_Returns.csv
    Legacy forecast from the superseded comparison notebook. Use only with
    the historical realised returns and covariance for its own fixed universe.
artifacts/part1/Actual_Returns.csv       (Part 1 -> Parts 3, 4)
    Same layout.  'Date' = end of month t+1, value = realised simple return
    of that month.
artifacts/part1/P1_Candidate_Universe.csv
    Fixed universe selected at OOS start (50 stocks, 2014-12-31).
artifacts/part2/P2_Covariance.csv        (Part 2 -> Parts 3, 4)
    Long: Date, Asset_1, Asset_2, Covariance.  One complete N x N matrix per
    forecast origin, in monthly decimal-return units (do NOT annualise).
artifacts/part3/Portfolio_Weights.csv    (Part 3 -> Part 4)
    Long: Date, Model, Asset, Weight.  One row per (origin, model, asset);
    weights must be non-negative and sum to one.
artifacts/part3/OOS_Portfolio_Returns.csv
    Long: Date, Model, Portfolio_Return.  Part 3's own realised returns, used
    by Part 4 only as a cross-check, never as an input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 12
DATE = "Date"
ASSET = "Asset"
MODEL = "Model"
WEIGHT = "Weight"
COV = "Covariance"
MIN_ASSETS = 20


def project_root(start: str | Path | None = None) -> Path:
    """Locate the group-project root (the directory holding artifacts/)."""
    path = Path(start or __file__).resolve()
    for candidate in (path, *path.parents):
        if (candidate / "artifacts").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError("cannot locate the group-project root (no artifacts/ + pyproject.toml)")


DEFAULT_EXPECTED_VARIANT = "raw"


def resolve_expected_returns(path: str | Path | None = None,
                             variant: str = DEFAULT_EXPECTED_VARIANT,
                             root: str | Path | None = None) -> Path:
    """The single place that decides which Part 1 forecast file is used.

    The default ('raw') is the current FM forecast. 'validated' explicitly
    opts into the legacy panel if present. An explicit path always wins.
    """
    if path is not None:
        return Path(path)
    paths = Paths(root=Path(root)) if root is not None else Paths()
    if variant == "raw":
        return paths.expected_returns
    if variant != "validated":
        raise ValueError(f"unknown expected-returns variant {variant!r}")
    validated = paths.validated_expected_returns
    return validated if validated.exists() else paths.expected_returns


@dataclass(frozen=True)
class Paths:
    """Default artifact locations, resolved once from the project root."""

    root: Path = field(default_factory=project_root)

    @property
    def expected_returns(self) -> Path:
        """Part 1's raw forecast file."""
        return self.root / "artifacts" / "part1" / "P1_Expected_Returns.csv"

    @property
    def validated_expected_returns(self) -> Path:
        """Legacy forecast after the old comparison notebook's validation step."""
        return self.root / "artifacts" / "part1" / "P1_Validated_Expected_Returns.csv"

    @property
    def actual_returns(self) -> Path:
        return self.root / "artifacts" / "part1" / "Actual_Returns.csv"

    @property
    def universe(self) -> Path:
        return self.root / "artifacts" / "part1" / "P1_Candidate_Universe.csv"

    @property
    def covariance(self) -> Path:
        return self.root / "artifacts" / "part2" / "P2_Covariance.csv"

    @property
    def weights(self) -> Path:
        return self.root / "artifacts" / "part3" / "Portfolio_Weights.csv"

    @property
    def part3_returns(self) -> Path:
        return self.root / "artifacts" / "part3" / "OOS_Portfolio_Returns.csv"


def read_wide(path: str | Path, *, label: str = "frame") -> pd.DataFrame:
    """Read a Date + one-column-per-asset CSV into a float frame indexed by date."""
    frame = pd.read_csv(path)
    if DATE not in frame.columns:
        raise ValueError(f"{label}: missing {DATE!r} column in {path}")
    frame[DATE] = pd.to_datetime(frame[DATE], errors="raise")
    frame = frame.set_index(DATE).sort_index()
    if frame.index.has_duplicates:
        raise ValueError(f"{label}: duplicated dates in {path}")
    frame = frame.apply(pd.to_numeric, errors="raise")
    frame.columns = [str(column).strip() for column in frame.columns]
    if frame.shape[0] == 0 or frame.shape[1] == 0:
        raise ValueError(f"{label}: empty frame in {path}")
    return frame


def read_expected(path: str | Path | None = None) -> pd.DataFrame:
    """Part 1 expected returns: origin date x asset, decimal monthly units."""
    return read_wide(path or Paths().expected_returns, label="P1_Expected_Returns")


def read_actual(path: str | Path | None = None) -> pd.DataFrame:
    """Part 1 realised returns: month-end date x asset, decimal monthly units."""
    return read_wide(path or Paths().actual_returns, label="Actual_Returns")


def read_universe(path: str | Path | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path or Paths().universe)
    if ASSET not in frame.columns:
        raise ValueError(f"universe file has no {ASSET!r} column")
    frame[ASSET] = frame[ASSET].astype(str).str.strip()
    return frame


def read_weights(path: str | Path | None = None) -> pd.DataFrame:
    """Part 3 weights, long format, lightly validated."""
    frame = pd.read_csv(path or Paths().weights)
    missing = {DATE, MODEL, ASSET, WEIGHT} - set(frame.columns)
    if missing:
        raise ValueError(f"weights file missing columns: {sorted(missing)}")
    frame[DATE] = pd.to_datetime(frame[DATE], errors="raise")
    frame[MODEL] = frame[MODEL].astype(str)
    frame[ASSET] = frame[ASSET].astype(str).str.strip()
    frame[WEIGHT] = pd.to_numeric(frame[WEIGHT], errors="raise")
    return frame.sort_values([DATE, MODEL, ASSET]).reset_index(drop=True)


def weights_to_wide(weights: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Long weights -> {model: DataFrame(origin x asset)}."""
    out: dict[str, pd.DataFrame] = {}
    for model, block in weights.groupby(MODEL, sort=True):
        wide = block.pivot(index=DATE, columns=ASSET, values=WEIGHT)
        if wide.isna().to_numpy().any():
            raise ValueError(f"model {model!r}: incomplete weight matrix (missing assets on some dates)")
        out[str(model)] = wide.sort_index()
    return out


def read_covariance_panel(path: str | Path | None = None,
                          assets: list[str] | None = None) -> dict[pd.Timestamp, np.ndarray]:
    """Part 2 long covariance -> {origin: (N, N) ndarray} ordered by the assets list."""
    frame = pd.read_csv(path or Paths().covariance)
    missing = {DATE, "Asset_1", "Asset_2", COV} - set(frame.columns)
    if missing:
        raise ValueError(f"covariance file missing columns: {sorted(missing)}")
    frame[DATE] = pd.to_datetime(frame[DATE], errors="raise")
    for column in ("Asset_1", "Asset_2"):
        frame[column] = frame[column].astype(str).str.strip()
    frame[COV] = pd.to_numeric(frame[COV], errors="raise")

    panel: dict[pd.Timestamp, np.ndarray] = {}
    for origin, block in frame.groupby(DATE, sort=True):
        try:
            matrix = block.pivot(index="Asset_1", columns="Asset_2", values=COV)
        except ValueError as error:
            raise ValueError(f"{origin}: duplicated covariance entries ({error})") from error
        if assets is not None:
            absent = set(assets) - set(matrix.index)
            if absent:
                raise ValueError(f"{origin}: covariance missing {len(absent)} assets, e.g. {sorted(absent)[:3]}")
            matrix = matrix.reindex(index=assets, columns=assets)
        values = matrix.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{origin}: covariance contains NaN/inf")
        if not np.allclose(values, values.T, rtol=1e-6, atol=1e-12):
            raise ValueError(f"{origin}: covariance matrix is not symmetric")
        if np.any(np.diag(values) <= 0):
            raise ValueError(f"{origin}: covariance has a non-positive diagonal")
        panel[origin] = values
    if not panel:
        raise ValueError("covariance file is empty")
    return panel


def target_dates(origins: pd.Index, realisation_dates: pd.Index) -> pd.Series:
    """Map each forecast origin to the first realised month-end strictly after it."""
    ordered = pd.DatetimeIndex(sorted(pd.DatetimeIndex(realisation_dates).unique()))
    mapped: dict[pd.Timestamp, pd.Timestamp] = {}
    missing: list[pd.Timestamp] = []
    for origin in pd.DatetimeIndex(origins):
        position = ordered.searchsorted(origin, side="right")
        if position >= len(ordered):
            missing.append(origin)
            continue
        mapped[origin] = ordered[position]
    if missing:
        raise ValueError(f"{len(missing)} origins have no realised month, e.g. {missing[:3]}")
    series = pd.Series(mapped, name="target_date")
    series.index.name = DATE
    return series.sort_index()


@dataclass
class ContractReport:
    """Collected findings of one full artifact audit."""

    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def summary(self) -> str:
        lines = [f"{'PASS' if self.ok else 'FAIL'}: {len(self.issues)} issue(s)"]
        lines += [f"  issue: {item}" for item in self.issues]
        lines += [f"  note:  {item}" for item in self.notes]
        return "\n".join(lines)


def audit(expected: pd.DataFrame, actual: pd.DataFrame, *,
          weights: pd.DataFrame | None = None,
          covariance: dict[pd.Timestamp, np.ndarray] | None = None,
          min_assets: int = MIN_ASSETS) -> ContractReport:
    """Check the cross-part hand-off rules that repeatedly break integration."""
    report = ContractReport()

    if len(expected.columns) < min_assets:
        report.issues.append(f"only {len(expected.columns)} assets (need >= {min_assets})")
    if not expected.columns.equals(actual.columns):
        report.issues.append("expected and actual return files do not share the same asset order")
    if expected.isna().to_numpy().any():
        report.issues.append("expected returns contain NaN")
    if actual.isna().to_numpy().any():
        report.issues.append("actual returns contain NaN")

    mapping = None
    try:
        mapping = target_dates(expected.index, actual.index)
        report.notes.append(f"{len(mapping)} origins mapped to realised months, "
                            f"{mapping.iloc[0].date()} .. {mapping.iloc[-1].date()}")
    except ValueError as error:
        report.issues.append(str(error))

    if mapping is not None:
        covered = set(mapping.values)
        unused = set(pd.DatetimeIndex(actual.index)) - covered
        if unused:
            report.issues.append(f"{len(unused)} realised months never used, e.g. {sorted(unused)[:3]}")
        if len(mapping) < 60:
            report.notes.append(f"only {len(mapping)} OOS months; the guideline asks for at least "
                                "5 years of monthly OOS data (60 months)")

    if weights is not None:
        totals = weights.groupby([DATE, MODEL])[WEIGHT].sum()
        bad = totals[(totals - 1.0).abs() > 1e-6]
        if len(bad):
            report.issues.append(f"{len(bad)} (date, model) blocks do not sum to one, e.g. {bad.head(3).to_dict()}")
        negative = weights[weights[WEIGHT] < -1e-10]
        if len(negative):
            report.issues.append(f"{len(negative)} negative weights (the brief requires long-only)")
        stray = set(pd.DatetimeIndex(weights[DATE])) - set(expected.index)
        if stray:
            report.issues.append(f"{len(stray)} weight dates are not forecast origins, e.g. {sorted(stray)[:3]}")
        absent = set(expected.index) - set(pd.DatetimeIndex(weights[DATE]))
        if absent:
            report.issues.append(f"{len(absent)} origins have no weights, e.g. {sorted(absent)[:3]}")

    if covariance is not None and weights is not None:
        missing = set(pd.DatetimeIndex(weights[DATE]).unique()) - set(covariance)
        if missing:
            report.issues.append(f"{len(missing)} origins have no covariance matrix, e.g. {sorted(missing)[:3]}")
    return report
