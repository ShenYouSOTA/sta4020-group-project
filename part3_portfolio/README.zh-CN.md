# 第 3 部分：投资组合构建

[English](README.md) | 简体中文

`Part3.py` 根据预测面板（第 1 部分）和协方差面板（第 2 部分），在每个再平衡月份构建五个纯多头投资组合，并输出供第 4 部分评估的权重。

## 与原交付版本相比的变更

- 路径通过参数指定，默认值相对于仓库根目录，不再从当前工作目录按文件名读取。因此，无论在哪个目录或哪台机器上运行，脚本的行为都一致。
- 优化器设置改为通过参数传入，不再使用模块级全局变量，因此进行敏感性分析时无需修改代码。
- 不再生成 `Performance_Summary.csv`。该文件中的数值未计入交易成本，也没有与 1/N 基准比较，因此包含四项必需指标的表格仅在第 4 部分的报告中提供。控制台摘要只用于快速检查，不作为正式结果。
- 缺少输入时，脚本会指出缺失的输入名称，而不是只抛出文件错误；协方差矩阵不完整时，会指出对应的资产和日期。

五种方法及其优化目标均保持不变。

## 用法

~~~bash
uv run python part3_portfolio/Part3.py               # real artifacts
uv run python part3_portfolio/Part3.py \
    --expected artifacts/sample/P1_Expected_Returns.csv \
    --covariance artifacts/sample/P2_Covariance.csv \
    --actual artifacts/sample/Actual_Returns.csv \
    --output-dir /tmp/part3                          # mock artifacts
~~~

默认设置：预期收益率取自 `artifacts/part1/P1_Expected_Returns.csv`（新版 FM 预测，与第 4 部分默认一致）；协方差取自 `artifacts/part2/P2_Covariance.csv`；实际收益率取自 `artifacts/part1/Actual_Returns.csv`；输出写入 `artifacts/part3/`。

主预测按每月最后一个交易日收盘的黑名单和不可交易标记筛选资产。自定义预测可在 Part 3 和 Part 4 同时传入 `--tradability-data`。使用 `--max-weight 0.10` 可复现中期实验的单股权重上限。

## 输出

| 文件 | 列 | 用途 |
| --- | --- | --- |
| Portfolio_Weights.csv | Date, Model, Asset, Weight | 供第 4 部分使用 |
| OOS_Portfolio_Returns.csv | Date, Model, Portfolio_Return | 仅供核对 |
| Forecast_Portfolio_Metrics.csv | Date, Model, Expected_Return, Expected_Volatility | 用于预测诊断 |
| Tradability_Diagnostics.csv | Date, Excluded_Assets | 启用交易限制时生成 |

投资组合不做空，且每个日期、每个模型的权重之和均为 1。交易成本、1/N 基准和所有统计检验均由第 4 部分处理。
