# Raw data

This directory is not committed: the files are 530 MB and are distributed with
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
file is ever cleaned or converted, write the transform into scripts/ so the
step is reproducible.

Check the layout with:

~~~bash
make check-data
~~~
