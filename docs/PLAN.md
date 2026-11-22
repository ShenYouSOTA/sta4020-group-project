# Engineering Plan

English | [简体中文](PLAN.zh-CN.md)

Status: interim and final pipelines run on 50 assets across 116 monthly out-of-sample returns.

## 1. Deadlines

| Milestone | Date | Weight | Deliverables |
| --- | --- | --- | --- |
| Interim discussion | Nov 23 – Nov 27 | 20% | Baseline per part, end-to-end run, final model plan (group must book slot). |
| Presentation slides | Dec 13, 23:59:59 | 40% | Final models, OOS results vs 1/N, interpretation, critique. |
| Final report + code + data | Dec 18, 23:59:59 | 40% | Written chapters, reproducible code, required data. |

The repository harness runs all four parts through the same code path used for the final numbers.

## 2. Current Status

### Data (complete)

| File | Content | Shape / range |
| --- | --- | --- |
| `data/monthly_returns.pkl` | Monthly simple total returns, wide | 355 x 5378, 1995-02 .. 2024-08 |
| `data/price.h5` | Daily adjusted prices and calendar | 324 MB, needs `h5py` |
| `data/mcap.pkl` | Month-end market cap, wide | 356 x 5634 |
| `data/daily_amount.pkl` | Daily traded value | 186 MB |
| `data/BLACKLIST.pkl`, `data/UNTRADABLE.pkl` | Daily exclusion flags | daily |
| `data/FF5.csv` | Fama–French five factors | 357 rows to 2024-09 |
| `data/risk_free.csv` | Daily risk-free rate | 7223 rows |
| `data/zz500.pk` | CSI 500 daily bars | 4346 x 7 |
| `data/addition/descriptors.zip` | 213 monthly descriptors; see [assessment](ADDITION_DATA_ASSESSMENT.md) | 6128 assets, 1999-12 .. 2026-08, 2.59 GiB unpacked |

Industry classification is absent across all datasets (see risk R2).

### Part 1 - Return model

- Universe: 50 fixed assets selected at 2014-12-30 (`artifacts/part1/P1_Candidate_Universe.csv`); OOS starts 2014-12-31, first target month 2015-01-31.
- `artifacts/part1/P1_Expected_Returns.csv`: 116 origins x 50 assets (next-month simple return forecasts from the FM model).
- `artifacts/part1/Actual_Returns.csv`: 116 realized months, 2015-01-31 .. 2024-08-31.
- See [Part 1 guide](../part1_return_model/README.md) for FM and tree notebooks; `uv run sta4020-check-artifacts` confirms 0 contract errors.

### Part 2 - Risk model

- Sample, Ledoit–Wolf, and eight-style factor models produce 116 positive-definite 50 x 50 covariance blocks.
- Factor model A uses an expanding history from 2013-01 on the 50-asset pool; Model B estimates factor returns on the top 800 liquid stocks from 2005-02. Both use a single market industry group.
- From the May 2023 close, active estimation omits delisted `300330.SZ`, retaining its pre-delisting specific variance.

### Part 3 - Portfolio construction

- All five methods run across the 116-month calendar, excluding 0 to 9 assets per origin via month-end vendor flags (`300330.SZ` has zero weight from May 2023).
- Interim 10% cap run is in `artifacts/part3/interim-10pct/`.

### Part 4 - Evaluation

- Main interim evaluation is in `part4_evaluation/reports/interim-10pct/REPORT.md` (10% cap, 10 bp one-way cost); uncapped/covariance comparisons use tags `interim`, `sample-risk`, and `ledoit-wolf`.
- Strategies, 1/N, and attribution share identical eligible universes and drifted-holdings cost accounting.

## 3. Artifact Contract

Parts exchange long or wide CSVs with an explicit `Date` column in monthly decimal simple return units. Calendar month-end dates align to `Actual_Returns.csv`; an origin at month-end `t` is scored against the first month-end strictly after `t`.

| File | Producer | Consumer | Schema |
| --- | --- | --- | --- |
| `artifacts/part1/P1_Expected_Returns.csv` | Part 1 | Part 3 | Wide: `Date` + asset columns (next-month expected simple return). |
| `artifacts/part1/Actual_Returns.csv` | Part 1 | Part 3, Part 4 | Wide, identical columns; `Date` = realization month-end. |
| `artifacts/part1/P1_Candidate_Universe.csv` | Part 1 | all | Master 50-asset roster. |
| `artifacts/part2/P2_Covariance.csv` | Part 2 | Part 3 | Long: `Date`, `Asset_1`, `Asset_2`, `Covariance`. Complete `N x N` symmetric PD block per origin, monthly units. |
| `artifacts/part3/Portfolio_Weights.csv` | Part 3 | Part 4 | Long: `Date`, `Model`, `Asset`, `Weight`. Long-only, sum to 1 per `(Date, Model)`. |
| `artifacts/part3/OOS_Portfolio_Returns.csv` | Part 3 | Part 4 | `Date`, `Model`, `Portfolio_Return` (reconciliation only; Part 4 recomputes from weights). |

Contract rules:

1. Universe = intersection of the three core files (minimum 20 assets).
2. Asset codes match `P1_Candidate_Universe.csv` verbatim.
3. All return forecasts and covariances are one-month decimal units.
4. Missing months raise errors rather than filling zeros.
5. Add new files for new semantics rather than altering existing file meanings.

Verify with `uv run sta4020-check-artifacts` before integration commits.

## 4. Work Breakdown

### Part 1 - Return model

- Document the model ladder (historical mean, IC + FM ridge, tree) and verify pre-2014-12-31 look-ahead isolation in universe selection.

### Part 2 - Risk model

