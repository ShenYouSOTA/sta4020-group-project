# Engineering plan

English | [简体中文](PLAN.zh-CN.md)

Status: the interim pipeline has run on the course data with 50 assets and 116 monthly out-of-sample returns.

## 1. Deadline map

| Milestone | Date | Weight | What it needs |
| --- | --- | --- | --- |
| Interim discussion | Nov 23 - Nov 27 | 20% | One baseline result per part, a working end-to-end run, and a plan for the final model. The group must book the slot itself; no booking means zero. |
| Presentation slides | Dec 13, 23:59:59 | 40% | Final models, OOS results versus 1/N, the interpretation and the critique. |
| Final report + code + data | Dec 18, 23:59:59 | 40% | Written chapters per part, reproducible code, and the data needed to re-run it. Late submissions are not accepted. |

The interim discussion is two days away.  The purpose of the harness in this
repository is that the group walks in with a number for every part, produced by
the same code path that will produce the final numbers.

## 2. Where the project stands

### Data (complete)

| File | Content | Shape / range |
| --- | --- | --- |
| data/monthly_returns.pkl | Monthly simple total returns, wide | 355 x 5378, 1995-02 .. 2024-08 |
| data/price.h5 | Daily adjusted prices plus trading calendar | 324 MB, needs h5py |
| data/mcap.pkl | Month-end market cap, wide | 356 x 5634 |
| data/daily_amount.pkl | Daily traded value | 186 MB |
| data/BLACKLIST.pkl, data/UNTRADABLE.pkl | Per-day exclusion flags | daily |
| data/FF5.csv | Fama-French five factors | 357 rows to 2024-09 |
| data/risk_free.csv | Daily risk-free rate | 7223 rows |
| data/zz500.pk | CSI 500 daily bars | 4346 x 7 |
| data/addition/descriptors.zip | 213 monthly descriptors (value, quality, momentum, volatility, liquidity, leverage, analyst); see [the assessment](ADDITION_DATA_ASSESSMENT.md) | 6128 assets, 1999-12 .. 2026-08, 2.59 GiB unpacked |

There is no industry classification anywhere in the data.  This matters for
Part 2 (see risk R2).

### Part 1 - return model (artifacts delivered)

- Universe: 50 assets fixed at the selection date, listed in
  artifacts/part1/P1_Candidate_Universe.csv. OOS starts 2014-12-31, the first
  target month is 2015-01-31.
- artifacts/part1/P1_Expected_Returns.csv: 116 origins x 50 assets, values are
  the forecast of the next calendar month's simple return.
- artifacts/part1/Actual_Returns.csv: 116 realised months, 2015-01-31 ..
  2024-08-31.
- The current FM forecast (P1_Expected_Returns.csv) is the default. The legacy
  validation panel is historical and must not be paired with the new universe.
  The [Part 1 guide](../part1_return_model/README.md) describes the main and tree notebooks.
  Rebuild Part 2 covariance and Part 3 weights against the updated fixed pool.
- Verified today by `uv run sta4020-check-artifacts`: 0 contract issues, 116 origins
  map one-to-one onto realised months.

### Part 2 - risk model

- Sample, Ledoit–Wolf and eight-style factor models each produce 116 covariance blocks of 50 × 50. All factor blocks are positive definite and reproducible from the source archive.
- The factor model uses an expanding history from 2013-01. It regresses monthly excess returns on the preceding month's exposures and uses sample factor covariance and specific variance estimates. A single industry group is used because the data lack labels. Starting at the May 2023 close, the active cross-section omits the delisted asset. Its last pre-delisting specific variance is retained in the artifact.

### Part 3 - portfolio construction

- All five methods have run on the course data. Month-end vendor flags exclude 0 to 9 assets per origin. The delisted asset has zero weight from the May 2023 close. The 10% weight cap run is in `artifacts/part3/interim-10pct/`.
- The simulation treats target weights as executable at the close, including immediate removal of previously held names that become ineligible. Execution during suspensions remains to be modelled.

### Part 4 - evaluation

