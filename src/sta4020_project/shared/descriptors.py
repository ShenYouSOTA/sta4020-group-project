"""Transparent subset-cached loader for the 2.59 GiB vendor descriptor archive."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pickle
import subprocess
from tempfile import NamedTemporaryFile, TemporaryFile, gettempdir

import pandas as pd

from .market_data import monthly_panel

PROJECT_DESCRIPTOR_FIELDS: tuple[str, ...] = (
    "accrual_to_asset_ttm",
    "book_value_to_total_mktcap_mrq",
    "gross_profit_to_asset_ttm",
    "idios_vol_ff3_21",
    "mktcap",
    "momentum_21",
    "momentum_academic_252_21",
    "net_profit_to_total_mktcap_ttm",
    "return_on_invested_capital_ttm",
    "total_liab_to_total_asset_mrq",
    "turnover_252",
)

_MEMORY_CACHE: dict[tuple[str, int, int, tuple[str, ...]], dict[str, pd.Series]] = {}


def _source_signature(source: Path) -> tuple[str, int, int]:
    resolved = source.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_size, stat.st_mtime_ns


def _default_cache_dir() -> Path:
    env = os.environ.get("STA4020_CACHE_DIR")
    if env:
        return Path(env)
    return Path(gettempdir()) / "sta4020-descriptor-cache"


def _cache_file(cache_dir: Path, signature: tuple[str, int, int], fields: tuple[str, ...]) -> Path:
    payload = f"{signature[0]}|{signature[1]}|{signature[2]}|{','.join(fields)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"descriptors_subset_{digest}.pkl"


def _read_full_pickle(data_dir: Path, extracted_path: Path | None) -> dict[str, pd.Series]:
    if extracted_path is not None:
        with extracted_path.open("rb") as handle:
            return pickle.load(handle)
    with TemporaryFile() as handle:
        subprocess.run(
            ["unzip", "-p", str(data_dir / "addition" / "descriptors.zip"), "descriptors.pkl"],
            stdout=handle,
            check=True,
        )
        handle.seek(0)
        return pickle.load(handle)


def load_descriptor_subset(
    data_dir: Path,
    extracted_path: Path | None,
    names,
    *,
    cache_dir: Path | None = None,
) -> dict[str, pd.Series]:
    """Load only requested descriptor Series, caching the compact project subset on disk and in RAM."""
    requested = tuple(sorted(set(names)))
    source = extracted_path if extracted_path is not None else (data_dir / "addition" / "descriptors.zip")
    if not source.is_file():
        raise FileNotFoundError(f"descriptor source not found: {source}")
    signature = _source_signature(source)

    # Extract all canonical project fields together when requested fields are a subset,
    # so Part 1 and Part 2 share one compact cache file instead of unpacking 2.59 GiB repeatedly.
    cache_fields = (
        PROJECT_DESCRIPTOR_FIELDS
        if set(requested).issubset(PROJECT_DESCRIPTOR_FIELDS)
        else requested
    )
    mem_key = (*signature, cache_fields)
    if mem_key in _MEMORY_CACHE:
        cached = _MEMORY_CACHE[mem_key]
        return {name: cached[name] for name in requested}

    target_dir = cache_dir if cache_dir is not None else _default_cache_dir()
    cache_path = _cache_file(target_dir, signature, cache_fields)
    if cache_path.is_file():
        try:
            with cache_path.open("rb") as handle:
                subset = pickle.load(handle)
            if isinstance(subset, dict) and set(requested).issubset(subset):
                _MEMORY_CACHE[mem_key] = subset
                return {name: subset[name] for name in requested}
        except (OSError, EOFError, pickle.UnpicklingError):
            pass

    full = _read_full_pickle(data_dir, extracted_path)
    missing = [name for name in requested if name not in full]
    if missing:
        raise KeyError(f"descriptor source missing required fields: {missing}")

    available_cache_fields = tuple(name for name in cache_fields if name in full)
    subset = {name: full[name] for name in available_cache_fields}
    del full

    # Persist compact subset atomically; ignore read-only cache directory errors gracefully.
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="wb", dir=target_dir, delete=False) as handle:
            temp_path = Path(handle.name)
            pickle.dump(subset, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temp_path.replace(cache_path)
    except OSError:
        pass

    _MEMORY_CACHE[(*signature, available_cache_fields)] = subset
    return {name: subset[name] for name in requested}


def descriptor_fields(
    data_dir: Path,
    extracted_path: Path | None,
    dates: pd.DatetimeIndex,
    assets,
    names,
    *,
    cache_dir: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """Read required descriptor fields aligned to (dates x assets) via Period('M')."""
    subset = load_descriptor_subset(data_dir, extracted_path, names, cache_dir=cache_dir)
    wanted_periods = dates.to_period("M")
    fields: dict[str, pd.DataFrame] = {}
    for name in sorted(set(names)):
        series = subset[name]
        mask = (
            series.index.get_level_values("asset").isin(assets)
            & series.index.get_level_values("date").to_period("M").isin(wanted_periods)
        )
        fields[name] = monthly_panel(series[mask].unstack("asset"), dates, assets)
    return fields
