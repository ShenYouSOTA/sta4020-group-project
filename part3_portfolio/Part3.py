#!/usr/bin/env python3
"""Part 3 - portfolio construction.

Reads expected returns (Part 1) and covariance panels (Part 2), builds five
long-only portfolios per rebalancing month, and writes weights for Part 4.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from sta4020_project.shared.contracts import Paths, read_covariance_panel, read_wide
from sta4020_project.shared.market_data import monthly_panel, monthly_risk_free
from sta4020_project.shared.tradability import load_eligibility

# =====================================
# 1. DEFAULTS
# =====================================

PROJECT = Path(__file__).resolve().parents[1]

PERIODS_PER_YEAR = 12
RISK_AVERSION = 5.0
MAX_WEIGHT = None
RISK_FREE_RATE = 0.0

MODELS = (
    "Mean-Variance Optimization",
    "Global Minimum Variance",
    "Maximum Diversification",
    "Risk Parity",
    "Black-Litterman",
)


def default_expected_returns() -> Path:
    return Paths(PROJECT).expected_returns


def default_covariance() -> Path:
    return Paths(PROJECT).covariance


def default_actual_returns() -> Path:
    return Paths(PROJECT).actual_returns


def default_output_dir() -> Path:
    return PROJECT / "artifacts" / "part3"


# =====================================
# 2. LOAD DATA
# =====================================


def load_panel(path: Path, label: str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return read_wide(path, label=label)


def load_covariance(path: Path, assets: list[str] | None = None) -> dict[pd.Timestamp, np.ndarray]:
    """Load long covariance CSV into an O(1) {origin: (N, N) ndarray} map."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"covariance panel not found: {path}")
    return read_covariance_panel(path, assets=assets)


# =====================================
# 3. COVARIANCE MATRIX
# =====================================


def floor_covariance(sigma: np.ndarray, date) -> np.ndarray:
    """Symmetrize and floor eigenvalues at 1e-10 for numerical optimization."""
    if not np.allclose(sigma, sigma.T, rtol=0.0, atol=1e-12):
        sigma = (sigma + sigma.T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(sigma)
    if (eigenvalues < -1e-8).any():
        warnings.warn(f"{date}: covariance has a negative eigenvalue "
                      f"{eigenvalues.min():.3e}; flooring it")
    return eigenvectors @ np.diag(np.maximum(eigenvalues, 1e-10)) @ eigenvectors.T


def covariance_at(
    covariance: dict[pd.Timestamp, np.ndarray] | pd.DataFrame,
    date,
    assets: list[str],
    *,
    panel_assets: list[str] | None = None,
) -> np.ndarray:
    """Extract the symmetric PSD-floored covariance submatrix for one origin date."""
    if isinstance(covariance, dict):
        if date not in covariance:
            raise ValueError(f"no covariance rows for {date}")
        matrix = covariance[date]
        if panel_assets is not None and assets != panel_assets:
            index_map = {asset: idx for idx, asset in enumerate(panel_assets)}
            positions = [index_map[asset] for asset in assets]
            matrix = matrix[np.ix_(positions, positions)]
        if np.isnan(matrix).any():
            raise ValueError(f"incomplete covariance matrix at {date}")
        return floor_covariance(matrix, date)

    frame = covariance[covariance["Date"] == date]
    if frame.empty:
        raise ValueError(f"no covariance rows for {date}")
    sigma = frame.pivot_table(
        index="Asset_1", columns="Asset_2", values="Covariance", aggfunc="first"
    ).reindex(index=assets, columns=assets).to_numpy(dtype=float)
    if np.isnan(sigma).any():
        missing = [asset for asset in assets if np.isnan(sigma[assets.index(asset)]).any()]
        raise ValueError(f"incomplete covariance matrix at {date} for {missing[:5]}")
    return floor_covariance(sigma, date)


# =====================================
# 4. PORTFOLIO OPTIMIZATION
# =====================================


def optimize_portfolio(mu, sigma: np.ndarray, method: str, *,
                       risk_aversion: float = RISK_AVERSION,
                       max_weight: float | None = MAX_WEIGHT) -> np.ndarray:
    n = len(mu)
    mu = np.asarray(mu, dtype=float)
    upper = max_weight if max_weight is not None else 1.0
    individual_vol = np.sqrt(np.diag(sigma))

    def objective(w):
        marginal = sigma @ w
        variance = w @ marginal

        if method == "Mean-Variance":
            return -w @ mu + 0.5 * risk_aversion * variance, -mu + risk_aversion * marginal

        if method == "GMV":
            return variance, 2 * marginal

        denominator = max(variance, 1e-12)
        variance_gradient = 2 * marginal if variance > 1e-12 else np.zeros_like(w)

        if method == "Maximum Diversification":
            numerator = w @ individual_vol
            volatility = np.sqrt(denominator)
            gradient = (-individual_vol + 0.5 * numerator * variance_gradient / denominator)
            return -numerator / volatility, gradient / volatility

        if method == "Risk Parity":
            contribution = w * marginal / denominator
            error = contribution - 1 / n
            gradient = (error * marginal + sigma @ (error * w)
                        - (error @ contribution) * variance_gradient)
            return error @ error, 2 * gradient / denominator

        raise ValueError(f"unknown method {method!r}")

    result = minimize(
        objective,
        np.ones(n) / n,
        method="SLSQP",
        jac=True,
        bounds=[(0.0, upper)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}],
        options={"maxiter": 2000, "ftol": 1e-12},
    )

    if not result.success:
        raise ValueError(result.message)

    weights = np.maximum(result.x, 0.0)
    total = weights.sum()
    if total <= 0:
        raise ValueError("optimiser returned an all-zero portfolio")
    return weights / total


