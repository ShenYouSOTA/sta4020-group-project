# Raw data

English | [简体中文](README.zh-CN.md)

This directory is not committed: the files are 530 MB, plus the 609 MB
`addition/` described below, and they are distributed with
the course material, not with the repository.  Copy them here before running
anything that touches the real data.  The code only ever refers to paths
relative to the repository root, so every machine needs the same layout, not
the same absolute path.

| File | Shape | What it holds |
| --- | --- | --- |
| monthly_returns.pkl | 355 x 5378 | Monthly simple total returns, index = month end, one column per stock code. |
| price.h5 | 324 MB | Daily adjusted prices plus the trading calendar (needs h5py, not installed by default). |
| mcap.pkl | 356 x 5634 | Month-end market capitalisation. |
| daily_amount.pkl | 186 MB | Daily traded value. |
| BLACKLIST.pkl | per date | Stocks that must not be held on that date. |
| UNTRADABLE.pkl | per date | Stocks that cannot be traded on that date (suspension, limit up/down). |
| FF5.csv | 357 rows | Fama-French five factors: date, MKT, SMB, HML, RMW, CMA. |
| risk_free.csv | 7223 rows | Daily risk-free rate, date and RF. |
| zz500.pk | 4346 x 7 | CSI 500 daily bars. |

Provenance: the Part 1 delivery (the original zip is kept in _incoming/, also
not committed).  Nothing in this directory is modified by this project; if a
file is ever cleaned or converted, write the transform into
src/sta4020_project/ so the
step is reproducible.

### Addition: `addition/` (descriptors)

| File | Shape | What it holds |
| --- | --- | --- |
| addition/descriptors.zip | 609 MB (2.59 GiB unpacked) | 213 cross-sectional descriptors: momentum, volatility, size and value, quality and profitability, growth, leverage and liquidity, scorecards, analyst expectations. Stored as `OrderedDict[str, Series]` with a `(date, asset)` index over 6,128 tickers x 321 month-end **trading** days (1999-12-30 to 2026-08-31). No industry classification. |

Three things to know before wiring it in (see
[docs/ADDITION_DATA_ASSESSMENT.md](../docs/ADDITION_DATA_ASSESSMENT.md)):

- The archive uses Deflate64, which Python's `zipfile` and bsdtar both reject; use `unzip` or 7z.
- Descriptor dates are the last trading day of the month while the forecast calendar uses calendar month ends; map through `Period('M')`, because a date join matches only 78 of 116 months.
- Per-field coverage and usability tiers live in `artifacts/addition/desc_field_coverage.csv`, produced by `tools/desc_field_coverage.py`.

Check the layout with:

~~~bash
uv run sta4020-check-data
~~~
