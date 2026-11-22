# Assessment of the new descriptor data (data/addition)

[简体中文](ADDITION_DATA_ASSESSMENT.zh-CN.md) | English

Object of assessment: `group-project/data/addition/descriptors.zip` (added 2026-11-21; 609 MB archive holding one member `descriptors.pkl`, 2,778,987,650 bytes unpacked ≈ 2.59 GiB).
Question: whether and how this data can be used scientifically as a source for the four parts of the project.
Revision: 2026-11-22, second version after review; see the revision log at the end.

## 0. Verdict

1. **Usable, and the same lineage as the existing panels.** `mktcap` equals `data/mcap.pkl` cell for cell (9,575 pairs; ratio median and 5%/95% quantiles all 1.0000, log correlation 1.00000). This is not an unrelated third-party feed.
2. **Point-in-time risk is low.** Fundamentals update on announcement months (April, August, October peaks; January/June/December ≈ 0), and price-based fields are aligned to the same month as `data/monthly_returns.pkl` (same-month correlation 0.9488, one-month-lag correlation -0.0001). Whether the vendor back-fills restated statements cannot be tested from this data.
3. **The largest payoff is Part 2.** The risk model has only ever run on synthetic data ("real-data integration and empirical calibration remain pending" in `part2_risk_model/README.md`), and this dataset supplies the style exposures it needs, including value, quality and leverage, which the price data cannot provide. Once Part 2 runs on real data, Part 3 has a real covariance and Part 4 has a risk decomposition.
4. **Part 2 needs history before the first origin, and the 50 assets have little of it.** `forecast_risk` truncates the panel at `as_of`, so the origin 2014-12-31 can only use data up to that date. The longest unbroken balanced run of returns and market caps for the 50 assets ends at 2014-12 and starts at 2012-10 (27 months); only 15 of the 50 have complete returns from 2010-01. **Decision (2026-11-22): implementation A** — a balanced 50-asset panel starting 2013-01 with an expanding window, so the first origin sees 24 months. A broad-cross-section estimate (implementation B) is the planned upgrade for the final report; see §4.1.
5. **Part 1 can only be extended under constraints, never by data-driven screening.** Pre-register at most 15 new literature-motivated candidates on top of the existing 11, lag every descriptor by one month (§4.2), and keep the existing 72-month rolling window, Rank IC and BY procedure.
6. **Industry labels are still absent.** Nothing among the 213 fields is an industry code, so risk R2 in `docs/PLAN.md` stands: the industry block degenerates to a single market factor. Do not fabricate industries by clustering.
7. **`300330.SZ` is delisted inside the sample.** It returns -0.5701 in 2023-04, has exactly zero returns from 2023-06, and its `data/mcap.pkl` values are NaN from 2023-06. It stays in the covariance (N = 50 throughout) but must receive zero weight from 2023-05 onward; feeding its zero returns to the optimisers as if they were real would make it look riskless.
8. **Gaps are quantified and manageable.** On the 50-asset × 116-month calendar: 163 fields tier A, 31 tier B, 10 tier C, 9 tier D. Three of the recommended style inputs are not tier A (`idios_vol_ff3_21` and `turnover_252` are B, `dividendyield2` is C); §4.1 handles them.
9. **Keep it out of git.** `.gitignore` already ignores `data/*`. Commit the derived panel and the rebuild script instead of the 2.59 GiB pickle.

## 1. Shape of the data

| Item | Fact |
| --- | --- |
| Container | ZIP, compression method 9 (Deflate64). Python `zipfile` raises `NotImplementedError` and bsdtar refuses it; Info-ZIP `unzip` and 7z both work. |
| Size | 2,778,987,650 bytes unpacked; `pd.read_pickle` peaks at about 2.89 GB RSS. The object must be loaded whole — it cannot be streamed in chunks. |
| Structure | `collections.OrderedDict` with 213 keys; every value is a `pandas.Series` of float64 with a `('date','asset')` MultiIndex. |
| Assets | 6,128 tickers in the project's format (`000001.SZ`, `600000.SH`). |
| Dates | 321 month-end **trading** days, 1999-12-30 to 2026-08-31 (e.g. 2000-01-28, 2014-12-31, 2015-01-30). |
| Field families | momentum and volatility (`momentum_21`, `momentum_academic_252_21`, `long_term_reversal_756`, `total_vol_21/63`, `idios_vol_ff3_21`, `market_beta_252`, `illiq_252`, `turnover_252`, `zero_return_ratio_252`); size and value (`mktcap`, `total_mv`, `[close]`, `book_value_to_total_mktcap_mrq`, `net_profit_to_total_mktcap_ttm`, `dividendyield2`); quality (`gross_profit_to_asset_ttm`, `return_on_invested_capital_ttm`, `accrual_to_asset_ttm`); growth (`revenue_yoy_pct_chg` and relatives); leverage and liquidity (`total_liab_to_total_asset_mrq`, `current_ratio_mra`); scorecards (`altman_zscore`, `fscore`, `graham_score`, `dechow_score`); analyst expectations (`west_eps_fy1`, `rating_avg`, `revisions_in_analyst_earnings_forecasts`). |
| Industry labels | **None.** |