# =====================================
# 5. BLACK-LITTERMAN
# =====================================


def black_litterman(mu, sigma: np.ndarray, *,
                    risk_aversion: float = RISK_AVERSION,
                    market_weights: np.ndarray | None = None, risk_free: float = 0.0) -> np.ndarray:
    n = len(mu)
    market_weights = np.ones(n) / n if market_weights is None else market_weights
    prior = risk_aversion * sigma @ market_weights

    tau = 0.05
    P = np.eye(n)
    Q = np.asarray(mu, dtype=float) - risk_free
    omega = np.diag(np.diag(tau * sigma) / 0.5)

    middle = P @ (tau * sigma) @ P.T + omega
    return risk_free + prior + tau * sigma @ P.T @ np.linalg.solve(middle, Q - P @ prior)


# =====================================
# 6. PERFORMANCE SUMMARY (console only)
# =====================================


def performance_summary(returns, *, periods_per_year: int = PERIODS_PER_YEAR,
                        risk_free_rate: float = RISK_FREE_RATE) -> pd.Series:
    r = pd.Series(returns).dropna()
    wealth = (1.0 + r).cumprod()
    deviation = r.std()

    annual_return = wealth.iloc[-1] ** (periods_per_year / len(r)) - 1.0
    sharpe = (np.nan if not np.isfinite(deviation) or deviation < 1e-15
              else (r.mean() - risk_free_rate) / deviation * np.sqrt(periods_per_year))

    return pd.Series({
        "Annualized Return": annual_return,
        "Annualized Volatility": deviation * np.sqrt(periods_per_year),
        "Sharpe Ratio": sharpe,
        "Maximum Drawdown": (wealth / wealth.cummax() - 1.0).min(),
    })


# =====================================
# 7. ROLLING PORTFOLIO CONSTRUCTION
# =====================================


