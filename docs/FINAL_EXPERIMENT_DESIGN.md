# Final experiment design

Freeze the Part 1 extension before fitting. Add six accounting candidates to the
existing eleven: book-to-market (`book_value_to_total_mktcap_mrq`), earnings
yield (`net_profit_to_total_mktcap_ttm`), return on invested capital
(`return_on_invested_capital_ttm`), gross profitability
(`gross_profit_to_asset_ttm`), accruals (`accrual_to_asset_ttm`), and leverage
(`total_liab_to_total_asset_mrq`). All enter with a one-calendar-month lag.
Use the existing broad eligible cross-section, rank scoring, coverage filters,
BY selection and 72-month FM ridge. Compare with the eleven-candidate model and
a trailing 72-month asset mean ending in the month before the origin. Keep the
original 50-stock pool for all runs.

Promote the extension only if its paired monthly Rank IC gain has a positive
six-month block-bootstrap 95% interval, its mean IC gain is positive in the
months at or above median broad descriptor coverage (including ties), and its net mean-variance Sharpe at 10 bp is
at least the existing FM Sharpe. Break ties in favor of the original FM.

For Part 2 B select up to 800 largest positive-cap names with observed
formation-month styles after composite aggregation. Select by formation-month
data, then use observable next-month returns for the realized WLS fit. Use
the broad sample's normalization to map the fixed-pool styles into the same
factor coordinates. Forecast with expanding sample factor covariance and
expanding fixed-pool residual variances. Compare all four covariance methods
with identical portfolio settings (risk aversion 5, 10% target cap and a
uniform Black–Litterman prior). Black–Litterman converts total views to excess
returns using the most recent observed monthly risk-free return. Use the common equal-weight target to assess
variance forecasts across methods, alongside realized strategy volatility.

The primary final runs use B. Report the annualized volatility of gross realized
returns alongside predicted volatility, with a Mincer–Zarnowitz regression and
a calibration error test. Portfolio sensitivities vary risk aversion (2, 5,
10), the Black–Litterman prior (uniform or market capitalization), and costs.

Execution at the monthly close freezes prior holdings flagged by UNTRADABLE.
A tradable blacklisted asset may be sold but has no target purchases. The cash
budget charges 10 bp on both buy and sell notionals and proportions the remaining
budget across eligible targets. This applies to both strategies and 1/N.
For the fixed delisting convention, liquidate 300330.SZ at the May 2023 origin
using vendor marks as the exit proxy and take no exposure thereafter. Keep
the old immediate target execution as a sensitivity under the same per-side
cost convention. The 10% bound applies to optimized target weights.