- The main interim evaluation is in `part4_evaluation/reports/interim-10pct/REPORT.md`, with a 10% single-asset weight cap and 10 bp one-way cost. Uncapped factor, sample and Ledoit–Wolf runs use `interim`, `sample-risk` and `ledoit-wolf` respectively.
- Strategies, 1/N and attribution use the same eligible assets. Trading costs use drifted holdings available at the rebalance close.

## 3. Artifact contract

Everything crosses a part boundary as a CSV in long or wide form with an
explicit Date column.  Units are monthly decimal simple returns, never
annualised, never percentages.  All dates are calendar month-ends taken from
the realised-return file; an origin at month-end t is scored against the first
month-end strictly after t.

| File | Producer | Consumer | Schema |
| --- | --- | --- | --- |
| artifacts/part1/P1_Expected_Returns.csv | Part 1 | Part 3 | Wide. Date, then one column per asset code. Value = expected simple return of the next month. |
| artifacts/part1/Actual_Returns.csv | Part 1 | Part 3, Part 4 | Wide, identical columns. Date = the month being realised. |
| artifacts/part1/P1_Candidate_Universe.csv | Part 1 | all | The master asset list. Any part that needs to know "the 50 assets" reads this file. |
| artifacts/part2/P2_Covariance.csv | Part 2 | Part 3 | Long: Date, Asset_1, Asset_2, Covariance. One complete N x N block per origin. Symmetric, positive diagonal, no NaN, monthly units. |
| artifacts/part3/Portfolio_Weights.csv | Part 3 | Part 4 | Long: Date, Model, Asset, Weight. Long only, weights sum to one per (Date, Model). |
| artifacts/part3/OOS_Portfolio_Returns.csv | Part 3 | Part 4 | Date, Model, Portfolio_Return. Reconciliation only; Part 4 recomputes the return from the weights. |

Rules that have already caused friction, so they are explicit here:

1. The universe is the intersection of the three files, and it must contain at
   least 20 assets.  Part 4 rejects anything smaller.
2. Asset codes are the vendor codes, exactly as they appear in
   P1_Candidate_Universe.csv, with no suffix changes and no reordering
   assumptions.
3. No file may contain an annualised covariance or an annualised return
   forecast.  Everything is one month.
4. A missing month is an error, not a zero.  Part 4 raises instead of filling.
5. Do not silently change the meaning of an existing file.  Add a new file and
   a note in this table.

`uv run sta4020-check-artifacts` (src/sta4020_project/checks.py) enforces the
mechanical parts of this contract and
should be run before any integration commit.

## 4. Work breakdown

### Part 1 - return model

Already delivered: universe selection, 116 monthly forecasts, realised panel.
Remaining work is explanation, not code:

- Document the model ladder (historical mean, factor model with IC-based factor
  selection, machine learning) and which one is cited in the report.
- Check the selection step for look-ahead: the candidate universe is chosen at
  2014-12-31 and must use information available before that date only.

### Part 2 - risk model

- The panel adapter is running with monthly excess returns from data/monthly_returns.pkl
  and data/risk_free.csv for the 50 assets in the candidate universe; market
  caps from data/mcap.pkl; style exposures from data/addition/descriptors.zip.
  The rules are in [the descriptor assessment](ADDITION_DATA_ASSESSMENT.md) §4.1.
- Eight styles: size, value, momentum, short-term reversal, residual
  volatility, liquidity, quality, leverage.  Value and quality now come from
  the descriptors instead of being dropped.
- Estimation window, implementation A (decided 2026-11-22): a balanced
  50-asset panel from 2013-01 with an expanding window, because the youngest
  assets list in 2012 and the first origin may only use data up to
  2014-12-31.  The first origin therefore sees 24 months.  Implementation B
  (factor returns estimated on a broad cross-section from 2005) is the
  upgrade for the final report.
- 300330.SZ delists in 2023: keep it in the covariance (N = 50), carry its
  market cap and styles forward, and do not let its zero returns shrink its
  own specific variance.
- Industry: no classification exists in the data.  Implementation A uses a
  single industry group, leaving the market intercept.
