import numpy as np
import pandas as pd
from scipy.optimize import minimize
import os
import warnings

# =====================================
# 1. SETTINGS
# =====================================

P1_FILE = "P1_Expected_Returns.csv"
P2_FILE = "P2_Covariance.csv"
ACTUAL_FILE = "Actual_Returns.csv"

OUTPUT_DIR = "Part3_Results"

PERIODS_PER_YEAR = 12
RISK_AVERSION = 5.0
MAX_WEIGHT = None
RISK_FREE_RATE = 0.0

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================
# 2. LOAD DATA
# =====================================

def load_returns(file):
    df = pd.read_csv(file)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date").sort_index().astype(float)


expected_returns = load_returns(P1_FILE)
actual_returns = load_returns(ACTUAL_FILE)

covariance_data = pd.read_csv(P2_FILE)
covariance_data["Date"] = pd.to_datetime(covariance_data["Date"])
covariance_data["Asset_1"] = covariance_data["Asset_1"].astype(str).str.strip()
covariance_data["Asset_2"] = covariance_data["Asset_2"].astype(str).str.strip()

assets = sorted(set(expected_returns.columns) & set(actual_returns.columns))

if len(assets) < 20:
    raise ValueError("At least 20 risky assets are required.")

expected_returns = expected_returns[assets]
actual_returns = actual_returns[assets]

print("Number of assets:", len(assets))


# =====================================
# 3. COVARIANCE MATRIX
# =====================================

def get_covariance_matrix(date):
    df = covariance_data[covariance_data["Date"] == date]

    sigma = df.pivot_table(
        index="Asset_1",
        columns="Asset_2",
        values="Covariance"
    ).reindex(index=assets, columns=assets).values

    if np.isnan(sigma).any():
        raise ValueError(f"Missing covariance at {date}")

    sigma = (sigma + sigma.T) / 2

    eigenvalues, eigenvectors = np.linalg.eigh(sigma)
    sigma = eigenvectors @ np.diag(np.maximum(eigenvalues, 1e-10)) @ eigenvectors.T

    return sigma


# =====================================
# 4. PORTFOLIO OPTIMIZATION
# =====================================

def optimize_portfolio(mu, sigma, method):

    n = len(mu)
    mu = np.asarray(mu)
    upper = MAX_WEIGHT if MAX_WEIGHT is not None else 1.0

    individual_vol = np.sqrt(np.diag(sigma))

    def objective(w):
        variance = w @ sigma @ w

        if method == "Mean-Variance":
            return -w @ mu + 0.5 * RISK_AVERSION * variance

        if method == "GMV":
            return variance

        if method == "Maximum Diversification":
            return -(w @ individual_vol) / np.sqrt(max(variance, 1e-12))

        if method == "Risk Parity":
            rc = w * (sigma @ w) / max(variance, 1e-12)
            return np.sum((rc - 1/n) ** 2)

        raise ValueError("Unknown method")

    result = minimize(
        objective,
        np.ones(n) / n,
        method="SLSQP",
        bounds=[(0, upper)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"maxiter": 2000, "ftol": 1e-12}
    )

    if not result.success:
        raise ValueError(result.message)

    weights = np.maximum(result.x, 0)
    return weights / weights.sum()


# =====================================
# 5. BLACK-LITTERMAN
# =====================================

def black_litterman(mu, sigma):

    n = len(mu)
    market_weights = np.ones(n) / n

    prior = RISK_AVERSION * sigma @ market_weights

    tau = 0.05
    P = np.eye(n)
    Q = np.asarray(mu)

    omega = np.diag(np.diag(tau * sigma) / 0.5)

    middle = P @ (tau * sigma) @ P.T + omega

    posterior = prior + tau * sigma @ P.T @ np.linalg.solve(
        middle, Q - P @ prior
    )

    return posterior


# =====================================
# 6. PERFORMANCE METRICS
# =====================================

