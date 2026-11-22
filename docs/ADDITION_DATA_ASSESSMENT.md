# Assessment of `data/addition/descriptors.zip`

[简体中文](ADDITION_DATA_ASSESSMENT.zh-CN.md) | English

Source: `group-project/data/addition/descriptors.zip` (609 MB archive containing `descriptors.pkl`, 2,778,987,650 bytes ≈ 2.59 GiB unpacked).

## 0. Summary

1. **Same lineage as existing panels.** `mktcap` matches `data/mcap.pkl` cell-for-cell (9,575 pairs; ratio median and 5%/95% quantiles = 1.0000; log correlation = 1.00000).
2. **Announcement-aligned fundamentals.** Fundamentals update on announcement months (April, August, October peaks; January/June/December ≈ 0), and price fields align to the same month as `data/monthly_returns.pkl` (same-month correlation 0.9488, one-month-lag correlation -0.0001). Restatement back-filling is undocumented.
3. **Primary use: Part 2 style exposures.** Supplies value, quality, and leverage factors missing from price-only data.
4. **Part 2 pre-sample window.** `forecast_risk` truncates at `as_of`, so 2014-12-31 uses only prior data. The longest unbroken balanced panel for the 50 assets starts 2012-10 (27 months); 15 assets have complete returns from 2010-01. **Implementation A** uses a balanced 50-asset expanding panel from 2013-01 (24 months at first origin); **Implementation B** estimates factor returns on a broad cross-section from 2005 (§4.1).
5. **Part 1 constraints.** Pre-register at most 15 literature-motivated candidates alongside the existing 11, lag every descriptor by one month (§4.2), and retain the 72-month rolling window, Rank IC, and BY procedure.
6. **No industry labels.** All 213 fields lack industry codes; the industry block collapses to a single market intercept (risk R2 in `docs/PLAN.md`).
7. **Delisting (`300330.SZ`).** Returns -0.5701 in 2023-04, +0.0515 in 2023-05, and 0 from 2023-06 (`data/mcap.pkl` becomes NaN). Retain `N = 50` in covariance with zero portfolio weight from 2023-05 onward.
8. **Coverage tiers (50 assets × 116 months).** 163 tier A, 31 tier B, 10 tier C, 9 tier D. Non-tier-A style inputs (`idios_vol_ff3_21` and `turnover_252` in B; `dividendyield2` in C) are handled in §4.1.
9. **Untracked.** `.gitignore` excludes `data/*`; commit derived panels and rebuild scripts only.

## 1. Data Structure

| Item | Detail |
| --- | --- |
| Container | ZIP, Deflate64 (method 9). Unpack with Info-ZIP `unzip` or `7z` (`zipfile` and `bsdtar` lack Deflate64 support). |
| Size | 2,778,987,650 bytes unpacked; `pd.read_pickle` peaks at ~2.89 GB RSS. |
| Structure | `collections.OrderedDict` of 213 `float64` `pandas.Series` with `('date','asset')` MultiIndex. |
| Assets | 6,128 tickers (`000001.SZ`, `600000.SH`). |
| Dates | 321 month-end **trading** days, 1999-12-30 to 2026-08-31. |
| Field families | Momentum & volatility (`momentum_21`, `momentum_academic_252_21`, `long_term_reversal_756`, `total_vol_21/63`, `idios_vol_ff3_21`, `market_beta_252`, `illiq_252`, `turnover_252`, `zero_return_ratio_252`); size & value (`mktcap`, `total_mv`, `[close]`, `book_value_to_total_mktcap_mrq`, `net_profit_to_total_mktcap_ttm`, `dividendyield2`); quality (`gross_profit_to_asset_ttm`, `return_on_invested_capital_ttm`, `accrual_to_asset_ttm`); growth (`revenue_yoy_pct_chg`); leverage & liquidity (`total_liab_to_total_asset_mrq`, `current_ratio_mra`); scorecards (`altman_zscore`, `fscore`, `graham_score`, `dechow_score`); analyst (`west_eps_fy1`, `rating_avg`, `revisions_in_analyst_earnings_forecasts`). |
| Industry labels | None. |

### 1.1 Calendar Alignment

`artifacts/part1/P1_Expected_Returns.csv` uses **calendar** month ends (2014-12-31 … 2024-07-31, 116 rows), whereas descriptors use the last **trading** day of each month. Direct date joins match 78/116 months; joining via `Period('M')` matches 116/116. Key the adapter on `(month, asset)`.

## 2. Consistency Checks

| Check | Method | Result | Interpretation |
| --- | --- | --- | --- |
| Lineage | `descriptors['mktcap']` vs `data/mcap.pkl` by month | 9,575 pairs; ratio median and p05/p95 = 1.0000; log corr = 1.00000 | Same pipeline and units. |
| Month labels | `[close]` MoM return vs `data/monthly_returns.pkl` (same month vs 1-month lag) | 9,525 pairs; same-month corr 0.9488, **lagged corr -0.0001**, median abs diff 0.00000 | Month-t descriptor embeds month-t return; known at month-t close. |
| Point-in-time | Monthly fraction of stocks changing value (2015–2024) | `book_value_mrq`: Apr 0.524, Aug 0.554, Oct 0.508, Mar 0.126, May 0.222, Jan/Jun/Dec ≈ 0.001; `net_profit_q`: 0.518 / 0.552 / 0.503 | Fundamentals update on announcement months rather than fiscal period ends. |

