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
#slide-title[One stock pool for the main portfolio experiment]
#grid(columns: (1fr, 1fr, 1fr), gutter: 25pt,
  [*Form the return signal* #linebreak() Penultimate trading close. Train on 72 completed labels and score the fixed pool.],
  [*Update risk and rebalance* #linebreak() At the month-end close, update risk from data realized by that close and target eligible names.],
  [*Measure the next month* #linebreak() Carry frozen positions and charge trading fees before booking subsequent total returns.],
)
#v(22pt)
The original FM selected the 50 names on December 30, 2014. The first portfolio
formed at the next close. All main portfolio comparisons use the same roster and calendar.

#v(13pt)
#small[Five long-only, fully invested allocations. Eligible 1/N shares their execution and cost model.]

#pagebreak()
// Saved Part 1 notebook tables, January 2015–August 2024.
// The stock portfolios use the top-25 equal-weight rule and 20 basis points per side.
#let part-one-results = (
  main: (
    ("Fama–MacBeth top 25 (net)", "12.08%", "35.79%", "−49.81%"),
    ("Fixed-pool equal weight (net)", "7.54%", "33.76%", "−49.97%"),
    ("CSI 500 price index", "−1.41%", "24.46%", "−58.18%"),
    ("Fama–French five-factor market proxy", "2.02%", "20.18%", "−40.49%"),
  ),
  tree: (
    ("Fama–MacBeth pool", "Fama–MacBeth", "15.699%", "0.1288", "12.08%", "−49.81%"),
    ("Fama–MacBeth pool", "Regression trees", "15.672%", "0.1247", "15.34%", "−47.42%"),
    ("Regression tree pool", "Fama–MacBeth", "15.851%", "0.1461", "11.71%", "−49.64%"),
    ("Regression tree pool", "Regression trees", "15.832%", "0.1419", "12.36%", "−48.96%"),
  ),
)
#let method-heading(body) = text(21pt, fill: navy, weight: "bold", body)
#slide-title[Return models and out-of-sample design]
#text(19pt, grid(columns: (1fr, 1fr), gutter: 40pt, align: top,
  [
    #method-heading[Factor screening]

    Both models screen 11 candidates using 72 months of realized training labels. They measure monthly Spearman rank correlations with next-month returns, requiring at least 100 stock pairs per month and 48 valid months.

    Six-month block resampling and the Benjamini–Yekutieli correction give adjusted $q$-values. The models retain factors with $q <= 0.10$.

    #method-heading[Six factors passed at the initial selection]

    - Prior month-end market capitalization
    - Average trading value over 21 days
    - Eight-week momentum
    - Return from the prior month-end to the signal day
    - Five-day return
    - Residual volatility net of three principal components
  ],
  [
    #method-heading[Model fitting]

    Fama–MacBeth averages coefficients from 72 monthly cross-sectional ridge regressions. The tree model fits gradient-boosted regression trees with a maximum depth of 3 over 60 rounds.

    #method-heading[Stock selection]

    On December 30, 2014, each model ranked 2,178 eligible A-shares and locked its own top 50. The two pools shared 13 stocks. The first rebalance took place at the next close.

    #method-heading[Out-of-sample evaluation]

    From January 2015 to August 2024 (116 months), the models refit monthly and retained 5 to 9 factors. They scored stocks at the penultimate trading close and rebalanced at month-end. Forecast comparisons use the same stock-months within each pool. The top 25 stocks each target a 4% weight, with fees of 0.20% per side.
  ],
))

#pagebreak()
#slide-title[Fama–MacBeth results on its fixed stock pool]
#small[Part 1 notebook · January 2015–August 2024 · 116 months]
#v(19pt)
#text(20pt, grid-table(
  ("Portfolio or market reference", "Compound annual growth rate", "Annualized volatility", "Maximum drawdown"),
  (1.75fr, 1.1fr, .92fr, .87fr),
  part-one-results.main,
))
#v(20pt)
*Forecast accuracy.* On matched stock-months, Fama–MacBeth had a mean rank information coefficient of 0.1288 and a root mean square error of 15.70%. Individual-stock historical means gave −0.0427 and 15.99%. Out-of-sample $R^2$ against that forecast baseline was 3.67%.

#v(10pt)
#small[Both stock portfolios are net of 0.20% per side. The market proxy adds the risk-free return to the Fama–French market premium.]

#v(13pt)
#small[The main mean–variance portfolio experiment retained Fama–MacBeth. With six lagged accounting fields, the gain in mean rank information coefficient was #num(selection.ic_gain, digits: 4) (95% interval #num(selection.ic_gain_ci95.at(0), digits: 4) to #num(selection.ic_gain_ci95.at(1), digits: 4)). The portfolio Sharpe ratio fell from #score(selection.fm_mvo_sharpe) to #score(selection.extended_mvo_sharpe).]

#pagebreak()
#slide-title[Regression tree results on both fixed pools]
#small[Part 1 notebook · January 2015–August 2024 · 116 months]
#v(19pt)
#text(18pt, table(
  columns: (1.3fr, 1.17fr, 1.06fr, 1.2fr, 1.2fr, .96fr),
  align: (x, y) => if x < 2 { left + horizon } else if y == 0 { center } else { right + horizon },
  inset: (x: 8pt, y: 8pt),
  fill: (x, y) => if y < 2 { rgb("#e7f0f3") } else if calc.odd(y) { rgb("#f5f8fa") },
  stroke: (x: none, y: .45pt + rgb("#d6e0e6")),
  table.header(
    table.cell(rowspan: 2)[*Fixed stock pool*],
    table.cell(rowspan: 2)[*Forecast model*],
    table.cell(colspan: 2)[*Forecast quality*],
    table.cell(colspan: 2)[*Top-25 equal-weight portfolio*],
    [*Root mean #linebreak() square error*],
    [*Mean rank information coefficient*],
    [*Net compound annual growth rate*],
    [*Maximum drawdown*],
  ),
  ..part-one-results.tree.flatten(),
))
#v(20pt)
- On each pool, the trees had slightly lower forecast error and Fama–MacBeth had a higher mean rank information coefficient. The paired 95% intervals for the error improvement included zero.
- Using each model's own pool, the tree minus Fama–MacBeth mean monthly net return was −0.03 percentage points. The paired 95% interval was −0.51 to +0.41 percentage points.
#v(7pt)
#small[Equal-weight benchmarks returned 7.54% (Fama–MacBeth pool) and 7.34% (tree pool) per year, net of 0.20% per side.]

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