def build_portfolios(expected: pd.DataFrame, actual: pd.DataFrame,
                     covariance: dict[pd.Timestamp, np.ndarray] | pd.DataFrame, *,
                     risk_aversion: float = RISK_AVERSION,
                     max_weight: float | None = MAX_WEIGHT,
                     eligibility: pd.DataFrame | None = None,
                     market_caps: pd.DataFrame | None = None,
                     origin_risk_free: pd.Series | float = 0.0):
    assets = sorted(set(expected.columns) & set(actual.columns))
    if len(assets) < 20:
        raise ValueError(f"at least 20 risky assets are required, got {len(assets)}")

    expected = expected[assets]
    actual = actual[assets]

    # Pre-index DataFrame covariance once for O(1) lookup per origin.
    cov_panel: dict[pd.Timestamp, np.ndarray] | pd.DataFrame = covariance
    panel_assets: list[str] | None = assets
    if isinstance(covariance, pd.DataFrame):
        grouped = {}
        for origin, block in covariance.groupby("Date", sort=False):
            matrix = block.pivot_table(
                index="Asset_1", columns="Asset_2", values="Covariance", aggfunc="first"
            ).reindex(index=assets, columns=assets).to_numpy(dtype=float)
            grouped[origin] = matrix
        cov_panel = grouped

    weight_records, return_records, forecast_records = [], [], []

    for date, mu in expected.iterrows():
        try:
            active = assets
            if eligibility is not None:
                eligible = eligibility.loc[date, assets]
                active = eligible.index[eligible].tolist()
            if not active or (max_weight is not None and len(active) * max_weight < 1 - 1e-12):
                raise ValueError(f"weight constraints are infeasible for {len(active)} eligible assets")
            mu = mu[active]
            sigma = covariance_at(cov_panel, date, active, panel_assets=panel_assets)
            prior_weights = None
            if market_caps is not None:
                caps = market_caps.loc[date, active].to_numpy(dtype=float)
                if not np.isfinite(caps).all() or (caps <= 0).any():
                    raise ValueError("eligible assets must have observed positive market caps")
                prior_weights = caps / caps.sum()
            rf = origin_risk_free.loc[date] if isinstance(origin_risk_free, pd.Series) else origin_risk_free
            bl_mu = black_litterman(mu, sigma, risk_aversion=risk_aversion,
                                    market_weights=prior_weights, risk_free=rf)

            portfolios = {
                "Mean-Variance Optimization":
                    optimize_portfolio(mu, sigma, "Mean-Variance",
                                       risk_aversion=risk_aversion, max_weight=max_weight),
                "Global Minimum Variance":
                    optimize_portfolio(mu, sigma, "GMV", max_weight=max_weight),
                "Maximum Diversification":
                    optimize_portfolio(mu, sigma, "Maximum Diversification",
                                       max_weight=max_weight),
                "Risk Parity":
                    optimize_portfolio(mu, sigma, "Risk Parity", max_weight=max_weight),
                "Black-Litterman":
                    optimize_portfolio(bl_mu, sigma, "Mean-Variance",
                                       risk_aversion=risk_aversion, max_weight=max_weight),
            }

            for model, weights in portfolios.items():
                model_mu = bl_mu if model == "Black-Litterman" else mu
                forecast_records.append({
                    "Date": date,
                    "Model": model,
                    "Expected_Return": float(weights @ np.asarray(model_mu, dtype=float)),
                    "Expected_Volatility": float(np.sqrt(weights @ sigma @ weights)),
                })
                full_weights = pd.Series(weights, index=active).reindex(assets, fill_value=0)
                for asset, weight in full_weights.items():
                    weight_records.append({
                        "Date": date, "Model": model, "Asset": asset, "Weight": float(weight),
                    })

            future_dates = actual.index[actual.index > date]
            if len(future_dates) == 0:
                continue

            next_date = future_dates[0]
            realised = actual.loc[next_date]
            if realised.isna().any():
                continue

            for model, weights in portfolios.items():
                return_records.append({
                    "Date": next_date,
                    "Model": model,
                    "Portfolio_Return": float(weights @ realised[active].to_numpy(dtype=float)),
                })

        except (ValueError, FileNotFoundError, np.linalg.LinAlgError) as error:
            raise ValueError(f"{date.date()}: {error}") from error

    weights_df = pd.DataFrame(weight_records, columns=["Date", "Model", "Asset", "Weight"])
    returns_df = pd.DataFrame(return_records, columns=["Date", "Model", "Portfolio_Return"])
    forecasts_df = pd.DataFrame(
        forecast_records,
        columns=["Date", "Model", "Expected_Return", "Expected_Volatility"],
    )

    if returns_df.empty:
        raise ValueError("no realised portfolio returns were generated")

    return weights_df, returns_df, forecasts_df


def write_outputs(output_dir: Path, weights_df: pd.DataFrame,
                  returns_df: pd.DataFrame, forecasts_df: pd.DataFrame) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {
        "weights": output_dir / "Portfolio_Weights.csv",
        "oos_returns": output_dir / "OOS_Portfolio_Returns.csv",
        "forecast_metrics": output_dir / "Forecast_Portfolio_Metrics.csv",
    }
    weights_df.to_csv(written["weights"], index=False)
    returns_df.to_csv(written["oos_returns"], index=False)
    forecasts_df.to_csv(written["forecast_metrics"], index=False)
    return written


def run_part3(
    expected_path: Path,
    covariance_path: Path,
    actual_path: Path,
    output_dir: Path,
    *,
    risk_aversion: float = RISK_AVERSION,
    max_weight: float | None = MAX_WEIGHT,
    tradability_data: Path | None = None,
    market_caps_path: Path | None = None,
    risk_free_path: Path | None = None,
    covariance_panel: dict[pd.Timestamp, np.ndarray] | None = None,
    eligibility: pd.DataFrame | None = None,
    market_caps: pd.DataFrame | None = None,
    origin_risk_free: pd.Series | float | None = None,
) -> dict[str, Path]:
    """In-process entry point that preserves the exact Part 3 CSV output contract."""
    expected = load_panel(expected_path, "expected returns")
    actual = load_panel(actual_path, "actual returns")
    assets = sorted(set(expected.columns) & set(actual.columns))
    covariance = (
        covariance_panel
        if covariance_panel is not None
        else load_covariance(covariance_path, assets=assets)
    )
    if eligibility is None and tradability_data is not None:
        eligibility = load_eligibility(tradability_data, expected.index, assets)
    if market_caps is None and market_caps_path is not None:
        market_caps = monthly_panel(pd.read_pickle(market_caps_path), expected.index, assets)
    if origin_risk_free is None:
        origin_risk_free = monthly_risk_free(risk_free_path, expected.index)
        if risk_free_path is not None and not isinstance(origin_risk_free, pd.Series):
            raise ValueError("valid daily risk-free data is required when risk_free_path is specified")

    weights_df, returns_df, forecasts_df = build_portfolios(
        expected, actual, covariance,
        risk_aversion=risk_aversion,
        max_weight=max_weight,
        eligibility=eligibility,
        market_caps=market_caps,
        origin_risk_free=origin_risk_free,
    )
    written = write_outputs(output_dir, weights_df, returns_df, forecasts_df)
    if eligibility is not None:
        dropped = len(assets) - eligibility.sum(axis=1)
        diag_path = Path(output_dir) / "Tradability_Diagnostics.csv"
        dropped.rename("Excluded_Assets").rename_axis("Date").to_csv(diag_path)
        written["tradability"] = diag_path
    return written


