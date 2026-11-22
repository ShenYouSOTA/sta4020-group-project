"""Build monthly covariance forecasts against the Part 1 calendar."""

from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import pandas as pd

from ..shared.contracts import Paths, read_wide
from ..shared.market_data import monthly_panel
from ..shared.tradability import DELISTED_ASSET, DELISTED_FROM


def sample_covariances(returns: pd.DataFrame, origins, *, shrink: bool = False):
    """Use each expanding history and carry the delisted asset's last risk."""
    for origin in origins:
        history = returns.loc[:origin]
        if len(history) < 2:
            raise ValueError(f"need at least two observations at {origin.date()}")
        active = history
        if DELISTED_ASSET in history and origin >= DELISTED_FROM:
            active = history.drop(columns=DELISTED_ASSET)
        covariance = active.cov().to_numpy()
        if shrink:
            from risk_model.stable_risk import shrink_covariance

            covariance = shrink_covariance(
                covariance, method="ledoit_wolf", returns=active.to_numpy()
            )
        if len(active.columns) == len(history.columns):
            yield covariance
        else:
            frozen = history.loc[history.index < DELISTED_FROM, DELISTED_ASSET].var()
            yield restore_delisted_asset(covariance, history.columns, frozen)


def restore_delisted_asset(active_covariance: np.ndarray, assets: pd.Index, frozen_variance: float) -> np.ndarray:
    """Keep the delisted name in the contract with a frozen standalone variance."""
    active = np.asarray(assets != DELISTED_ASSET)
    matrix = np.zeros((len(assets), len(assets)))
    matrix[np.ix_(active, active)] = active_covariance
    position = assets.get_loc(DELISTED_ASSET)
    matrix[position, position] = frozen_variance
    return matrix


def write_covariances(path: Path, origins, assets, matrices) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = pd.MultiIndex.from_product([assets, assets], names=["Asset_1", "Asset_2"])
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary_path = Path(handle.name)
            for index, (origin, matrix) in enumerate(zip(origins, matrices, strict=True)):
                if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T):
                    raise ValueError(f"invalid covariance at {origin.date()}")
                eigenvalues = np.linalg.eigvalsh(matrix)
                if np.any(matrix.diagonal() <= 0) or eigenvalues[0] < -1e-10:
                    raise ValueError(f"invalid covariance at {origin.date()}")
                frame = pd.DataFrame({"Covariance": matrix.ravel()}, index=keys).reset_index()
                frame.insert(0, "Date", origin)
                frame.to_csv(handle, index=False, header=index == 0)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv=None) -> int:
    paths = Paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=paths.expected_returns)
    parser.add_argument("--universe", type=Path, default=paths.universe)
    parser.add_argument("--data-dir", type=Path, default=paths.root / "data")
    parser.add_argument("--output", type=Path, default=paths.covariance)
    parser.add_argument("--history-start", default="2013-01")
    parser.add_argument("--method", choices=["sample", "ledoit-wolf", "factor", "broad-factor"], default="sample")
    parser.add_argument("--descriptors", type=Path, help="optional extracted descriptors.pkl")
    parser.add_argument("--broad-start", default="2005-01")
    args = parser.parse_args(argv)

    expected = read_wide(args.expected)
    assets = pd.read_csv(args.universe)["Asset"].tolist()
    if len(set(assets)) != len(assets) or set(expected.columns) != set(assets):
        raise ValueError("candidate universe and forecasts must contain the same unique assets")
    origins = expected.index
    if origins.empty or not origins.is_month_end.all():
        raise ValueError("expected returns must contain calendar month-end origins")
    dates = pd.date_range(args.history_start, origins[-1], freq="ME")
    returns = monthly_panel(pd.read_pickle(args.data_dir / "monthly_returns.pkl"), dates, assets)
    if not origins.isin(dates).all() or not np.isfinite(returns.to_numpy()).all():
        raise ValueError("monthly returns must cover every asset and month in the estimation window")

    if args.method == "broad-factor":
        from .broad_risk import load_history, write_broad_risk

        history = load_history(args.data_dir, args.descriptors, origins, pd.Index(assets),
                               dates[0], args.broad_start)
        write_broad_risk(args.output, history, origins, assets)
        print(f"broad-factor: wrote {len(origins)} covariance blocks for {len(assets)} assets to {args.output}")
        return 0

    if args.method == "factor":
        from .styles import factor_covariances, load_risk_panel

        panel, imputation = load_risk_panel(args.data_dir, returns, args.descriptors)
        matrices = factor_covariances(panel, origins)
    else:
        matrices = sample_covariances(returns, origins, shrink=args.method == "ledoit-wolf")
    write_covariances(args.output, origins, assets, matrices)
    if args.method == "factor":
        imputation.to_csv(args.output.with_suffix(".imputation.csv"))
    print(f"{args.method}: wrote {len(origins)} covariance blocks for {len(assets)} assets to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
