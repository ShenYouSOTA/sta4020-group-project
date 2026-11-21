# STA4020 Final Project - group repository

Four-part project: forecast expected returns (Part 1), estimate the risk
structure (Part 2), build portfolios (Part 3), and evaluate them out of sample
(Part 4).  Each part is one person's 25% contribution; the final slides and
report are graded once for the whole group.

Start with [docs/PLAN.md](docs/PLAN.md) - it holds the deadline map, the
artifact contract that the four parts exchange, the work breakdown and the risk
list.

All commands below are run from the repository root, and every path in the code
is relative to it.  Nothing depends on where the repository lives or on who
runs it.

## Requirements

- Python 3.11 or newer
- make (optional; the underlying commands are one line each)

The default dependency sets are numpy, pandas, scipy and matplotlib, with
pytest for the development extras.

## Setup

~~~bash
make setup
~~~

which is a shortcut for:

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
~~~

On Windows use .venv/Scripts/python.exe instead of .venv/bin/python.  After
setup, .venv/bin/python is picked up automatically, or activate the environment
and call python directly.

## Quick start

~~~bash
make test            # unit tests for the shared code
make sample          # end-to-end smoke test on the mock artifacts
make check-data      # are the raw data files present?
make check-artifacts # are the CSVs from Parts 1 and 2 well formed?
~~~

The smoke test runs the unmodified Part 3 script on the mock 20-asset,
24-month panel that came inside the Part 3 zip, passes the weights through the
Part 4 evaluation, and writes part4_evaluation/reports/sample/REPORT.md.  It
proves that the hand-off works before the real Part 2 and Part 3 outputs exist.

Evaluate the real artifacts once they have been delivered:

~~~bash
make evaluate TAG=run1 COST_BPS=10
~~~

## Raw data

data/ is not committed: the payload is 530 MB and ships with the course
material.  Copy it in, keeping the file names, then run make check-data.  The
expected layout and the meaning of each file are documented in
[data/README.md](data/README.md), which is tracked even though its neighbours
are not.  price.h5 needs h5py, which is only required for the daily frequency
route, so it is not in the default dependencies.

## Directory map

| Path | What it is | Owner |
| --- | --- | --- |
| data/ | Raw vendor data: 5378 monthly returns, daily prices, market caps, turnover, blacklists, FF5, risk-free, CSI 500. Not committed. | shared |
| docs/ | Project guideline PDF and the lecture slides. | shared |
| docs/PLAN.md | Engineering plan: deadlines, interfaces, work breakdown, risks. | shared |
| part1_return_model/ | Part 1 notebooks and their original README, unchanged as delivered. | Part 1 |
| part2_risk_model/ | Part 2 package (import risk_model), its tests and the spec; vendored, see PROVENANCE.md. | Part 2 |
| part3_portfolio/ | Part 3 script Part3.py with a CLI; defaults to the artifacts tree. | Part 3 |
| part4_evaluation/ | Part 4 report output: tables/, figures/, REPORT.md per run tag. Not committed. | Part 4 |
| src/sta4020_project/ | Shared code: artifact contracts, metrics, inference, backtest engine, attribution, reporting, CLI. | Part 4 (shared) |
| artifacts/part1/ | Part 1 outputs: expected returns, realised returns, candidate universe. | Part 1 |
| artifacts/part2/ | Part 2 output: P2_Covariance.csv. | Part 2 |
| artifacts/part3/ | Part 3 output: Portfolio_Weights.csv. | Part 3 |
| artifacts/sample/ | The mock 20-asset, 24-month panel from the Part 3 zip. Only used for smoke tests. | fixture |
| scripts/ | Runnable entry points: data check, artifact check, sample pipeline. | shared |
| tests/ | Unit tests for the shared code. | shared |
| _incoming/ | The original zips, kept for provenance. Not committed. | shared |

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
- Run make test, make check-data and make check-artifacts before asking for a
  review.
- Report numbers are only quoted from part4_evaluation/reports/, never from an
  ad-hoc notebook cell.
- Record generated reports as tag directories; a tag is never overwritten by a
  later run, because a number in the slides must stay reproducible.

## Getting a working copy

The repository is private: a collaborator needs an invite from the owner
before cloning, and then clones with their own credentials.  Nothing else in
the process is user specific.

~~~bash
git clone https://github.com/ShenYouSOTA/sta4020-group-project.git
cd sta4020-group-project
make setup
# copy the raw data into data/, then:
make check-data && make test && make sample
~~~

If a fresh clone cannot write to .git because the directory was created by a
different user, that is a local ownership problem, not a project one; fix the
ownership of the clone rather than adding per-machine paths to the code.