# =====================================
# 8. COMMAND LINE
# =====================================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Part 3 portfolio construction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--expected", type=Path, default=default_expected_returns(),
                        help="expected returns panel; defaults to the current Part 1 main forecast")
    parser.add_argument("--covariance", type=Path, default=default_covariance(),
                        help="long format covariance panel")
    parser.add_argument("--actual", type=Path, default=default_actual_returns(),
                        help="realised returns panel")
    parser.add_argument("--tradability-data", type=Path,
                        help="directory for vendor flags; defaults to data/ for the main forecast")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir(),
                        help="where the CSVs are written")
    parser.add_argument("--risk-aversion", type=float, default=RISK_AVERSION,
                        help="risk aversion in the mean-variance objective")
    parser.add_argument("--risk-free-data", type=Path,
                        help="daily risk_free.csv to convert Black–Litterman total views to excess views")
    parser.add_argument("--market-caps", type=Path,
                        help="monthly mcap.pkl for a capitalization-weighted Black–Litterman prior")
    parser.add_argument("--max-weight", type=float, default=MAX_WEIGHT,
                        help="optional upper bound on any single weight")
    parser.add_argument("--periods-per-year", type=int, default=PERIODS_PER_YEAR,
                        help="annualisation factor for the console summary")
    parser.add_argument("--risk-free-rate", type=float, default=RISK_FREE_RATE,
                        help="per-period risk-free rate for the console summary")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        expected = load_panel(arguments.expected, "expected returns")
        actual = load_panel(arguments.actual, "actual returns")
        assets = sorted(set(expected.columns) & set(actual.columns))
        covariance = load_covariance(arguments.covariance, assets=assets)
    except (FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"expected returns: {arguments.expected}")
    print(f"covariance:       {arguments.covariance}")
    print(f"actual returns:   {arguments.actual}")

    try:
        data_dir = arguments.tradability_data
        if data_dir is None and arguments.expected.resolve() == default_expected_returns():
            data_dir = PROJECT / "data"
        eligibility = None
        if data_dir is not None:
            eligibility = load_eligibility(data_dir, expected.index, assets)
            dropped = len(assets) - eligibility.sum(axis=1)
            print(f"excluded assets per origin: min={dropped.min()} max={dropped.max()}")
        market_caps = (monthly_panel(pd.read_pickle(arguments.market_caps), expected.index, assets)
                       if arguments.market_caps is not None else None)
        origin_risk_free = monthly_risk_free(arguments.risk_free_data, expected.index)
        if arguments.risk_free_data is not None and not isinstance(origin_risk_free, pd.Series):
            raise ValueError("valid daily risk-free data is required when --risk-free-data is specified")
        weights_df, returns_df, forecasts_df = build_portfolios(
            expected, actual, covariance,
            risk_aversion=arguments.risk_aversion,
            max_weight=arguments.max_weight,
            eligibility=eligibility, market_caps=market_caps, origin_risk_free=origin_risk_free,
        )
    except (ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    months = weights_df["Date"].nunique()
    print(f"\nPortfolio construction completed: {months} rebalancing months, "
          f"{len(assets)} assets, {len(MODELS)} methods")

    summary = pd.DataFrame({
        model: performance_summary(
            group["Portfolio_Return"],
            periods_per_year=arguments.periods_per_year,
            risk_free_rate=arguments.risk_free_rate,
        )
        for model, group in returns_df.groupby("Model")
    }).T
    print("\nUncosted summary (sanity check; formal metrics live in Part 4):")
    print(summary.round(4).to_string())

    written = write_outputs(arguments.output_dir, weights_df, returns_df, forecasts_df)
    if eligibility is not None:
        dropped.rename("Excluded_Assets").rename_axis("Date").to_csv(
            arguments.output_dir / "Tradability_Diagnostics.csv"
        )
    print("\nResults saved in:", arguments.output_dir)
    for label, path in written.items():
        print(f"  {label}: {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