- Panel adapter pulls excess returns (`monthly_returns.pkl`, `risk_free.csv`), market caps (`mcap.pkl`), and eight styles (`descriptors.zip`, see [assessment](ADDITION_DATA_ASSESSMENT.md) §4.1): size, value, momentum, short-term reversal, residual volatility, liquidity, quality, leverage.
- Implementation A uses an expanding 50-asset balanced panel from 2013-01 (24 months at first origin); Implementation B estimates factor returns on a broad cross-section from 2005.
- Delisted `300330.SZ` retains `N = 50` with carried-forward market cap/styles and frozen pre-delisting specific variance.
- Compare sample, Ledoit–Wolf, and factor models on identical windows using realized OOS volatility and QLIKE.

### Part 3 - Portfolio construction

- Run via `uv run python part3_portfolio/Part3.py` with configurable `--max-weight` (e.g. 0.10), turnover penalty, and risk aversion.
- Run sensitivities across risk aversion (2, 5, 10) and Black–Litterman priors (`1/N` vs market-cap).
- Apply `BLACKLIST.pkl` and `UNTRADABLE.pkl` masks; keep `300330.SZ` at zero weight from 2023-05.
- Report formal metrics only from Part 4.

### Part 4 - Evaluation

Implemented: contract validation, required metrics plus Sortino/Calmar/hit-rate/turnover, aligned `1/N` benchmark, Memmel Sharpe test, Newey–West Jensen alpha, exact `gap = signal + timing` attribution, subperiod tables, weight diagnostics, figures, and markdown reporting.

Remaining write-up tasks:

1. Cost sensitivity analysis across 0, 10, 30, and 50 bp (`--cost-sweep`).
2. Subperiod narrative (2015 crash, 2018 de-risking, 2021–2022 drawdown, 2023–2024) tied to Part 1–3 choices.
3. Attribution breakdown separating signal tilt from timing/execution effects.
4. Weight diagnostics (effective holdings, max weight, turnover) linked to Part 2 conditioning.
5. Optional: Deflated Sharpe Ratio and reality-check bootstrap.

**Dependency order:** `data -> Part 1 artifacts -> Part 2 covariance -> Part 3 weights -> Part 4 report`

## 5. Risks

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| R1 | Short early history in A; broader cap reference in B. | Regime/reference-dependent covariance bias. | Compare both against sample and Ledoit–Wolf on the same calendar. |
| R2 | Missing industry labels. | Industry block collapses to market intercept. | Document as limitation; rely on eight style factors. |
| R3 | 24-month mock fixture. | Below 60-month requirement. | Fixture only; quote numbers solely from real-data `reports/`. |
| R4 | Cross-part universe mismatch. | Misaligned weights. | `P1_Candidate_Universe.csv` is master; `checks.py` enforces intersection. |
| R5 | Look-ahead in selection or covariance window. | Invalidates OOS results. | Audit window boundaries; covariance at `t` uses data `<= t`. |
| R6 | Untradable stocks in weights. | Unrealistic returns. | Apply `BLACKLIST`/`UNTRADABLE` masks in Part 3; report turnover/costs in Part 4. |
| R7 | Optimistic cost assumptions. | Overstated net returns. | Report 0–50 bp sweep in report and slides. |
| R8 | Interim discussion deadline. | 20% of grade. | Present end-to-end harness and baseline metrics per part. |
| R9 | Reproducibility. | Code grade. | Locked `uv.lock`, tests, and single-command pipelines. |
| R10 | `300330.SZ` delisting (zero returns from 2023-06). | Minimum-variance optimizers treat zero return as zero risk. | Zero target weight from 2023-05 in Part 3 and 1/N; freeze pre-delisting specific variance in Part 2. |
| R11 | Short history in A; undocumented vendor restatements. | Noisy early covariances; potential back-fill. | Document limitations; use Model B for extended factor history. |

## 6. Integration Workflow

- Feature branches `part1/`, `part2/`, `part3/`, `part4/` merge via PR into `main`.
- Attach `uv run sta4020-check-artifacts` output to PRs touching `artifacts/`.
- Freeze each run under `part4_evaluation/reports/<tag>/` with recorded config and manifest.
- Run all commands from the repository root using `uv`:

~~~bash
uv run sta4020-check-data
uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline
~~~

## 7. Decision Log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-11-21 | Separate `group-project` git repository. | Isolates group deliverables and commit history from individual coursework. |
| 2026-11-21 | Vendor `part2_risk_model/` without submodule. | Graded zip archives omit submodule contents and nested `.git` repos. See `PROVENANCE.md`. |
| 2026-11-21 | Default to revised FM forecast and 50-stock pool. | Supersedes legacy validation panel. |
| 2026-11-21 | Parameterize costs across 0, 10, 30, 50 bp one-way. | 10 bp is the base case; sweep shows where strategy rankings flip. |
| 2026-11-21 | Quote metrics solely from `part4_evaluation/reports/`. | `Part3.py` omits costs, 1/N, and statistical tests. |
| 2026-11-22 | Part 2 uses `descriptors.zip`; A for interim, B for final. | A requires no package changes; B extends factor-return history from 2005. |
| 2026-11-22 | Part 1 extensions allow <= 15 pre-registered, 1-month lagged descriptors. | Prevents look-ahead at penultimate close and multiple-testing overfitting across 213 fields. |

## 8. Definition of Done

- All four artifacts pass `sta4020-check-artifacts` (50 assets, >= 60 OOS months).
- Summary table compares all strategies against `1/N` on the four required metrics.
- Formal statistical tests against `1/N` distinguish statistical significance from economic magnitude.
- Cost sensitivity and subperiod tables included.
- Part 4 narrative explains model performance via specific Part 1–3 modeling choices.
- Clean checkout + `data/` reproduces all reported numbers.