def performance_metrics(returns):

    r = pd.Series(returns).dropna()

    wealth = (1 + r).cumprod()

    annual_return = wealth.iloc[-1] ** (PERIODS_PER_YEAR / len(r)) - 1
    annual_vol = r.std() * np.sqrt(PERIODS_PER_YEAR)

    sharpe = (
        (r.mean() - RISK_FREE_RATE) / r.std()
        * np.sqrt(PERIODS_PER_YEAR)
        if r.std() > 0 else np.nan
    )

    max_drawdown = (wealth / wealth.cummax() - 1).min()

    return {
        "Annualized Return": annual_return,
        "Annualized Volatility": annual_vol,
        "Sharpe Ratio": sharpe,
        "Maximum Drawdown": max_drawdown
    }


# =====================================
# 7. ROLLING PORTFOLIO CONSTRUCTION
# =====================================

weight_records = []
return_records = []
forecast_records = []

for date, mu in expected_returns.iterrows():

    try:
        sigma = get_covariance_matrix(date)

        bl_mu = black_litterman(mu, sigma)

        # Five portfolio methods
        portfolios = {
            "Mean-Variance Optimization":
                optimize_portfolio(mu, sigma, "Mean-Variance"),

            "Global Minimum Variance":
                optimize_portfolio(mu, sigma, "GMV"),

            "Maximum Diversification":
                optimize_portfolio(mu, sigma, "Maximum Diversification"),

            "Risk Parity":
                optimize_portfolio(mu, sigma, "Risk Parity"),

            "Black-Litterman":
                optimize_portfolio(bl_mu, sigma, "Mean-Variance")
        }

        # Save weights and forecast metrics
        for model, weights in portfolios.items():

            model_mu = bl_mu if model == "Black-Litterman" else mu

            forecast_records.append({
                "Date": date,
                "Model": model,
                "Expected_Return": weights @ np.asarray(model_mu),
                "Expected_Volatility": np.sqrt(weights @ sigma @ weights)
            })

            for asset, weight in zip(assets, weights):
                weight_records.append({
                    "Date": date,
                    "Model": model,
                    "Asset": asset,
                    "Weight": weight
                })

        # Next-period actual returns
        future_dates = actual_returns.index[actual_returns.index > date]

        if len(future_dates) == 0:
            continue

        next_date = future_dates[0]
        realized = actual_returns.loc[next_date]

        if realized.isna().any():
            continue

        for model, weights in portfolios.items():
            return_records.append({
                "Date": next_date,
                "Model": model,
                "Portfolio_Return": weights @ realized.values
            })

    except (ValueError, np.linalg.LinAlgError) as e:
        warnings.warn(f"{date}: {e}")
        continue


weights_df = pd.DataFrame(weight_records)
returns_df = pd.DataFrame(return_records)
forecasts_df = pd.DataFrame(forecast_records)

if returns_df.empty:
    raise ValueError("No realized portfolio returns were generated.")

print("\nPortfolio construction completed.")
print("Methods:", returns_df["Model"].nunique())


# =====================================
# 8. PERFORMANCE COMPARISON
# =====================================

performance_df = pd.DataFrame({
    model: performance_metrics(
        returns_df.loc[
            returns_df["Model"] == model,
            "Portfolio_Return"
        ]
    )
    for model in returns_df["Model"].unique()
}).T

print("\nPerformance Comparison:")
print(performance_df.round(4))


# =====================================
# 9. EXPORT RESULTS
# =====================================

weights_df.to_csv(f"{OUTPUT_DIR}/Portfolio_Weights.csv", index=False)
returns_df.to_csv(f"{OUTPUT_DIR}/OOS_Portfolio_Returns.csv", index=False)
forecasts_df.to_csv(f"{OUTPUT_DIR}/Forecast_Portfolio_Metrics.csv", index=False)
performance_df.to_csv(f"{OUTPUT_DIR}/Performance_Summary.csv")

print(f"\nResults saved in: {OUTPUT_DIR}")