### 1.1 Calendar alignment

`artifacts/part1/P1_Expected_Returns.csv` indexes **calendar** month ends (2014-12-31 … 2024-07-31, 116 rows) while the descriptors use the last trading day of the month. A direct date join matches only 78 of 116; mapping descriptor dates to `Period('M')` matches 116 of 116. The adapter must key on (month, asset) and must never join on dates.

## 2. Three consistency checks

| Check | Method | Result | Meaning |
| --- | --- | --- | --- |
| Same lineage | `descriptors['mktcap']` against `data/mcap.pkl` by month | 9,575 pairs; ratio median 1.0000, p05/p95 1.0000, log correlation 1.00000 | Same pipeline and units; the two datasets cross-validate |
| Month labels | `[close]` month-on-month return against `data/monthly_returns.pkl`, same month vs one month lag | 9,525 pairs; same-month correlation 0.9488, **lagged correlation -0.0001**, median absolute difference 0.00000 | The month-t descriptor already contains the month-t return, so it is known only at the last close of month t |
| Point-in-time | Share of assets whose value changes, aggregated by calendar month, 2015–2024 | `book_value_mrq`: April 0.524, August 0.554, October 0.508, March 0.126, May 0.222, January/June/December ≈ 0.001; `net_profit_q` identical pattern (0.518 / 0.552 / 0.503) | Fundamentals are released on announcement dates (annual and Q1 reports by April, interim August, Q3 October), not at fiscal period ends |

What the point-in-time row does and does not establish: it shows the vendor does not stamp statements at the fiscal period end, so the gross look-ahead of using a December balance sheet in December is absent. It cannot show whether later restatements were written back into earlier months. This is a data limitation (§7), not a closure of risk R5 in `docs/PLAN.md`: R5 is about the Part 1 selection and the covariance window, and stays open.

No field contains `inf` on the target panel, and no tier A or B field has a non-positive cross-sectional standard deviation in any of the 116 months. Extreme values still need care: the 99.9th percentile of cross-sectional `|z|` reaches about 7 (`total_accrual_to_net_profit_ttm` 6.9, `return_on_invested_capital_ttm` 7.1), so the raw data is **not** winsorised and the adapter must winsorise.

## 3. Coverage

### 3.1 Forecast calendar

Target panel: 50 assets (`artifacts/part1/P1_Candidate_Universe.csv`) × 116 months = 5,800 cells; all 50 assets are present.

| Tier (rule) | Fields | Handling |
| --- | --- | --- |
| A: coverage ≥95%, no `inf`, positive dispersion each month | 163 | use directly |
| B: coverage 90–95% | 31 | impute with the cross-sectional median and log the imputation rate |
| C: coverage 50–90% | 10 | robustness checks only |
| D: coverage <50% | 9 | drop |

The per-field table is `artifacts/addition/desc_field_coverage.csv`. Its `first_valid_month` column is measured inside the forecast calendar and therefore reads 2014-12 for almost every field; `first_valid_month_full` is measured over the whole file.

Three kinds of gap:

1. **Delisting.** `300330.SZ` has no descriptors for 2023-05 … 2024-07, which is exactly why 15 months show 49 of 50 assets observed (the best coverage is 5,785 / 5,800 = 0.997414). Its return is -0.5701 in 2023-04, +0.0515 in 2023-05 and exactly 0 for the 15 months from 2023-06; `data/mcap.pkl` keeps the column but its values are NaN from 2023-06.
2. **Stock-level gaps in price fields.** Only 3 of the 50 assets have `total_vol_21` in every month; the worst (`300149.SZ`) misses 24. By year the missing rate falls from 13.7% (2015) and 14.5% (2016) to about 1% after 2019. Missingness overlaps a zero return only 3.9% of the time, so it reflects gaps in the vendor's own price history rather than suspensions.
3. **Analyst fields.** 38–43% coverage on the calendar, tier D. They exist well before the sample (`rating_avg` from 2004-12, `revisions_in_analyst_earnings_forecasts` from 2005-03, `west_eps_fy1` from 2013-01); the reason to drop them is coverage, not start date.

