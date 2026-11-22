#import "final_tables.typ": *

#set document(title: "Forecasting and allocating across 50 A-shares", author: "STA4020 project group")
#set page("a4", margin: (x: 19mm, top: 16mm, bottom: 19mm),
  footer: context align(right, text(9pt, fill: rgb("#526471"))[STA4020 · #counter(page).display("1")]))
#set text(font: "Libertinus Serif", size: 11pt, fill: rgb("#172a35"), lang: "en")
#set par(leading: 0.63em, spacing: 0.82em, justify: true)
#show heading: set text(font: "Liberation Sans", fill: rgb("#17465a"))
#let label(body) = text(font: "Liberation Sans", size: 9pt, fill: rgb("#17465a"), weight: "bold", body)
#let note(body) = text(size: 9.5pt, fill: rgb("#526471"), body)
#let fig(name) = image(final-dir + "figures/" + name + ".png", width: 94%)
#let perf = model-row(mvo)
#let ew = model-row(benchmark)
#let against = records("versus_benchmark")
#let mvo-test = find(against, "", mvo)
#let headline-gap = stat(perf, "Annualized return") - stat(ew, "Annualized return")

#label[STA4020 · STATISTICAL MODELING IN FINANCIAL MARKETS · FALL 2026]
#v(13pt)
#text(26pt, weight: "bold")[Forecasting and allocating #linebreak() across 50 A-shares]
#v(5pt)
#text(13pt, fill: rgb("#526471"))[Monthly out-of-sample evidence, January 2015 to August 2024]
#v(16pt)

Mean–variance optimization achieved a net compound annual return of
*#pct(perf.at("Annualized return"))*, with a Sharpe ratio of *#score(perf.at("Sharpe ratio"))*.
The eligible 1/N benchmark earned #pct(ew.at("Annualized return")) with a Sharpe
ratio of #score(ew.at("Sharpe ratio")). The #pp(headline-gap) compound return
advantage came with higher volatility. The paired Sharpe test gave
$p = #score(mvo-test.at("p-value"))$, and the block-bootstrap interval for net
active returns spans zero. The backtest supports a return-ranking signal with
limited evidence of a persistent portfolio performance advantage.

#v(8pt)
#grid-table(("Strategy", "Net ann. return", "Ann. volatility", "Sharpe", "Max drawdown"),
  (2.2fr, 1fr, 1fr, .8fr, 1fr), performance-rows)
#note[All metrics use the same #manifest.months monthly outcomes and #manifest.assets
stock identifiers. Net returns include 10 bp per side. Sharpe ratios use
monthly compounded risk-free returns. Drawdowns use cumulative net wealth.]

== Study design

The original FM model selected the universe on December 30, 2014, using
labels through November 2014. The first simulated rebalance took place at
the December 31 close. Every later month used that same roster. The month-end
forecast and weight files join to the next calendar month's total returns.
Monthly rebalancing, long-only fully invested targets and the shared
month-end restrictions apply throughout. All five strategies target a 10%
single-name cap. The 1/N benchmark targets equal weights among eligible stocks.

== Primary responsibilities

#grid-table(("Part", "Section", "Primary member and contribution"),
  (.65fr, 1.45fr, 2.4fr), team)
#note[Member names and individual contributions require confirmation by the group.]

#pagebreak()
= 1. Forecasting expected returns

At the penultimate trading close of each month, the original FM fits a 72-month
rolling window of mature next-month labels. For a December signal, the most
recent feature row used in fitting is October and its label is November.
The broad eligible Shanghai and Shenzhen sample supplies 11 price, market-cap,
liquidity, momentum, volatility and PCA-based candidates. We screen each
candidate by Spearman Rank IC with six-month block resampling, at least 100
stock pairs per month and at least 48 measured months. Benjamini–Yekutieli
adjusted $q <= 0.10$ determines which features enter the current model.

Within each training month, the model standardizes mid-ranks and fills
missing scores at the center, winsorizes target returns at 1% and 99%, then
fits a ridge regression with penalty 0.10 on the slopes. We average monthly
coefficients and score the current fixed pool. When a stock lacks a fresh
signal, its export receives the common historical forecast. The headless build
reproduces the original notebook's exported forecasts to within $10^(-9)$.

== A lagged accounting extension

