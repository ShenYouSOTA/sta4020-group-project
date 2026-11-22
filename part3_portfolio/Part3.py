#!/usr/bin/env python3
"""Part 3 - portfolio construction.

Reads the expected returns and the covariance panel that Parts 1 and 2 deliver,
builds five portfolios per rebalancing month, and writes the weights that Part 4
evaluates out of sample.

Paths
-----
Every input is an explicit path, with the artifact contract of this repository
as the default.  Nothing is read from the working directory, so the script
behaves the same no matter where it is started from.  Override any default on
the command line:

    python part3_portfolio/Part3.py
    python part3_portfolio/Part3.py \
        --expected artifacts/sample/P1_Expected_Returns.csv \
        --covariance artifacts/sample/P2_Covariance.csv \
        --actual artifacts/sample/Actual_Returns.csv \
        --output-dir /tmp/part3

Outputs (written to --output-dir, default artifacts/part3):

    Portfolio_Weights.csv          Date,Model,Asset,Weight   <- Part 4 consumes this
    OOS_Portfolio_Returns.csv      Date,Model,Portfolio_Return (own bookkeeping)
    Forecast_Portfolio_Metrics.csv Date,Model,Expected_Return,Expected_Volatility

Performance metrics are deliberately not written here.  They ignore transaction
costs and never compare against the 1/N benchmark, so the reference numbers live
in the Part 4 report (see docs/PLAN.md, section 3).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from sta4020_project.cli import monthly_risk_free
from sta4020_project.risk import monthly_panel
from sta4020_project.tradability import load_eligibility

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
    """Use the current Part 1 main forecast, as Part 4 does."""
    return PROJECT / "artifacts" / "part1" / "P1_Expected_Returns.csv"


def default_covariance() -> Path:
    return PROJECT / "artifacts" / "part2" / "P2_Covariance.csv"


def default_actual_returns() -> Path:
    return PROJECT / "artifacts" / "part1" / "Actual_Returns.csv"


def default_output_dir() -> Path:
    return PROJECT / "artifacts" / "part3"


# =====================================
# 2. LOAD DATA
# =====================================


def load_panel(path: Path, label: str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        raise ValueError(f"{label} has no Date column: {path}")
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame.set_index("Date").sort_index().astype(float)


def load_covariance(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"covariance panel not found: {path}")
    frame = pd.read_csv(path)
    required = {"Date", "Asset_1", "Asset_2", "Covariance"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"covariance panel is missing columns {sorted(missing)}: {path}")
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["Asset_1"] = frame["Asset_1"].astype(str).str.strip()
    frame["Asset_2"] = frame["Asset_2"].astype(str).str.strip()
    frame["Covariance"] = pd.to_numeric(frame["Covariance"], errors="raise")
    return frame


# =====================================
# 3. COVARIANCE MATRIX
# =====================================


def covariance_at(covariance: pd.DataFrame, date, assets: list[str]) -> np.ndarray:
    """Rebuild the N x N matrix for one origin date, symmetric and PSD-floored."""
    frame = covariance[covariance["Date"] == date]
    if frame.empty:
        raise ValueError(f"no covariance rows for {date}")

    sigma = frame.pivot_table(
        index="Asset_1", columns="Asset_2", values="Covariance", aggfunc="first"
    ).reindex(index=assets, columns=assets).to_numpy(dtype=float)

    if np.isnan(sigma).any():
        missing = [asset for asset in assets if np.isnan(sigma[assets.index(asset)]).any()]
        raise ValueError(f"incomplete covariance matrix at {date} for {missing[:5]}")

    if not np.allclose(sigma, sigma.T, rtol=0.0, atol=1e-12):
        sigma = (sigma + sigma.T) / 2

    eigenvalues, eigenvectors = np.linalg.eigh(sigma)
    if (eigenvalues < -1e-8).any():
        warnings.warn(f"{date}: covariance has a negative eigenvalue "
                      f"{eigenvalues.min():.3e}; flooring it")
    sigma = eigenvectors @ np.diag(np.maximum(eigenvalues, 1e-10)) @ eigenvectors.T
    return sigma


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
                     covariance: pd.DataFrame, *,
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
            sigma = covariance_at(covariance, date, active)
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
        covariance = load_covariance(arguments.covariance)
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
            assets = sorted(set(expected.columns) & set(actual.columns))
            eligibility = load_eligibility(data_dir, expected.index, assets)
            dropped = len(assets) - eligibility.sum(axis=1)
            print(f"excluded assets per origin: min={dropped.min()} max={dropped.max()}")
        market_caps = (monthly_panel(pd.read_pickle(arguments.market_caps), expected.index, expected.columns)
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

    assets = sorted(weights_df["Asset"].unique())
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
    print("\nUncosted summary (for sanity only; the reference numbers are in the "
          "Part 4 report):")
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