Announcements align to release months, avoiding fiscal-period-end look-ahead; restatement back-filling remains undocumented (§7), and risk R5 in `docs/PLAN.md` remains open.

No field contains `inf`, and all tier A/B fields have positive monthly cross-sectional standard deviation. The 99.9th percentile of cross-sectional `|z|` reaches ~7 (`total_accrual_to_net_profit_ttm` 6.9, `return_on_invested_capital_ttm` 7.1), so raw values require winsorization.

## 3. Coverage

### 3.1 Forecast Calendar

Target panel: 50 assets (`artifacts/part1/P1_Candidate_Universe.csv`) × 116 months = 5,800 cells.

| Tier (rule) | Fields | Handling |
| --- | --- | --- |
| A: coverage ≥ 95%, finite, positive monthly dispersion | 163 | Use directly |
| B: coverage 90–95% | 31 | Impute with cross-sectional median; log rate |
| C: coverage 50–90% | 10 | Robustness checks only |
| D: coverage < 50% | 9 | Drop |

Per-field coverage lives in `artifacts/addition/desc_field_coverage.csv` (`first_valid_month` covers the forecast calendar; `first_valid_month_full` covers the full file).

Gap patterns:

1. **Delisting:** `300330.SZ` lacks descriptors for 2023-05 … 2024-07 (15 months with 49/50 assets; max coverage 5,785/5,800 = 0.997414).
2. **Stock-level price gaps:** Only 3/50 assets have complete `total_vol_21` (`300149.SZ` misses 24 months). Missingness drops from 13.7% (2015) and 14.5% (2016) to ~1% after 2019, overlapping zero returns only 3.9% of the time.
3. **Analyst fields:** 38–43% coverage (tier D, dropped despite starting in 2004–2013).

### 3.2 Pre-Sample Window (Part 2)

| Window ending 2014-12 | Assets with complete returns (/50) |
| --- | --- |
| from 2005-01 | 12 |
| from 2010-01 | 15 |
| from 2012-01 | 40 |
| from 2012-10 | 50 (27 months, longest balanced run) |

The youngest stock (`300354.SZ`) lists in 2012-10. Over 2012-10 … 2014-11 (`presample_coverage`), fundamental inputs = 1.000, `momentum_21` = 0.953, `idios_vol_ff3_21` = 0.945, `turnover_252` & `market_beta_252` = 0.916, `momentum_academic_252_21` = 0.892 (median across 213 fields = 0.987).

## 4. Integration Design

### 4.1 Layer 1: Part 2 Style Exposures

`RiskPanel` contract (`part2_risk_model/src/risk_model/factor_model.py:11-19`, validation `:30-53`, standardization `:64-69`) and `forecast_risk` (`risk_model.py:21`):

- Balanced panel, finite values, `T >= 2`, `market_caps > 0`, one represented industry per stock.
- Internal standardization: cap-weighted centering divided by equal-weighted cross-sectional standard deviation (`ddof=1`).

**Standardization rules:** Because package standardization is invariant to positive monthly affine transforms (`a_t + b_t·x`, `b_t > 0`), single fields omit external z-scoring:

- **Single-field styles:** pass transformed raw value (log where specified, winsorized, signed).
- **Composite styles:** winsorize each component, z-score within month, apply sign, take equal-weighted mean of available components.
- **Winsorization:** clip monthly at `median ± 5 × 1.4826 × MAD`.

**Eight styles (Q = 8):** leaves 41 degrees of freedom per monthly regression when `N = 50`.

| Style | Field(s) | Tier | Handling |
| --- | --- | --- | --- |
| Size | `mktcap` | A | log |
| Value | `book_value_to_total_mktcap_mrq`, `net_profit_to_total_mktcap_ttm` | A, A | composite (`dividendyield2` C-tier for robustness) |
| Momentum | `momentum_academic_252_21` | A | as is |
| Short-term reversal | `momentum_21` | A | negate |
| Volatility | `idios_vol_ff3_21` | B | as is |
| Liquidity | `turnover_252` | B | log (`illiq_252` for robustness) |
| Quality | `return_on_invested_capital_ttm`, `gross_profit_to_asset_ttm`, `accrual_to_asset_ttm` | A, A, A | composite; accruals negated |
| Leverage | `total_liab_to_total_asset_mrq` | A | as is |

Robustness candidates: `market_beta_252`, `revenue_yoy_pct_chg`, `dividendyield2`, `illiq_252`.

**Implementation A (interim):** 50 assets, 2013-01 to 2024-07, excess returns (`monthly_returns.pkl` minus `risk_free.csv`), expanding `forecast_risk(panel, as_of=t)` (24 rows / 23 factor returns at first origin), single industry, compared with sample and Ledoit–Wolf covariances.