We preregistered book-to-market, earnings yield, return on invested capital,
gross profitability, accruals and leverage. Each is taken from the previous
calendar month, before the current signal close, and uses the same scoring
and missing-value rules. All six candidate fields had at least 99.99% mean
coverage on the eligible broad cross-sections in the first fitting window. The reference is each asset's mean from the last
72 completed months before the origin. Both FM fits retain the original
50-stock roster. IC uses the same fresh and execution-eligible stocks for
all three forecasts, with at least #selection.minimum_matched_assets observations
per month. ICIR is the mean monthly IC divided by its sample standard deviation.

#grid-table(("Forecast", "Rank IC", "ICIR", "High coverage IC", "MVO return", "MVO vol.", "Sharpe", "Drawdown"),
  (1.15fr, .72fr, .65fr, .9fr, .9fr, .85fr, .7fr, .85fr), return-rows)

The accounting extension raised mean IC by #num(selection.ic_gain, digits: 4).
Its paired 95% block-bootstrap interval was
[#num(selection.ic_gain_ci95.at(0), digits: 4), #num(selection.ic_gain_ci95.at(1), digits: 4)].
The gain was #num(selection.high_coverage_ic_gain, digits: 4) in the
#selection.high_coverage_months months at or above median broad descriptor coverage
with ties included. The extended model also reduced MVO Sharpe from
#score(selection.fm_mvo_sharpe) to #score(selection.extended_mvo_sharpe).
The adoption rule required a positive interval, a positive high-coverage
gain and at least the original Sharpe. We retained the 11-candidate forecast.
In the higher-coverage realization years
#selection.high_coverage_years.map(str).join(", "), the conditional MVO Sharpe
was #score(records("high_coverage_portfolios").find(row => row.forecast == "fm" and row.model == mvo).sharpe_ratio)
for FM and #score(records("high_coverage_portfolios").find(row => row.forecast == "extended" and row.model == mvo).sharpe_ratio)
for the extension. The sensitivity retains each strategy's original path.
The negative IC of historical means helps explain their weaker use as a
cross-sectional allocation signal. The reused evaluation period supports a
controlled comparison and model selection. Independent forward performance
remains untested.

#pagebreak()
= 2. Estimating risk across the fixed roster

== Four monthly covariance estimates

Sample and Ledoit–Wolf use expanding returns from January 2013. Ledoit–Wolf
shrinks toward a scaled identity. Factor model A fits monthly realized excess
returns using the preceding month's characteristics on the fixed stock pool.
Its earliest factor history contains 23 realized months. Model B estimates
market and eight style factor returns from February 2005. Its first covariance
uses 119 realized months through December 2014, with expanding fixed-pool
specific risk starting from January 2013. Both models use constrained WLS
weighted by square-root market cap and use the monthly compounded daily
risk-free series. Industry is represented by a single market group and the
industry coefficient is constrained to zero.

In each B formation month, we cap descriptor outliers at five scaled median
absolute deviations and average available standardized components for composite
styles. The eight styles represent size, value, momentum, reversal, residual
volatility, liquidity, quality and leverage. Size and turnover are logged.
Short momentum and accruals are sign reversed in the reversal and quality
styles. From Shanghai and Shenzhen
stocks with positive capitalization and all eight styles, B selects the
largest 800 using formation-month information. Formation exposures are
centered by cap weights and scaled by sample standard deviation in that group.
The next month's realized returns determine which selected names enter the
fit. The normalization and the 50-stock exposure mapping are fixed before
those returns are observed. For missing fixed-roster styles, B uses the
formation sample's median. The factor covariance grows with completed factor
returns. The fixed-pool specific variance grows with the residuals from the
prior month's exposures and the realized factor return. We assemble
$Sigma_t = X_t F_t X_t^T + "diag"(s_t^2)$.

The departing stock 300330.SZ keeps its place in the matrix. From the May
2023 origin onward its standalone variance is frozen at the pre-delisting
estimate, and its cross-covariances are zero. Its executed portfolio weights
are zero from that origin. All 235 broad fits used 800 names. B was positive
definite at 116 origins. Its largest top-five eigenvalue share was 69.7% of
the trace. The largest median absolute pairwise style correlation was 0.36
and the maximum monthly VIF was 3.36.

== Forecast calibration on the identical executed 1/N path

#grid-table(("Risk model", "Pred. vol.", "Gross vol.", "QLIKE", "MZ joint p", "Bias p", "Q(6) p"),
  (1.2fr, .9fr, .9fr, .8fr, .8fr, .75fr, .75fr), risk-rows)
