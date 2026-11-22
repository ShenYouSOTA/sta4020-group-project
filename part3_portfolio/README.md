# Part 3 - Portfolio Construction

English | [简体中文](README.zh-CN.md)

`Part3.py` builds five long-only portfolios per rebalancing month from Part 1 expected returns and Part 2 covariances, writing weights for Part 4 evaluation.

## Changes from Delivered Version

- CLI arguments use repository-relative defaults instead of working-directory filenames or module globals.
- Removed `Performance_Summary.csv`; formal metrics, transaction costs, and the 1/N benchmark live in Part 4.
- Validates missing inputs and incomplete covariance blocks with explicit asset/date diagnostics.
- Five portfolio objectives remain unchanged.

## Usage

~~~bash
uv run python part3_portfolio/Part3.py               # real artifacts
uv run python part3_portfolio/Part3.py \
    --expected artifacts/sample/P1_Expected_Returns.csv \
    --covariance artifacts/sample/P2_Covariance.csv \
    --actual artifacts/sample/Actual_Returns.csv \
    --output-dir /tmp/part3                          # mock artifacts
~~~

Defaults: `artifacts/part1/P1_Expected_Returns.csv`, `artifacts/part2/P2_Covariance.csv`, `artifacts/part1/Actual_Returns.csv`, output to `artifacts/part3/`.

The main forecast applies month-end vendor blacklist and untradable flags; pass `--tradability-data` to both Part 3 and Part 4 for custom forecasts. Use `--max-weight 0.10` for the 10% single-name cap.

## Outputs

| File | Columns | Consumer |
| --- | --- | --- |
| `Portfolio_Weights.csv` | Date, Model, Asset, Weight | Part 4 |
| `OOS_Portfolio_Returns.csv` | Date, Model, Portfolio_Return | reconciliation only |
| `Forecast_Portfolio_Metrics.csv` | Date, Model, Expected_Return, Expected_Volatility | forecast diagnostics |
| `Tradability_Diagnostics.csv` | Date, Excluded_Assets | generated when vendor flags are active |

Weights are long-only and sum to 1 per `(Date, Model)`. Part 4 handles costs, 1/N, and statistical tests.