### 3.2 Pre-sample window (needed by Part 2)

| Window ending 2014-12 | Assets with complete returns (of 50) |
| --- | --- |
| from 2005-01 | 12 |
| from 2010-01 | 15 |
| from 2012-01 | 40 |
| from 2012-10 | 50 (longest unbroken balanced run of returns and market caps, 27 months) |

The youngest assets list in 2012 (`300354.SZ` has its first return in 2012-10). On the pre-sample window 2012-10 … 2014-11 (`presample_coverage` in the table) the fundamental style inputs are complete (1.000), `momentum_21` is 0.953, `idios_vol_ff3_21` 0.945, `turnover_252` and `market_beta_252` 0.916, `momentum_academic_252_21` 0.892 — the last needs twelve months of history that recent listings do not yet have. Median `presample_coverage` across all 213 fields is 0.987.

## 4. How to use it

### 4.1 Layer one (required): real style exposures for Part 2

The contract lives in `part2_risk_model/src/risk_model/factor_model.py:11-19`, validation in `:30-53`, style standardisation in `:64-69`; the entry point `forecast_risk` truncates the panel at `as_of` (`risk_model.py:21`) and uses the last exposure row for the forecast.

Constraints the adapter must meet:

- The panel must be balanced with no NaN and `T>=2`; `market_caps` must match `returns` and stay strictly positive; every stock belongs to exactly one listed industry on every date and every industry must be represented.
- Styles are standardised **inside the package**: cap-weighted centring, then division by the equal-weighted cross-sectional standard deviation (ddof = 1), raising `ValueError("raw styles must have positive dispersion")` when dispersion is non-positive.

**Standardisation rule.** That transform is invariant to any per-month affine map `a_t + b_t·x` with `b_t > 0`, so an external z-score would be harmless but redundant: it neither shifts the intercept nor changes the conditioning of the constrained WLS. The rule is therefore about clarity, not numerics:

- **Single-field styles:** pass the transformed raw value (log where listed, winsorised, sign applied). No external z-score.
- **Composite styles:** winsorise each component, z-score it within the month, apply its sign, then take the equal-weighted mean of the available components. The components must be on a common scale before they are averaged; the package re-standardises the composite anyway.
- **Winsorisation:** each month, clip at median ± 5 × 1.4826 × MAD (≈ ±5 robust standard deviations). A mean ± 3σ rule uses a standard deviation that the outliers themselves inflate.

**Styles: Q = 8, no more.** With N = 50 each monthly cross-sectional regression estimates 1 + Q parameters, so Q = 8 leaves 41 degrees of freedom; beta and growth go to robustness only.

| Style | Field(s) | Tier | Handling |
| --- | --- | --- | --- |
| Size | `mktcap` | A | log |
| Value | `book_value_to_total_mktcap_mrq`, `net_profit_to_total_mktcap_ttm` | A, A | composite; `dividendyield2` (tier C, 0.817) only in a robustness variant |
| Momentum | `momentum_academic_252_21` | A | as is |
| Short-term reversal | `momentum_21` | A | negate |
| Volatility | `idios_vol_ff3_21` | B | as is; closer to Barra residual volatility than `total_vol_63` |
| Liquidity | `turnover_252` | B | log; `illiq_252` as robustness alternative |
| Quality | `return_on_invested_capital_ttm`, `gross_profit_to_asset_ttm`, `accrual_to_asset_ttm` | A, A, A | composite; accruals negated |
| Leverage | `total_liab_to_total_asset_mrq` | A | as is |

Robustness only: `market_beta_252`, `revenue_yoy_pct_chg`, `dividendyield2` in Value, `illiq_252` for Liquidity.

**Estimation design: implementation A (decided 2026-11-22).**

- The panel holds the 50 assets from **2013-01** to 2024-07, monthly, with excess returns from `data/monthly_returns.pkl` minus the monthly risk-free rate from `data/risk_free.csv`. Starting at 2013-01 rather than 2012-10 skips the first months after the latest listings; 2012-10 is the sensitivity run.
- For every origin `t` in the Part 1 calendar, call `forecast_risk(panel, as_of=t, ...)`. The window expands; the first origin has 24 rows of history and therefore 23 monthly factor returns for a 9 × 9 factor covariance. Early covariances are noisy, and the report must say so.
- Industry: one industry for all assets (R2).
- `300330.SZ`: see the gap rules below.
- Run a plain sample covariance and a Ledoit–Wolf covariance on the same windows as references (PLAN R1).