#note[Predicted volatility is the square root of 12 times mean forecast variance.
Realized volatility is the annualized sample volatility of gross returns.
QLIKE is mean log variance plus the ratio of squared realized excess return
to forecast variance. Lower is better. MZ tests intercept zero and slope one
with HAC errors. The bias p-value uses a HAC test of mean normalized error.
Q(6) is a six-lag Ljung–Box diagnostic.]

B improves QLIKE relative to A, while plain sample covariance scores
slightly better on 1/N. Ledoit–Wolf's average risk level is closest to
the realized 1/N volatility. Normalized errors are serially dependent under
all four models. With identical FM forecasts, MVO Sharpe was 0.528 for
sample, 0.537 for Ledoit–Wolf, 0.465 for A and 0.408 for B. B's longer history
supports a style decomposition, with no observed allocation gain over the
simpler estimates.

#pagebreak()
= 3. Constructing and executing portfolios

The five objectives are mean–variance utility, minimum variance, maximum
diversification ratio, equal variance contributions and Black–Litterman
posterior mean–variance utility. SLSQP solves each month's long-only,
fully invested problem on eligible stocks from a uniform feasible start.
The maximum diversification and risk parity implementations use numerical
local optimization. The risk matrix is symmetrized and any eigenvalues below
$10^(-10)$ are floored for optimization. Risk aversion $lambda = 5$ is the
main monthly mean–variance setting. It maximizes
$w^T mu - (lambda / 2) w^T Sigma w$ in monthly units.

Black–Litterman takes equilibrium excess returns $lambda Sigma w_M$ from a
uniform eligible prior in the main result. The alternative uses that month's
market capitalization among the same eligible names. Absolute views use the
FM forecasts with the implementation's fixed confidence setting
($tau = 0.05$, diagonal view uncertainty $2 tau "diag"(Sigma)$).
For a fully invested mean–variance objective, the risk-free level cancels as
a common shift. In the Black–Litterman update the view is converted to excess
return with the last observed monthly risk-free rate so the view and prior
have the same units.

== Execution and turnover

Universe restrictions use the vendor's month-end BLACKLIST and UNTRADABLE
flags. A tradable blacklisted asset receives a zero target. A blocked asset
with existing holdings retains its pre-trade number of shares. Trades scale
the eligible target weights to the available cash after freezing holdings.
Fees are paid from that cash budget at 10 bp per side on the actual total
buy and sell notional, including initial purchases. Reported turnover counts
both sides. The subsequent monthly
return drifts the holdings before the next rebalance. Strategies, 1/N and
attribution use the same post-trade weights and monthly return alignment.

The 10% bound applies at optimization. A position that drifts while
untradable can temporarily exceed it. The exit for 300330.SZ at the May 2023
origin uses the vendor mark as a liquidation proxy. It is the main execution
exception. Month-end marks and flags also abstract from intraday availability,
direction-specific limit rules, spreads and market impact. Same-close
valuation and rebalancing assume an executable close and enough time to
incorporate the end-of-day inputs.

#let execution = records("execution")
#let allocation = records("portfolio_sensitivity")
#let alloc-rows = (2, 5, 10).map(aversion => {
  let uniform = allocation.find(row => row.model == bl and row.prior == "Uniform" and int(row.aversion) == aversion)
  let cap = allocation.find(row => row.model == bl and row.prior == "Market cap" and int(row.aversion) == aversion)
  let mv = allocation.find(row => row.model == mvo and row.prior == "Uniform" and int(row.aversion) == aversion)
  (str(aversion), score(mv.at("Sharpe ratio")), score(uniform.at("Sharpe ratio")),
   score(cap.at("Sharpe ratio")), pct(mv.at("Annualized return")))
})
#grid-table(("Risk aversion", "MVO Sharpe", "BL uniform", "BL cap", "MVO net return"),
  (1fr, 1fr, 1fr, 1fr, 1.15fr), alloc-rows)

#pagebreak()
= 4. Evaluating the portfolio results

#align(center, fig("wealth"))
#note[Growth of one unit of initial wealth, after 10 bp per-side costs. Source
data are the monthly net returns in the final output.]

== Benchmark tests and active returns

#let gaps = records("return_attribution")
#let sig = models.slice(0, 5).map(model => {
  let row = find(against, "", model)
  let gap = find(gaps, "model", model)
  (names.at(model), pp(row.at("Excess annualized return")), score(row.at("p-value")),
   score(row.at("Alpha t-statistic")), pp(gap.annual_net_gap_ci_low) + " to " + pp(gap.annual_net_gap_ci_high))
})
#grid-table(("Strategy", "CAGR gap", "Sharpe p", "HAC alpha t", "Net active mean 95% CI"),
  (1.65fr, .8fr, .8fr, .95fr, 1.65fr), sig)

