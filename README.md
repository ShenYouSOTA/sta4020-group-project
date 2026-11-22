# STA4020 Final Project

English | [简体中文](README.zh-CN.md)

Four-part quantitative equity project: return forecasting (Part 1), risk modeling (Part 2), portfolio construction (Part 3), and out-of-sample evaluation (Part 4). Each part represents 25% individual work; the final slides and report are graded as a group.

See [docs/PLAN.md](docs/PLAN.md) for deadlines, artifact contracts, work breakdown, and risks. Run all commands from the repository root; all code resolves paths relative to it.

## Requirements & Setup

- [uv](https://docs.astral.sh/uv/) (automatically provisions Python ≥ 3.11 and syncs `uv.lock`).
- Update dependencies via `uv add` or `uv lock`.

~~~bash
uv sync    # optional; `uv run` syncs automatically
~~~

## Quick Start

~~~bash
uv run pytest                    # unit tests for shared code
uv run sta4020-sample            # smoke test on 20-asset, 24-month mock panel -> part4_evaluation/reports/sample/REPORT.md
uv run sta4020-check-data        # verify raw data files
uv run sta4020-check-artifacts   # validate Part 1 and Part 2 CSV contracts
~~~

Reproduce the interim run using Part 1 forecasts and course data (factor risk requires `unzip` with Deflate64 support and ~2.6 GiB temp space):

~~~bash
uv run --extra risk sta4020-build-risk --method factor
uv run python part3_portfolio/Part3.py --max-weight 0.10 --output-dir artifacts/part3/run1
uv run sta4020-check-artifacts --weights artifacts/part3/run1/Portfolio_Weights.csv
uv run sta4020-evaluate --tag run1 --cost-bps 10 --weights artifacts/part3/run1/Portfolio_Weights.csv
~~~

- **Covariance comparison:** rerun `sta4020-build-risk` with `--method sample` or `--method ledoit-wolf` and a distinct `--output`, then pass `--covariance` to Part 3 with a separate output directory and tag.
- **Tradability:** the main forecast applies local month-end vendor flags in Parts 3 and 4; pass `--tradability-data` to both for custom forecasts.
- **Cost sensitivity:** `--cost-sweep 0,10,30,50` is enabled by default; pass `--cost-sweep ''` to skip.

## Final Experiment

Run from the repository root with course data in `data/`. The `final` extra includes `h5py` for Part 1 daily features. Pass `--descriptors /path/to/descriptors.pkl` to reuse an extracted copy.

~~~bash
OPENBLAS_NUM_THREADS=1 uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline
uv run --locked --extra risk --extra final pytest tests part2_risk_model/tests
typst compile --root . docs/final_report.typ part4_evaluation/reports/final/Final_Report.pdf
typst compile --root . docs/final_slides.typ part4_evaluation/reports/final/Final_Slides.pdf
~~~

Use a new tag (e.g. `--tag final-recheck`) for reruns, and pass `--input tag=final-recheck` when compiling Typst. Outputs and manifests live in `part4_evaluation/reports/final/`. See [docs/FINAL_EXPERIMENT_DESIGN.md](docs/FINAL_EXPERIMENT_DESIGN.md) for experiment rules.

## Raw Data

`data/` is excluded from git (530 MB course payload). Copy the files into `data/` and run `uv run sta4020-check-data`. See [data/README.md](data/README.md) for the schema. `price.h5` requires `h5py` (included in `--extra final`, or `uv add h5py`).

## Directory Map

| Path | Description | Owner |
| --- | --- | --- |
| `data/` | Raw vendor data (untracked). | shared |
| `docs/` | Project guidelines, lecture slides, plan, report/slide sources. | shared |
| `part1_return_model/` | FM and tree notebooks; see [Part 1 guide](part1_return_model/README.md). | Part 1 |
| `part2_risk_model/` | Vendored risk model package (`risk_model`), tests, and spec; see [PROVENANCE.md](part2_risk_model/PROVENANCE.md). | Part 2 |
| `part3_portfolio/` | Portfolio construction CLI (`Part3.py`); see [portfolio guide](part3_portfolio/README.md). | Part 3 |
| `part4_evaluation/` | Evaluation outputs (`tables/`, `figures/`, `REPORT.md` per tag, untracked). | Part 4 |
| `src/sta4020_project/` | Layered package: `shared/` (contracts, data, descriptors, tradability, config), `part1/`, `part2/`, `part4/`, and `pipeline/`. | shared |
| `artifacts/part1/` | Part 1 outputs: expected returns, actual returns, candidate universe. | Part 1 |
| `artifacts/part2/` | Part 2 output: `P2_Covariance.csv`. | Part 2 |
| `artifacts/part3/` | Part 3 output: `Portfolio_Weights.csv`. | Part 3 |
| `artifacts/sample/` | 20-asset, 24-month mock panel for smoke tests. | fixture |
| `tests/` | Unit tests for shared code. | shared |
| `_incoming/` | Original delivery archives (untracked). | shared |

Tasks run via `[project.scripts]` in `pyproject.toml` or `uv run python <file>`.

## Part Deliverables

Parts communicate solely through four CSV contracts defined in [docs/PLAN.md](docs/PLAN.md):

- **Part 1** -> `artifacts/part1/P1_Expected_Returns.csv` (FM forecast), `Actual_Returns.csv`, `P1_Candidate_Universe.csv`
- **Part 2** -> `artifacts/part2/P2_Covariance.csv`
- **Part 3** -> `artifacts/part3/Portfolio_Weights.csv`
- **Part 4** -> `part4_evaluation/reports/TAG/REPORT.md` plus tables and figures

## Working Agreement

- Use one branch per part and merge via PR to `main`; check artifact contracts on boundary changes.
- Keep `data/` and `_incoming/` out of git.
- Run `uv run pytest`, `uv run sta4020-check-data`, and `uv run sta4020-check-artifacts` before requesting review.
- Quote report numbers only from `part4_evaluation/reports/`.
- Write each evaluation run to a distinct tag directory to keep reported numbers reproducible.
- **Bilingual docs:** English is primary; Simplified Chinese counterparts use `.zh-CN.md`. Sync both when updating commands, paths, or interfaces. Leave upstream docs, course materials, and generated reports unchanged.

## Clone & Initialize

~~~bash
git clone https://github.com/ShenYouSOTA/sta4020-group-project.git
cd sta4020-group-project
uv sync
# copy raw data into data/, then:
uv run sta4020-check-data && uv run pytest && uv run sta4020-sample
~~~