- Implementation A uses the package factor fit and covariance assembly.
  All 116 blocks in artifacts/part2/P2_Covariance.csv are positive definite.
- Calibration and comparison: sample covariance, Ledoit-Wolf shrinkage and the
  Barra-style factor model on the same window; report realised out-of-sample
  volatility of the covariance estimates as the objective criterion.

### Part 3 - portfolio construction

- Inputs are wired (done): artifacts/part1 and artifacts/part2 by default,
  overridable per flag, so `uv run python part3_portfolio/Part3.py` is the one
  command.  The real covariance hand-off has been verified.
- Add the constraints the report will claim: MAX_WEIGHT cap (for example 5% or
  10%), optional turnover penalty, and a documented choice of RISK_AVERSION.
  The flags exist; the values still have to be chosen and justified.
- Produce at least one sensitivity run: risk aversion 2, 5, 10 and a
  Black-Litterman variant with a different tau or a market-cap prior instead of
  1/N.
- Applied the tradability masks in data/BLACKLIST.pkl and data/UNTRADABLE.pkl
  before optimising, and record how many names were dropped each month.
  300330.SZ must have zero weight from 2023-05 (delisted; see R10).
- Do not report the metrics computed inside Part3.py as final results.

### Part 4 - evaluation (this repository part)

Implemented: contract validation, the four required metrics plus Sortino,
Calmar, hit rate and turnover, the 1/N benchmark on the identical calendar and
cost model, Memmel's Sharpe difference test, Jensen alpha with a Newey-West
t-statistic, an exact gap = signal + timing attribution, subperiod tables,
weight diagnostics, three figures and a markdown report.

Remaining work, in order:

1. The first real runs are complete. The main interim evaluation is in reports/interim-10pct/.
2. Cost sensitivity: the machinery is already wired (--cost-sweep writes
   tables/cost_sensitivity.csv and two pivot tables into REPORT.md at 0, 10, 30
   and 50 bp one-way).  The real tables are available. The write-up still needs to address
   whether the ranking changes across cost levels.  This
   is the strongest single piece of practical critique available.
3. Subperiod narrative: 2015 crash, 2018 de-risking, 2021-2022 drawdown,
   2023-2024.  For each, name the Part 1-3 modelling choice that explains the
   result.
4. Attribution write-up: which share of the gap is signal and which is timing.
   A strategy that "wins" through timing only is a finding, not a success.
5. Weight diagnostics: effective number of holdings, maximum weight, turnover.
   Concentrated weights are the expected symptom of an ill-conditioned
   covariance matrix, which is exactly the Part 2 comparison the report needs.
6. Optional extensions if time allows: deflated Sharpe ratio across the five
   strategies, and a reality-check bootstrap for the best strategy.

### Dependency order

data -> Part 1 artifacts -> Part 2 covariance -> Part 3 weights -> Part 4 report

## 5. Risks

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| R1 | A has a short early history and B has a wider capitalization reference. | Covariance bias can vary with the regime and reference. | Compare both with sample and Ledoit–Wolf on the same calendar. |
| R2 | No industry classification in the data. | The Barra-style model loses its industry block; the comparison to the literature weakens. | Decide the proxy explicitly, report it as a limitation, and lean on the style-factor-only specification. |
| R3 | The smoke-test fixture has 24 months. | Any quoted number would be wrong and below the 60-month requirement. | Treated as a fixture. The report only quotes reports/ generated from artifacts/part1 and artifacts/part2. |
| R4 | Universe drift between parts (50 in Part 1, 20 in the mock, N in Part 2). | Silent mismatched assets, wrong weights. | P1_Candidate_Universe.csv is the master list; check_artifacts.py enforces the intersection rule. |
| R5 | Look-ahead in the Part 1 selection or in the covariance window. | Invalidates the whole OOS claim. | Review the notebooks' window boundaries; the covariance at origin t may only use data up to t. |
| R6 | Untradable names entering the weights. | Unrealistic performance. | Apply BLACKLIST/UNTRADABLE masks in Part 3; Part 4 reports turnover and the cost drag so the effect is visible. |
| R7 | Cost assumption is optimistic. | Overstated performance. | Report the 0-50 bp sensitivity and state the assumption in the slides. |
| R8 | Interim discussion is in two days. | 20% of the grade. | Present the harness and the mock run as the integration proof, plus one real number per part where available; be explicit about what is real and what is a fixture. |
| R9 | Reproducibility. | Code marks. | One interpreter, pinned requirements, tests, one command per part, no manual notebook steps in the deliverable path. |
| R10 | 300330.SZ delists in 2023 but stays in the fixed universe with zero returns. | A zero-return asset looks riskless, so minimum-variance style optimisers pile into it. | Zero weight from 2023-05 in Part 3 and in the 1/N benchmark; Part 2 keeps its last pre-delisting specific variance. |
| R11 | Short early history for Part 2 (implementation A) and undocumented vendor restatements in the descriptors. | Noisy early covariances; possible back-filled fundamentals. | State both as limitations; implementation B lengthens the factor-return history. |

