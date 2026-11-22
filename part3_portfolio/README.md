# Part 3 - portfolio construction

English | [简体中文](README.zh-CN.md)

Part3.py builds five long-only portfolios per rebalancing month from the forecast
panel (Part 1) and the covariance panel (Part 2), and writes the weights that
Part 4 evaluates.

## Changed from the delivered version

- Paths are arguments with repository-relative defaults, not file names read
  from the working directory. The script therefore behaves the same from any
  directory and on any machine.
- The optimiser settings are arguments instead of module-level globals, so a
  sensitivity run does not need a code edit.
- It no longer writes Performance_Summary.csv: those numbers ignored
  transaction costs and never compared against 1/N, so a table with the four
  required metrics exists only in the Part 4 report. The console summary is a
  sanity print, not a result.
- Missing inputs are reported by name instead of raising a bare file error, and
  an incomplete covariance matrix names the offending asset and date.

The five methods and their objectives are unchanged.

## Usage

~~~bash
uv run python part3_portfolio/Part3.py               # real artifacts
uv run python part3_portfolio/Part3.py \
    --expected artifacts/sample/P1_Expected_Returns.csv \
    --covariance artifacts/sample/P2_Covariance.csv \
    --actual artifacts/sample/Actual_Returns.csv \
    --output-dir /tmp/part3                          # mock artifacts
~~~

Defaults: expected returns from artifacts/part1/P1_Expected_Returns.csv (the
current FM forecast, also used by Part 4), covariance from
artifacts/part2/P2_Covariance.csv, realised returns from
artifacts/part1/Actual_Returns.csv, outputs to artifacts/part3/.

The main forecast applies the vendor blacklist and untradable flags at each
month's last trading close. For a custom forecast, pass `--tradability-data`
to both Part 3 and Part 4. Use `--max-weight 0.10` to reproduce the interim
single-asset weight cap.

## Outputs

| File | Columns | Consumer |
| --- | --- | --- |
| Portfolio_Weights.csv | Date, Model, Asset, Weight | Part 4 |
| OOS_Portfolio_Returns.csv | Date, Model, Portfolio_Return | reconciliation only |
| Forecast_Portfolio_Metrics.csv | Date, Model, Expected_Return, Expected_Volatility | forecast diagnostics |
| Tradability_Diagnostics.csv | Date, Excluded_Assets | produced when vendor flags are applied |

Weights are long only and sum to one per model per date. Costs, the 1/N
benchmark and all statistical tests belong to Part 4.
