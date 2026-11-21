# STA4020 Final Project - group repository

Four-part project: forecast expected returns (Part 1), estimate the risk
structure (Part 2), build portfolios (Part 3), and evaluate them out of sample
(Part 4).  Each part is one person's 25% contribution; the final slides and
report are graded once for the whole group.

Start with [docs/PLAN.md](docs/PLAN.md) - it holds the deadline map, the
artifact contract that the four parts exchange, the work breakdown and the risk
list.

## Directory map

| Path | What it is | Owner |
| --- | --- | --- |
| data/ | Raw vendor data: 5378 monthly returns, daily prices, market caps, turnover, blacklists, FF5, risk-free, CSI 500. 530 MB, never committed. | shared |
| docs/ | Project guideline PDF and the lecture slides. | shared |
| docs/PLAN.md | Engineering plan: deadlines, interfaces, work breakdown, risks. | shared |
| part1_return_model/ | Part 1 notebooks and their original README, unchanged as delivered. | Part 1 |
| part2_risk_model/ | Part 2 package (import risk_model), its tests and the spec document. | Part 2 |
| part3_portfolio/ | Part 3 script Part3.py, unchanged; reads three CSVs from the working directory. | Part 3 |
| part4_evaluation/ | Part 4 report output: tables/, figures/, REPORT.md per run tag. | Part 4 |
| src/sta4020_project/ | Shared code: artifact contracts, metrics, inference, backtest engine, attribution, reporting, CLI. | Part 4 (shared) |
| artifacts/part1/ | Part 1 outputs: expected returns, realised returns, candidate universe. | Part 1 |
| artifacts/part2/ | Part 2 output: P2_Covariance.csv (not delivered yet). | Part 2 |
| artifacts/part3/ | Part 3 output: Portfolio_Weights.csv (not delivered yet). | Part 3 |
| artifacts/sample/ | The mock 20-asset, 24-month panel from the Part 3 zip. Only used for smoke tests. | fixture |
| scripts/ | Runnable entry points: artifact checker, sample pipeline. | shared |
| tests/ | Unit tests for the shared code. | shared |
| _incoming/ | The original zips, kept for provenance. 248 MB, never committed. | shared |

## Quick start

The interpreter used for everything below is the course virtual environment:

~~~
/home/Sota/research/data-analysis/STA4020/.venv/bin/python
~~~

Run the tests:

~~~
make test
~~~

Run the full pipeline on the mock data (Part 3 -> Part 4, 20 assets, 24 months).
This is the smoke test that proves the hand-off works:

~~~
make sample
~~~

Then open part4_evaluation/reports/sample/REPORT.md.

Validate the artifacts before integrating anything:

~~~
.venv/bin/python scripts/check_artifacts.py          # real artifacts
.venv/bin/python scripts/check_artifacts.py --sample # mock artifacts
~~~

Evaluate the real artifacts once Parts 2 and 3 have delivered:

~~~
make evaluate TAG=run1 COST_BPS=10
~~~

## What each part must deliver

The exchange format is deliberately narrow: four CSV files, described in
docs/PLAN.md under "Artifact contract".  Nothing else crosses a part boundary,
so any part can be re-run - or replaced by a better model - without touching
the others.

- Part 1 -> artifacts/part1/P1_Validated_Expected_Returns.csv (the default input)
  and Actual_Returns.csv; P1_Expected_Returns.csv is the raw forecast and stays
  available as a fallback
- Part 2 -> artifacts/part2/P2_Covariance.csv
- Part 3 -> artifacts/part3/Portfolio_Weights.csv
- Part 4 -> part4_evaluation/reports/TAG/REPORT.md plus tables and figures

## Working agreement

- One branch per part, pull requests into main; the artifact contract is the
  review checklist for every pull request that touches a part boundary.
- Never commit data/ or _incoming/; .gitignore already excludes them.
- Run make test and scripts/check_artifacts.py before asking for a review.
- Report numbers are only quoted from part4_evaluation/reports/, never from an
  ad-hoc notebook cell.