## 6. Integration workflow

- Branches: part1/, part2/, part3/, part4/ ; pull requests into main.
- Every pull request that touches artifacts/ must show the output of
  `uv run sta4020-check-artifacts`.
- Freeze result sets by tag: part4_evaluation/reports/<tag>/ with the config
  block written into REPORT.md, so a quoted number can always be traced back to
  the exact inputs and cost assumption.
- Every command in this document is run from the repository root, and every
  path is relative to it: no absolute paths, no per-machine setup, no
  particular user.  The only prerequisite is uv: `uv sync` builds .venv from
  the committed uv.lock, `uv run sta4020-check-data` verifies the raw data
  (which is not in git, see data/README.md).
- Run the locked final pipeline with a new tag. The manifest records each Part command.

~~~bash
uv run sta4020-check-data
uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline
~~~

## 7. Decision log

| Date | Decision | Why |
| --- | --- | --- |
| 2026-11-21 | group-project is its own git repository, not a folder in the STA4020 course repository. | The four parts belong to four people; sharing one course repository would expose unrelated coursework and mix commit history. |
| 2026-11-21 | Part 2's repository is vendored into part2_risk_model/ (nested .git removed), not a submodule. | A submodule ships as an empty directory in the graded zip, and a nested repository is silently skipped by the outer one. Provenance is recorded in part2_risk_model/PROVENANCE.md. |
| 2026-11-21 | The legacy validated forecast was initially the default. | Superseded by the revised FM forecast and fixed universe; see the Part 1 section. |
| 2026-11-21 | Transaction cost is a parameter, reported at 0, 10, 30 and 50 bp one-way. | 10 bp is a plausible base case for a liquid A-share book, but it is not defensible as the only number; the sensitivity table shows where the ranking flips. |
| 2026-11-21 | Report numbers come from part4_evaluation/reports/ only. | Part3.py's own metrics ignore costs, the 1/N benchmark and any statistical test, so they cannot appear as results. |
| 2026-11-22 | Part 2 styles come from data/addition/descriptors.zip; estimation uses implementation A (50 assets, from 2013-01, expanding window) for the interim, B for the final. | A needs no changes to the package and runs before the interim; B fixes the short early history. |
| 2026-11-22 | Part 1 may only add descriptors lagged by one month, at most 15 pre-registered candidates. | The Part 1 signal is formed before the last trading day, when the month's descriptor is not yet known; screening all 213 fields would overfit. |

## 8. Definition of done

- All four artifacts exist and pass the checker, with 50 assets and at least
  60 OOS months.
- Every strategy's four required metrics appear in one table against 1/N.
- At least one formal test per strategy against 1/N, and a stated conclusion
  that separates statistical significance from economic size.
- A cost sensitivity table and a subperiod table.
- The Part 4 chapter answers "why did this model win or lose" by pointing at a
  specific choice in Parts 1-3, not at the realised numbers alone.
- The repository reproduces every reported number from a clean checkout plus
  the data directory.
