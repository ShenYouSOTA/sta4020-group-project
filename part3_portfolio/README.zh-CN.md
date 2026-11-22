# 第 3 部分：投资组合构建

[English](README.md) | 简体中文

`Part3.py` 基于第 1 部分预期收益与第 2 部分协方差，在每个调仓月构建五个纯多头组合，输出供第 4 部分评估的权重。

## 相对原交付版本的调整

- 命令行参数默认相对于仓库根目录，取代工作目录文件名与模块全局变量。
- 移除 `Performance_Summary.csv`；正式指标、交易成本与 1/N 基准统一由第 4 部分计算。
- 校验缺失输入与不完整协方差块，并输出具体资产与日期诊断。
- 五种组合优化目标保持不变。

## 用法

~~~bash
uv run python part3_portfolio/Part3.py               # 真实产物
uv run python part3_portfolio/Part3.py \
    --expected artifacts/sample/P1_Expected_Returns.csv \
    --covariance artifacts/sample/P2_Covariance.csv \
    --actual artifacts/sample/Actual_Returns.csv \
    --output-dir /tmp/part3                          # 模拟产物
~~~

默认输入：`artifacts/part1/P1_Expected_Returns.csv`、`artifacts/part2/P2_Covariance.csv`、`artifacts/part1/Actual_Returns.csv`；输出至 `artifacts/part3/`。

主预测默认按月末黑名单与不可交易标记筛选资产；自定义预测需在 Part 3 与 Part 4 同时传入 `--tradability-data`。使用 `--max-weight 0.10` 应用 10% 单股权重上限。

## 输出

| 文件 | 列 | 用途 |
| --- | --- | --- |
| `Portfolio_Weights.csv` | Date, Model, Asset, Weight | 第 4 部分输入 |
| `OOS_Portfolio_Returns.csv` | Date, Model, Portfolio_Return | 仅作核对 |
| `Forecast_Portfolio_Metrics.csv` | Date, Model, Expected_Return, Expected_Volatility | 预测诊断 |
| `Tradability_Diagnostics.csv` | Date, Excluded_Assets | 启用交易限制时生成 |

权重纯多头且按 `(Date, Model)` 归一化为 1。交易成本、1/N 基准与统计检验由第 4 部分处理。
