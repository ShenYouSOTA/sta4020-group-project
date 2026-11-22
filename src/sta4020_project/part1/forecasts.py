"""Reproduce the fixed-pool FM and test the preregistered lagged extension."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ..shared.contracts import Paths, read_wide
from ..shared.descriptors import descriptor_fields
from .features import MIN_FACTOR_PAIRS, TRAIN_MONTHS, ReturnFeatures

MIN_IC_MONTHS = 48
RIDGE_PENALTY = 0.10
FDR_Q = 0.10
BLOCK_MONTHS = 6
BOOTSTRAPS = 1999
SEED = 4020

ACCOUNTING = (
    "book_value_to_total_mktcap_mrq",
    "net_profit_to_total_mktcap_ttm",
    "return_on_invested_capital_ttm",
    "gross_profit_to_asset_ttm",
    "accrual_to_asset_ttm",
    "total_liab_to_total_asset_mrq",
)


def block_draws(n_dates: int, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n_dates / BLOCK_MONTHS))
    starts = rng.integers(n_dates, size=(BOOTSTRAPS, n_blocks, 1))
    indices = (starts + np.arange(BLOCK_MONTHS)) % n_dates
    return indices.reshape(BOOTSTRAPS, -1)[:, :n_dates]


def by_adjust(p_values: pd.Series) -> pd.Series:
    valid = p_values.dropna().sort_values()
    m = len(valid)
    ranks = np.arange(1, m + 1)
    scaled = valid.to_numpy() * m * np.sum(1 / ranks) / ranks
    adjusted = np.minimum.accumulate(scaled[::-1])[::-1].clip(0, 1)
    return pd.Series(adjusted, index=valid.index).reindex(p_values.index)


def screen_factors(ic_history: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    means = ic_history.mean()
    centered = ic_history.sub(means).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        samples = centered[block_draws(len(ic_history))]
        sampled_means = np.nansum(samples, axis=1) / np.isfinite(samples).sum(axis=1)
    valid_draws = np.isfinite(sampled_means).sum(axis=0)
    extreme = (np.abs(sampled_means) >= means.abs().to_numpy()).sum(axis=0)
    p_values = pd.Series((extreme + 1) / (valid_draws + 1), index=means.index)
    p_values = p_values.where(ic_history.count().ge(MIN_IC_MONTHS))
    summary = pd.DataFrame({
        "mean_rank_ic": means,
        "months": ic_history.count(),
        "p_value": p_values,
        "q_value": by_adjust(p_values),
    })
    selected = summary.loc[summary.q_value.le(FDR_Q)].sort_values("q_value", kind="stable")
    return selected.index.to_list(), summary


def rank_ic(signal: pd.Series, target: pd.Series) -> float:
    measured = signal.notna() & target.notna()
    signal, target = signal.loc[measured], target.loc[measured]
    if len(signal) < MIN_FACTOR_PAIRS or signal.nunique() < 2 or target.nunique() < 2:
        return np.nan
    return float(spearmanr(signal, target).statistic)


def training_statistics(features: pd.DataFrame, target: pd.Series) -> dict:
    valid = target.notna()
    target = target.loc[valid]
    if len(target) < MIN_FACTOR_PAIRS:
        raise ValueError(f"need at least {MIN_FACTOR_PAIRS} valid targets, got {len(target)}")
    factor_ic = features.loc[valid].apply(rank_ic, target=target)
    design = features.loc[valid].fillna(0).to_numpy(dtype=float)
    low, high = target.quantile([0.01, 0.99])
    response = target.clip(low, high).to_numpy()
    design_mean, response_mean = design.mean(axis=0), response.mean()
    centered_design, centered_response = design - design_mean, response - response_mean
    # Cache moments so different screened subsets can reuse the same monthly sample.
    return {
        "ic": factor_ic,
        "design_mean": design_mean,
        "response_mean": response_mean,
        "gram": centered_design.T @ centered_design / len(target),
        "cross": centered_design.T @ centered_response / len(target),
        "raw_return_mean": target.mean(),
    }


def fama_macbeth_ridge(train_stats: list[dict], factor_names: list[str], feature_columns: pd.Index) -> np.ndarray:
    if not factor_names:
        return np.array([np.mean([stats["response_mean"] for stats in train_stats])])
    selected = feature_columns.get_indexer(factor_names)
    if (selected < 0).any():
        raise ValueError(f"unknown factor names: {factor_names}")
    penalty = np.eye(len(selected)) * RIDGE_PENALTY
    monthly_coefficients = []
    for stats in train_stats:
        slopes = np.linalg.solve(
            stats["gram"][np.ix_(selected, selected)] + penalty, stats["cross"][selected]
        )
        intercept = stats["response_mean"] - stats["design_mean"][selected] @ slopes
        monthly_coefficients.append(np.r_[intercept, slopes])
    return np.mean(monthly_coefficients, axis=0)


def rank_features(raw: pd.DataFrame) -> pd.DataFrame:
    ranked = raw.rank(method="average").sub(0.5).div(raw.count())
    return (np.sqrt(12) * (ranked - 0.5)).astype("float32")


def build_forecasts(data_dir: Path, expected: pd.DataFrame, descriptors: Path | None = None):
    origins = expected.index.to_period("M")
    features = ReturnFeatures(data_dir, origins)
    months = pd.period_range(origins[0] - TRAIN_MONTHS - 1, origins[-1], freq="M")
    descriptor_dates = (months - 1).to_timestamp(how="end").normalize()
    fields = descriptor_fields(data_dir, descriptors, descriptor_dates, features.assets, ACCOUNTING)
    baseline_stats, extended_stats = {}, {}
    baseline_rows, extended_rows, historical_rows, coverage_rows, selection_rows = [], [], [], [], []
    signal_rows = []
    for month, descriptor_date in zip(months, descriptor_dates, strict=True):
        raw = features.at(month)
        accounting = pd.DataFrame({field: values.loc[descriptor_date].reindex(raw.index)
                                   for field, values in fields.items()}).replace([np.inf, -np.inf], np.nan)
        base = rank_features(raw)
        extended = base.join(rank_features(accounting))
        coverage_rows.append({"Formation": month, "DescriptorMonth": descriptor_date,
                              "Eligible": len(raw), **accounting.notna().mean().to_dict()})
        if month in origins:
            signal_rows.append(expected.columns.isin(raw.index))
            train_months = pd.period_range(month - TRAIN_MONTHS - 1, month - 2, freq="M")
            if features.last_close.loc[train_months[-1] + 1] >= features.signal_close.loc[month]:
                raise ValueError(f"{month}: training label is unavailable at signal time")
            selection = {"Formation": month, "LastLabel": train_months[-1] + 1}
            common = 0.0
            for model, stats, scores, rows in (
                ("FM", baseline_stats, base, baseline_rows),
                ("Extended", extended_stats, extended, extended_rows),
            ):
                training = [stats[past] for past in train_months]
                ic_history = pd.DataFrame([record["ic"] for record in training], index=train_months)
                selected, _ = screen_factors(ic_history)
                coefficients = fama_macbeth_ridge(training, selected, scores.columns)
                prediction = coefficients[0] + scores[selected].fillna(0) @ coefficients[1:]
                common = np.mean([record["raw_return_mean"] for record in training])
                rows.append(prediction.reindex(expected.columns).fillna(common))
                selection[model] = ", ".join(selected)
            mean = features.returns.loc[month - TRAIN_MONTHS:month - 1, expected.columns].mean()
            historical_rows.append(mean.fillna(common))
            selection_rows.append(selection)
        if month <= origins[-1] - 2:
            target = features.returns.loc[month + 1].reindex(base.index)
            baseline_stats[month] = training_statistics(base, target)
            extended_stats[month] = training_statistics(extended, target)
    frames = [pd.DataFrame(rows, index=expected.index)
              for rows in (baseline_rows, extended_rows, historical_rows)]
    if not np.allclose(frames[0].to_numpy(), expected.to_numpy(), rtol=0, atol=1e-9):
        max_diff = float(np.nanmax(np.abs(frames[0].to_numpy() - expected.to_numpy())))
        raise ValueError(f"Rebuilt 11-candidate FM differs from delivered forecast (max diff {max_diff:.3e})")
    return dict(zip(("fm", "extended", "historical"), frames, strict=True)), {
        "descriptor_coverage": pd.DataFrame(coverage_rows),
        "factor_selection": pd.DataFrame(selection_rows),
        "signal_eligibility": (
            pd.DataFrame(signal_rows, columns=expected.columns)
            .assign(Date=expected.index)
            .set_index("Date")
            .reset_index()
        ),
    }


def main(argv=None) -> int:
    paths = Paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=paths.expected_returns)
    parser.add_argument("--data-dir", type=Path, default=paths.root / "data")
    parser.add_argument("--descriptors", type=Path)
    parser.add_argument("--output-dir", type=Path, default=paths.root / "artifacts/part1/final")
    args = parser.parse_args(argv)
    expected = read_wide(args.expected)
    forecasts, audits = build_forecasts(args.data_dir, expected, args.descriptors)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in forecasts.items():
        frame.to_csv(args.output_dir / f"{name}.csv", index_label="Date")
    for name, audit in audits.items():
        audit.to_csv(args.output_dir / f"{name}.csv", index=False)
    print(f"Rebuilt FM and wrote forecasts and audits to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