**Implementation B (final-report upgrade, not built yet).** Estimate factor returns month by month on a broad cross-section (for example the largest 800 stocks with complete data in months t and t+1; a two-row `RiskPanel` is valid input to `fit_factor_model`), which yields a factor-return history from 2005. Then assemble the 50-asset covariance with the package's components (`stable.estimate_factor_covariance`, `integration.compute_asset_covariance`), using specific variances from the 50-asset residuals. This bypasses `forecast_risk`, so the dynamic and integration steps must be composed by hand. Comparing A with B is part of the Part 2 chapter.

**Gap rules, fixed and reproducible:**

- Stock-level gaps in style inputs: cross-sectional median imputation within the month, plus a missingness indicator kept only for diagnostics. Log the imputation rate per style and month.
- `300330.SZ` from 2023-05: keep the asset so that N = 50 throughout. Carry its last market cap and style values forward to satisfy `market_caps > 0`. Exclude its post-delisting months from its own specific-variance estimate and carry the last pre-delisting estimate instead, so its covariance row does not shrink towards zero. Part 3 sets its weight to zero from 2023-05 through the UNTRADABLE mask, and Part 4 reports the treatment.

### 4.2 Layer two (recommended): extending Part 1's feature set

1. **Never screen 213 fields.** Pre-register **at most 15 new candidates** from the literature (value, profitability, investment, accruals, leverage), added to the existing 11, so the BY procedure runs on at most 26 tests. Write the list into this document before running anything.
2. **Lag every descriptor by one month.** Part 1 builds features after the close of the second-to-last trading day of month t and executes at the last close (`part1_return_model/logic_readme.md` §1). The month-t descriptor is only known at that last close, so at signal time Part 1 may use the **month t−1** descriptor. Fundamentals change quarterly, so the lag costs little. Price-based descriptors (`momentum_21`, `total_vol_*`, `idios_vol_*`) are not added: the existing 11 features already cover price and volume at the correct timing. Moving the whole Part 1 signal date instead would rebuild a delivered model and is not planned.
3. **Train on the broad cross-section, not on the 50.** The first 72-month training window runs from 2008-11 to 2014-11. Before using a candidate, measure its coverage on the broad cross-section over that window (the 50 assets themselves were only about 28% covered in 2008).
4. **Reuse the existing missing-value convention** (centre score 0) and report one sensitivity run restricted to years with high coverage.

The payoff: the existing 11 features are price and volume, so the descriptors add value, quality and accruals — the most defensible "economic explanation" upgrade available for the presentation.

### 4.3 Layer three (cheap, high visibility): Part 4 risk decomposition and attribution

- **Risk decomposition**: split forecast portfolio volatility into factor and specific risk using the Part 2 covariance, then compare with realised volatility (Mincer–Zarnowitz regression, a Q-statistic on forecast errors).
- **Style attribution**: regress portfolio monthly returns on the eight style factor returns to say where the excess return came from, which complements the "versus 1/N" comparison.

### 4.4 Explicitly rejected

- Analyst fields (`west_eps_fy1`, `rating_avg`, `revisions_*`): tier D, below half coverage.
- `free_cash_flow_yoy_pct_chg`: 19% coverage on the calendar, none on the pre-sample window.
- Clustering an industry proxy: no labels means no validation standard, so the single-industry degeneracy plus a written limitation is the defensible choice.
- `graham_score` and `gscore` as core factors: 55–70% coverage, tier C, robustness only.

## 5. Acceptance gates