**Implementation B (final):** estimate monthly factor returns via `fit_factor_model` on the top 800 positive-cap stocks from 2005, then assemble 50-asset covariances with `stable.estimate_factor_covariance` and `integration.compute_asset_covariance` using 50-asset residual variances.

**Gap rules:**
- Stock-level style gaps: monthly cross-sectional median imputation; log imputation rate per style/month.
- `300330.SZ` from 2023-05: carry forward last market cap and styles to keep `N = 50`; freeze pre-delisting specific variance; set portfolio weight to 0 via `UNTRADABLE` mask.

### 4.2 Layer 2: Part 1 Feature Extension

1. Pre-register at most 15 literature-motivated candidates (value, profitability, investment, accruals, leverage) alongside the existing 11 (≤ 26 total BY tests).
2. Lag every descriptor by one calendar month: month-t descriptors are only observed at month-t close, whereas signals form at the penultimate trading close (`part1_return_model/logic_readme.md` §1). Omit price-based descriptors already covered by the 11 features.
3. Train on the broad cross-section (first 72-month window: 2008-11 to 2014-11) after verifying candidate coverage.
4. Keep center-score (0) imputation and report a high-coverage-years sensitivity run.

Adds fundamental value, quality, and accruals alongside the 11 price/volume features.

### 4.3 Layer 3: Part 4 Decomposition

- **Risk decomposition:** split forecast variance into factor and specific components; evaluate against realized volatility via Mincer–Zarnowitz regression and Q(6) test.
- **Style attribution:** regress monthly portfolio active returns on the eight style factor returns.

### 4.4 Excluded Fields

- Analyst fields (`west_eps_fy1`, `rating_avg`, `revisions_*`): tier D (< 50% coverage).
- `free_cash_flow_yoy_pct_chg`: 19% coverage, missing pre-sample.
- Clustered industry proxies: no ground-truth labels for validation; retain single-industry fallback.
- `graham_score`, `gscore`: tier C (55–70% coverage), robustness only.

## 5. Acceptance Gates

1. Loader unpacks/rebuilds panels in < 3 minutes and reproduces `artifacts/addition/desc_field_coverage.csv`.
2. Style panel passes `RiskPanel` validation (finite, `market_caps > 0`, one industry, positive monthly dispersion).
3. Median monthly `|ρ| < 0.7` across all style pairs and `VIF < 5` for every style over 116 months.
4. No look-ahead in Part 2 (covariance at `t` invariant to perturbations after `t`).
5. `artifacts/part2/P2_Covariance.csv` passes `sta4020-check-artifacts`, is PD at every origin, has top-5 eigenvalue share < 95%, and matches realized stock variance scale.
6. Part 1 reports baseline (11) vs extended (11 + ≤ 15) on identical 116 months × 50 assets (Rank IC, ICIR, OOS vs 1/N).
7. Final report documents R2 (no industry), A's short early history, `300330.SZ` handling, winsorization/imputation, and PIT evidence/limits.

## 6. Milestone Plan

| Step | Output | Estimate |
| --- | --- | --- |
| 1. Loader | `src/sta4020_project/descriptors.py` + alignment/identity tests | 0.5 day |
| 2. Styles | 8 styles, winsorization, `300330.SZ` carry-forward -> `artifacts/addition/style_panel.npz` | 1 day |
| 3a. Risk A | Expanding `forecast_risk` + sample/Ledoit–Wolf -> `artifacts/part2/P2_Covariance.csv` | 1 day |
| 4. Portfolio & Eval | Part 3 with masks + Part 4 `interim` tag | 0.5 day |
| 3b. Risk B | Broad-cross-section factor returns + A vs B comparison | 1 day |
| 5. Return model | Pre-registered 1-month-lagged extension | 1 day |
| 6. Part 4 decomposition | Factor/specific split + style attribution | 0.5 day |
| 7. Documentation | Plan risk table + report limitations | 0.5 day |

## 7. Limitations

1. **No industry labels:** industry rotation merges into market risk.
2. **Short early history (Model A):** first origins use ~2 years of 50-stock factor returns (addressed by Model B).
3. **Undocumented vendor restatements:** point-in-time release months are confirmed, but back-filled restatements cannot be ruled out.
4. **Uneven early coverage:** price fields miss 12–15% in 2015–2017.
5. **Delisted stock in fixed pool:** `300330.SZ` exits in 2023-05 with zero weight in strategies and 1/N.
6. **Archive format:** 609 MB Deflate64 ZIP (2.59 GiB unpacked) requires `unzip` or `7z`.
7. **Single vendor source:** `mktcap` matches `mcap.pkl`, so both share any vendor-level bias.

## Appendix A: Reproduction

~~~bash
unzip -o data/addition/descriptors.zip -d "$HOME/.cache/sta4020/"

.venv/bin/python tools/desc_field_coverage.py \
  --descriptors "$HOME/.cache/sta4020/descriptors.pkl" \
  --universe artifacts/part1/P1_Candidate_Universe.csv \
  --calendar artifacts/part1/P1_Expected_Returns.csv \
  --history-start 2012-10 \
  --out artifacts/addition/desc_field_coverage.csv
~~~
