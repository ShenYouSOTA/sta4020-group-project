#import "final_tables.typ": *

#set document(title: "Forecasting and allocating across 50 A-shares", author: "STA4020 project group")
#set page(width: 16in, height: 9in, margin: (x: 0.75in, top: 0.5in, bottom: 0.58in),
  footer: context align(right, text(13pt, fill: rgb("#526471"))[STA4020 · #counter(page).display("1")]))
#set text(font: "Liberation Sans", size: 22pt, fill: rgb("#162e3a"), lang: "en")
#set par(leading: 0.68em, spacing: 0.8em)
#let navy = rgb("#17465a")
#let slide-title(body) = block(above: 0pt, below: 26pt,
  text(36pt, fill: navy, weight: "bold", body))
#let small(body) = text(17pt, fill: rgb("#526471"), body)
#let perf = model-row(mvo)
#let ew = model-row(benchmark)
#let compare = records("versus_benchmark")
#let gap = find(records("return_attribution"), "model", mvo)

#small[STA4020 · FINAL PROJECT · FALL 2026]
#v(0.76in)
#text(49pt, weight: "bold", fill: navy)[Forecasting and allocating #linebreak() across 50 A-shares]
#v(0.22in)
Monthly rebalancing from January 2015 to August 2024

#v(0.53in)
#grid(columns: (1fr, 1fr, 1fr), gutter: 22pt,
  [*#manifest.months* #linebreak() #small[Realized months]],
  [*#pct(perf.at("Annualized return"))* #linebreak() #small[Mean–variance net CAGR]],
  [*#pct(ew.at("Annualized return"))* #linebreak() #small[Eligible 1/N net CAGR]],
)

#pagebreak()
#slide-title[One stock pool across all experiments]
#grid(columns: (1fr, 1fr, 1fr), gutter: 25pt,
  [*Form the return signal* #linebreak() Penultimate trading close. Train on 72 completed labels and score the fixed pool.],
  [*Update risk and rebalance* #linebreak() At the month-end close, update risk from data realized by that close and target eligible names.],
  [*Measure the next month* #linebreak() Carry frozen positions and charge trading fees before booking subsequent total returns.],
)
#v(22pt)
The original FM selected the 50 names on December 30, 2014. The first portfolio
formed at the next close. All comparisons use the same roster and calendar.

#v(13pt)
#small[Five long-only, fully invested allocations. Eligible 1/N shares their execution and cost model.]

#pagebreak()
#slide-title[The original FM remains the final forecast]
#grid-table(("Forecast", "Rank IC", "ICIR", "High coverage IC", "MVO CAGR", "MVO vol.", "Sharpe", "Drawdown"),
  (1.3fr, .78fr, .7fr, 1fr, .87fr, .85fr, .8fr, .85fr), return-rows)
#v(18pt)
- FM uses monthly Rank IC screening, BY correction and averaged ridge coefficients.
- Six added accounting fields enter one calendar month late and use the same broad training universe.
- The extension's paired mean IC gain was #num(selection.ic_gain, digits: 4), with a 95% interval of
  [#num(selection.ic_gain_ci95.at(0), digits: 4), #num(selection.ic_gain_ci95.at(1), digits: 4)].
  MVO Sharpe declined from #score(selection.fm_mvo_sharpe) to #score(selection.extended_mvo_sharpe).

#pagebreak()
#slide-title[Model B extends factor history]
#grid-table(("Risk model", "Pred. 1/N vol.", "Gross 1/N vol.", "QLIKE", "MZ joint p", "Bias p", "Q(6) p"),
  (1.15fr, 1.15fr, 1.15fr, .85fr, .9fr, .8fr, .8fr), risk-rows)
#v(19pt)
- Model B used 800 names per monthly factor regression. The first forecast used 119 realized factor months versus 23 for A.
- B was positive definite at every origin. Sample covariance had 27 rank-deficient months.
- B had lower QLIKE than A. Ledoit–Wolf was closest on 1/N volatility and had the highest MVO Sharpe among these risk inputs.

#pagebreak()
#slide-title[Allocation depends on risk aversion and execution]
#let alloc = records("portfolio_sensitivity")
#let find-allocation(name, aversion, prior) = alloc.find(row =>
  row.model == name and int(row.aversion) == aversion and row.prior == prior)
#let sensitivity = (2, 5, 10).map(a => (
  str(a),
  score(find-allocation(mvo, a, "Uniform").at("Sharpe ratio")),
  score(find-allocation(bl, a, "Uniform").at("Sharpe ratio")),
  score(find-allocation(bl, a, "Market cap").at("Sharpe ratio")),
))
#grid-table(("Risk aversion", "MVO Sharpe", "BL uniform Sharpe", "BL market-cap Sharpe"),
  (1fr, 1fr, 1.2fr, 1.35fr), sensitivity)
#v(19pt)
- Targets hold at most 10% per name. Frozen holdings can drift above the cap.
- Fees use actual buy and sell notionals. The cash budget covers every fee before the next month's return.
- 300330.SZ exits at the May 2023 origin under a marked liquidation assumption.

#pagebreak()
#slide-title[Mean–variance led on net return and Sharpe]
#grid(columns: (1fr, 1.14fr), gutter: 30pt, align: horizon,
  text(19pt, grid-table(("Strategy", "CAGR", "Vol.", "Sharpe", "Max DD"),
    (2.15fr, 1fr, .95fr, 1.1fr, 1.05fr), performance-rows)),
  image(final-dir + "figures/wealth.png", width: 100%),
)
#v(18pt)
#small[CAGR and wealth include 10 bp per side. Volatility, Sharpe and maximum drawdown are from monthly net returns.]
#v(13pt)
The Memmel Sharpe test against 1/N gave $p = #score(find(compare, "", mvo).at("p-value"))$.
The annual arithmetic active return interval was #pp(gap.annual_net_gap_ci_low)
to #pp(gap.annual_net_gap_ci_high) using a paired block bootstrap.

#pagebreak()
#slide-title[Forecast tilts helped and execution ate into the gain]
#let risk-split = find(records("risk_decomposition"), "model", mvo)
#grid(columns: (1fr, 1fr), gutter: 33pt,
 [*Return attribution* #linebreak() MVO's forecast tilt contributed #pp(gap.signal_annualized) per year.
  Forecast errors contributed #pp(gap.timing_annualized). Additional trading cost
  reduced the active mean by #pp(gap.incremental_cost_drag).],
 [*Risk attribution* #linebreak() Common factors account for #pct(risk-split.factor_variance_share) of predicted MVO variance.
  Negative liquidity and residual-volatility loadings had the largest positive fitted contributions.],
)
#v(27pt)
The 2021–2022 MVO advantage reversed in 2023 through August 2024. At 50 bp per
side, the Sharpe advantage over 1/N was small.
#v(10pt)
#small[The variance and realized style decompositions use the same executed weights as the performance evaluation.]

#pagebreak()
#slide-title[What the evidence supports]
- The original FM was a better ranking signal than trailing historical means.
- Model B supports style attribution, while simpler covariances yielded higher FM portfolio Sharpe.
- MVO led on net Sharpe, though benchmark tests and cost sensitivity show limited persistence.

#v(14pt)
#small[Fixed 50-stock pool; undocumented vendor restatement history; close-price execution assumptions.]
#v(17pt)
#grid-table(("Part", "Section", "Primary member and contribution"),
  (.7fr, 1.28fr, 2fr), team)