1. The loader rebuilds the panels from `descriptors.zip` in under three minutes and reproduces `artifacts/addition/desc_field_coverage.csv`.
2. The style panel satisfies the `RiskPanel` contract exactly: no NaN, `market_caps > 0`, one industry per stock, positive dispersion every month — asserted by a test that calls the package's own validation.
3. Across the 116 months, the median monthly |ρ| between any two of the eight constructed styles is below 0.7, and every style's VIF is below 5. A single-month threshold is not used: with N = 50 the monthly correlation is noisy (raw `net_profit_to_total_mktcap_ttm` against `return_on_invested_capital_ttm` peaks at 0.97 with a mean of 0.55).
4. No look-ahead in Part 2: the covariance for origin t is a function of panel rows up to t only, checked by a test that perturbs rows after t and asserts the covariance at t is unchanged.
5. `artifacts/part2/P2_Covariance.csv` from real data passes `sta4020-check-artifacts`, is positive definite at every origin, its top five eigenvalues explain less than 95% of the trace, and its diagonal is on the same scale as realised stock variance.
6. Part 1 reports baseline (11 candidates) against extended (11 + at most 15) on the same 116 months and the same 50 assets: Rank IC, ICIR and out-of-sample metrics against 1/N. If the extension does not improve stably, keep the baseline and say so.
7. The report states: R2 (no industry) remains; the short early history of implementation A; how `300330.SZ` was handled; the winsorisation and imputation rules; the point-in-time evidence and its limit.

## 6. Work plan against the milestones

| Step | Output | Estimate |
| --- | --- | --- |
| 1. Loader | `src/sta4020_project/descriptors.py`: unzip into the cache, (month, asset) keys, per-field panel builder that loads only the requested fields, tests for the 116/116 alignment and the `mktcap` = `mcap.pkl` identity | 0.5 day |
| 2. Styles | eight styles under the §4.1 rules, winsorisation, imputation log, `300330.SZ` carry-forward, excess returns, export `artifacts/addition/style_panel.npz`; gates 2 and 3 | 1 day |
| 3a. Risk model A | `forecast_risk` per origin on the expanding window, sample and Ledoit–Wolf references, export `artifacts/part2/P2_Covariance.csv` plus diagnostics; gates 4 and 5 | 1 day |
| 4. Portfolio and evaluation | Part 3 with UNTRADABLE/BLACKLIST masks across five methods on the new covariance; Part 4 run frozen under the `interim` tag | 0.5 day |
| 3b. Risk model B | broad-cross-section factor returns, assembled covariance, comparison with A | 1 day |
| 5. Return model | pre-registered extension with the one-month lag; gate 6 | 1 day |
| 6. Part 4 decomposition | factor/specific risk split and style attribution | 0.5 day |
| 7. Documentation | plan risk table and the report's limitations; gate 7 | 0.5 day |

Steps 1, 2, 3a and 4 target the 11/23–11/27 interim window; steps 3b, 5, 6 and 7 follow in early December.

## 7. Risks and limitations to quote in the report

1. **No industry labels**, so industry rotation is absorbed into market risk and stock-specific risk is estimated conservatively.
2. **Short early history (implementation A)**: the first origins rely on about two years of factor returns estimated on 50 stocks, so early covariances are noisy. Implementation B addresses this.
3. **Field semantics are vendor-defined**: windows, adjustment conventions and accounting restatements are undocumented, and can only be confirmed indirectly through the consistency checks above. Back-filled restatements cannot be ruled out.
4. **Uneven coverage**: price fields miss 12–15% in 2015–2017, so early-sample estimates lean more heavily on imputation.
5. **A delisted asset in a fixed universe**: `300330.SZ` delists in 2023; it is held at zero weight from 2023-05, which the 1/N benchmark must mirror.
6. **Bulk**: 609 MB archive, 2.59 GiB unpacked, Deflate64 compression that the Python standard library cannot read — the reproduction instructions must require `unzip` or 7z.
7. **Single source**: the exact match with `data/mcap.pkl` shows both datasets come from one vendor, so they cannot correct each other's systematic bias.

## Appendix A: reproduction

~~~bash
unzip -o data/addition/descriptors.zip -d "$HOME/.cache/sta4020/"

.venv/bin/python tools/desc_field_coverage.py \
  --descriptors "$HOME/.cache/sta4020/descriptors.pkl" \
  --universe artifacts/part1/P1_Candidate_Universe.csv \
  --calendar artifacts/part1/P1_Expected_Returns.csv \
  --history-start 2012-10 \
  --out artifacts/addition/desc_field_coverage.csv
~~~

## Revision log

| Date | Change |
| --- | --- |
| 2026-11-22 | First version. |
| 2026-11-22 | Review revision: added the pre-sample analysis and chose implementation A (§3.2, §4.1); replaced the `300330.SZ` zero-return rule with zero weight from 2023-05; Part 1 descriptors lagged one month; corrected the standardisation argument and added the composite rule; corrected the tiers of the style inputs and dropped `dividendyield2` from the core Value style; R5 no longer described as closed; analyst start dates corrected; correlation gate replaced; "≤15" defined as new candidates; added the look-ahead gate. |