CAGR gaps compare net compound returns. Confidence intervals apply to
annualized arithmetic net active returns from a paired six-month circular
block bootstrap. The Memmel test compares monthly excess-return Sharpe ratios
and the alpha regression uses excess returns with Newey–West errors. These are
individual tests across five strategies. Maximum diversification's low
unadjusted Sharpe p-value should be read in that context. The largest point
estimate belongs to MVO. Its signal and volatility exposures, the amount of
trading needed to maintain them, and their sample dependence matter more than
the performance ranking alone.

#pagebreak()
= 5. Why results differ

#let mv-gap = find(gaps, "model", mvo)
#let decomposition = records("risk_decomposition")
#let mv-risk = find(decomposition, "model", mvo)
#let mv-exec = find(execution, "Model", mvo)
#let costs = records("cost_sensitivity")
#let cost-rows = ("0.0", "10.0", "30.0", "50.0").map(cost => {
  let mv = costs.find(row => row.cost_bps == cost and row.Model == mvo)
  let base = costs.find(row => row.cost_bps == cost and row.Model == benchmark)
  (cost, pct(mv.annualized_return), pct(base.annualized_return),
   score(mv.sharpe_ratio), score(base.sharpe_ratio))
})

*Signal, risk and construction.* MVO earned a gross active arithmetic
return of #pp(mv-gap.gross_gap) per year. The weights' forecast tilt
contributed #pp(mv-gap.signal_annualized) and the forecast error contribution was
#pp(mv-gap.timing_annualized). Trading reduced the net active mean by
#pp(mv-gap.incremental_cost_drag). Factor risk accounts for
#pct(mv-risk.factor_variance_share) of MVO's mean forecast variance. The factor
and specific volatility components were #pct(mv-risk.factor_vol) and
#pct(mv-risk.specific_vol). They add in variance units. Maximum
diversification disregards expected returns in the objective. Its forecast
tilts were negative and its realized gross active mean was
#pp(find(gaps, "model", maxdiv).gross_gap). Risk parity tracked the benchmark
closely, with annual tracking error of #pct(find(against, "", rp).at("Tracking error")).

*Trading constraints.* MVO carried frozen holdings in
#mv-exec.MonthsWithFrozenHoldings months, with a maximum combined frozen
weight of #pct(mv-exec.MaxFrozenWeight). The biggest executed weight was
#pct(mv-exec.MaxExecutedWeight). All targets passed the 10% cap check. The
immediate-exit control uses the identical target paths and per-side fees.
Comparing that control to the main run isolates the effect of freezing under
this execution model. MVO net annual return was
#pct(records("execution_sensitivity").find(row => row.execution == "Immediate" and row.model == mvo).at("Annualized return"))
under immediate execution and #pct(perf.at("Annualized return")) with freezing.
At 50 bp, the Sharpe advantage is small and MVO has a deeper drawdown than 1/N.

#grid-table(("Cost per side (bp)", "MVO net return", "1/N net return", "MVO Sharpe", "1/N Sharpe"),
  (1.25fr, 1fr, 1fr, .85fr, .85fr), cost-rows)

*Style exposures and sample dependence.* The MVO active-return
regression gives an annual contribution of 3.7 pp for liquidity and 3.0 pp
for residual volatility. Both loadings are negative and both factor means
are negative. The intercept contributes −5.7 pp. These are descriptive
loadings on the realized factors. MVO gained 13.5 pp of annualized return
over 1/N in 2021–2022 and lost 8.6 pp in 2023 through August 2024. The 2015
surge came from the preselected stock pool and lifted both series. The
cost and subperiod tables quantify how much of the full-sample ranking
depends on these choices.

== Reproduction and limitations

The locked pipeline reproduces the results from the trusted course inputs.
Input SHA-256 hashes, the calendar, commands and selected model are recorded
in the final manifest. The single market industry limits sector attribution.
Vendor book values and reported profits changed much more frequently in
April, August and October, consistent with announcement timing. A one-month
lag respects the recorded release months. The handling of later restatements
remains undocumented.
A uses a short factor history, while B uses a larger capitalization-weighted
reference group that may represent risk imperfectly in the fixed pool.
The results describe the 2015–2024 holdout and its execution assumptions.
