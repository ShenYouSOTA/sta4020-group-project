# 新增描述变量数据（`data/addition`）评估与接入方案

[English](ADDITION_DATA_ASSESSMENT.md) | 简体中文

评估对象：`group-project/data/addition/descriptors.zip`（609 MB，含 `descriptors.pkl`，解压后 2,778,987,650 字节 ≈ 2.59 GiB）。

## 0. 结论

1. **与现有面板同源。** `mktcap` 与 `data/mcap.pkl` 逐格一致（9,575 组配对，比值中位数及 5%/95% 分位均为 1.0000，对数相关 1.00000）。
2. **基本面按公告期更新。** 基本面字段集中于财报公告月更新（4/8/10 月高峰，1/6/12 月 ≈ 0）；价格字段与 `data/monthly_returns.pkl` 同月对齐（同月相关 0.9488，滞后一月 -0.0001）。供应商重述回填口径未文档化。
3. **主要收益在 Part 2。** 补充纯价格数据缺失的价值、质量与杠杆风格暴露。
4. **Part 2 样本前窗口。** `forecast_risk` 截断至 `as_of`，故 2014-12-31 仅用此前数据。50 只股票最长不间断平衡区间始于 2012-10（27 个月）；2010-01 起完整者仅 15 只。**方案 A** 采用 2013-01 起 50 只平衡面板扩展窗口（首期 24 个月）；**方案 B** 自 2005 年起在宽截面估计因子收益（§4.1）。
5. **Part 1 约束扩展。** 在现有 11 个特征外预先登记至多 15 个文献先验候选，全部滞后一月（§4.2），沿用 72 月滚动窗、Rank IC 与 BY 流程。
6. **无行业分类。** 213 个字段均不含行业代码，行业块退化为单一市场截距（`PLAN.zh-CN.md` 风险 R2）。
7. **退市股处理（`300330.SZ`）。** 2023-04 收益 -0.5701，2023-05 为 +0.0515，2023-06 起恒为 0（`data/mcap.pkl` 自 2023-06 起为 NaN）。协方差保持 `N = 50`，组合权重自 2023-05 起置 0。
8. **覆盖分级（50 只 × 116 月）。** A 档 163 个、B 档 31 个、C 档 10 个、D 档 9 个。非 A 档风格输入（B 档 `idios_vol_ff3_21`、`turnover_252`；C 档 `dividendyield2`）按 §4.1 规则处理。
9. **不纳入 git。** `.gitignore` 已忽略 `data/*`，仅提交派生面板与重建脚本。

## 1. 数据形态

| 项 | 说明 |
| --- | --- |
| 容器 | ZIP，Deflate64（方法 9）；使用 Info-ZIP `unzip` 或 `7z` 解压（Python `zipfile` 与 `bsdtar` 不支持）。 |
| 体积 | 解压后 2,778,987,650 字节；`pd.read_pickle` 峰值内存约 2.89 GB。 |
| 结构 | `collections.OrderedDict`（213 个键），值为 `float64` `pandas.Series`，MultiIndex 为 `('date','asset')`。 |
| 股票 | 6,128 只（`000001.SZ`、`600000.SH`）。 |
| 时间 | 321 个月末**交易日**（1999-12-30 至 2026-08-31）。 |
| 字段族 | 动量/波动（`momentum_21`、`momentum_academic_252_21`、`long_term_reversal_756`、`total_vol_21/63`、`idios_vol_ff3_21`、`market_beta_252`、`illiq_252`、`turnover_252`、`zero_return_ratio_252`）；规模/价值（`mktcap`、`total_mv`、`[close]`、`book_value_to_total_mktcap_mrq`、`net_profit_to_total_mktcap_ttm`、`dividendyield2`）；质量/盈利（`gross_profit_to_asset_ttm`、`return_on_invested_capital_ttm`、`accrual_to_asset_ttm`）；成长（`revenue_yoy_pct_chg`）；杠杆/流动性（`total_liab_to_total_asset_mrq`、`current_ratio_mra`）；评分卡（`altman_zscore`、`fscore`、`graham_score`、`dechow_score`）；分析师（`west_eps_fy1`、`rating_avg`、`revisions_in_analyst_earnings_forecasts`）。 |
| 行业标签 | 无。 |

### 1.1 日历对齐

`artifacts/part1/P1_Expected_Returns.csv` 使用**日历**月末（2014-12-31 … 2024-07-31，116 行），描述变量使用当月**最后交易日**。按日期等值连接仅命中 78/116，映射至 `Period('M')` 后命中 116/116。接入层以 `(月份, 资产)` 为键。

## 2. 一致性核验

| 核验 | 方法 | 结果 | 含义 |
| --- | --- | --- | --- |
| 同源性 | `descriptors['mktcap']` 与 `data/mcap.pkl` 按月对比 | 9,575 组配对；比值中位数及 p05/p95 = 1.0000；对数相关 1.00000 | 同管线、同单位。 |
| 月份标签 | `[close]` 月环比与 `data/monthly_returns.pkl`（同月 vs 滞后一月） | 9,525 组配对；同月相关 0.9488，**滞后一月 -0.0001**，绝对差中位数 0.00000 | 第 t 月描述变量包含第 t 月收益，第 t 月末收盘可知。 |
| 时点性 | 2015–2024 每月发生变化的股票占比 | `book_value_mrq`：4 月 0.524、8 月 0.554、10 月 0.508、3 月 0.126、5 月 0.222、1/6/12 月 ≈ 0.001；`net_profit_q`：0.518 / 0.552 / 0.503 | 基本面按公告期更新，非按报表期末。 |

基本面按公告月更新，规避了报表期末直接前视；重述回填情况未文档化（§7），`PLAN.zh-CN.md` 风险 R5 保持打开。

目标面板无 `inf`，A/B 档月度横截面标准差均大于 0；横截面 `|z|` 的 99.9 分位可达 ~7（`total_accrual_to_net_profit_ttm` 6.9、`return_on_invested_capital_ttm` 7.1），接入时须缩尾。

## 3. 覆盖与缺口

### 3.1 预测日历内

目标面板：50 只（`artifacts/part1/P1_Candidate_Universe.csv`）× 116 月 = 5,800 格。

| 档位（判据） | 字段数 | 处置 |
| --- | --- | --- |
| A：覆盖 ≥ 95%、有限值、各月离散度为正 | 163 | 直接使用 |
| B：覆盖 90–95% | 31 | 横截面中位数填补并记录填补率 |
| C：覆盖 50–90% | 10 | 仅用于稳健性检验 |
| D：覆盖 < 50% | 9 | 弃用 |

逐字段明细见 `artifacts/addition/desc_field_coverage.csv`（`first_valid_month` 针对预测日历，`first_valid_month_full` 针对全文件）。

三类缺口：

1. **退市：** `300330.SZ` 在 2023-05 … 2024-07 共 15 个月无描述变量（49/50 只可观测，最高覆盖 5,785/5,800 = 0.997414）。
2. **价格类字段逐股缺失：** `total_vol_21` 仅 3/50 只全期完整（`300149.SZ` 缺 24 个月）；缺失率从 2015 年 13.7%、2016 年 14.5% 降至 2019 年后约 1%，与零收益仅重合 3.9%。
3. **分析师字段：** 覆盖率 38%–43%（D 档，虽始于 2004–2013 年仍弃用）。

### 3.2 样本前窗口（Part 2）

| 截至 2014-12 窗口 | 收益完整股票数（/50） |
| --- | --- |
| 自 2005-01 | 12 |
| 自 2010-01 | 15 |
| 自 2012-01 | 40 |
| 自 2012-10 | 50（27 个月，最长平衡区间） |

最晚上市股（`300354.SZ`）始于 2012-10。在 2012-10 … 2014-11（`presample_coverage`）上：基本面输入 1.000、`momentum_21` 0.953、`idios_vol_ff3_21` 0.945、`turnover_252` 与 `market_beta_252` 0.916、`momentum_academic_252_21` 0.892（213 字段中位数 0.987）。

## 4. 接入方案

### 4.1 层一：Part 2 风格暴露

`RiskPanel` 契约（`part2_risk_model/src/risk_model/factor_model.py:11-19`，校验 `:30-53`，标准化 `:64-69`）与 `forecast_risk`（`risk_model.py:21`）：

- 平衡面板、有限值、`T >= 2`、`market_caps > 0`、每只股票属单一非空行业。
- 包内标准化：市值加权去中心后除以等权横截面标准差（`ddof=1`）。

**标准化规则：** 包内变换对月度正仿射变换 `a_t + b_t·x`（`b_t > 0`）不变，单字段不做外部 z-score：

- **单字段风格：** 传入变换后原始值（按表取对数、缩尾、定方向）。
- **合成风格：** 各分量先缩尾、月内 z-score 并定方向，再对可用分量等权平均。
- **缩尾：** 每月截断于 `中位数 ± 5 × 1.4826 × MAD`。

**八个风格（Q = 8）：** `N = 50` 时每月截面回归保留 41 个自由度。

| 风格 | 字段 | 档位 | 处理 |
| --- | --- | --- | --- |
| Size | `mktcap` | A | 取对数 |
| Value | `book_value_to_total_mktcap_mrq`、`net_profit_to_total_mktcap_ttm` | A, A | 合成（`dividendyield2` C 档作稳健性） |
| Momentum | `momentum_academic_252_21` | A | 直接使用 |
| Short-term reversal | `momentum_21` | A | 取负 |
| Volatility | `idios_vol_ff3_21` | B | 直接使用 |
| Liquidity | `turnover_252` | B | 取对数（`illiq_252` 作稳健性） |
| Quality | `return_on_invested_capital_ttm`、`gross_profit_to_asset_ttm`、`accrual_to_asset_ttm` | A, A, A | 合成；应计取负 |
| Leverage | `total_liab_to_total_asset_mrq` | A | 直接使用 |

稳健性候选：`market_beta_252`、`revenue_yoy_pct_chg`、`dividendyield2`、`illiq_252`。

**方案 A（中期）：** 50 只股票，2013-01 至 2024-07，超额收益（`monthly_returns.pkl` 减 `risk_free.csv`），扩展窗口调用 `forecast_risk(panel, as_of=t)`（首期 24 行 / 23 个因子收益），单一行业，对照样本与 Ledoit–Wolf 协方差。

**方案 B（期末）：** 自 2005 年起在市值前 800 只正市值股票上通过 `fit_factor_model` 估计月度因子收益，再用 `stable.estimate_factor_covariance` 与 `integration.compute_asset_covariance` 结合 50 只残差方差组装协方差。

**缺口规则：**
- 风格逐股缺失：月内横截面中位数填补，按风格/月记录填补率。
- `300330.SZ` 自 2023-05 起：市值与风格前值填充以保持 `N = 50`；冻结退市前特异方差；通过 `UNTRADABLE` 掩码将组合权重置 0。

### 4.2 层二：Part 1 特征扩展

1. 在现有 11 个特征外预先登记至多 15 个文献先验候选（价值、盈利、投资、应计、杠杆），BY 检验总数 ≤ 26。
2. 所有描述变量滞后一月：第 t 月描述变量于第 t 月末收盘可知，而信号在倒数第二个交易日收盘生成（`part1_return_model/logic_readme.md` §1）；不重复加入价量描述变量。
3. 在全 A 股宽截面训练（首个 72 月窗口 2008-11 至 2014-11），入模前核验覆盖率。
4. 沿用中心值（0）缺失填补，并报告高覆盖年份敏感性。

在 11 个价量特征基础上补充基本面价值、质量与应计维度。

### 4.3 层三：Part 4 风险分解与归因

- **风险分解：** 拆分预测方差为因子与特异风险，通过 Mincer–Zarnowitz 回归与 Q(6) 检验对比实现波动。
- **风格归因：** 将组合月度主动收益对八个风格因子收益回归。

### 4.4 弃用字段

- 分析师字段（`west_eps_fy1`、`rating_avg`、`revisions_*`）：D 档（覆盖 < 50%）。
- `free_cash_flow_yoy_pct_chg`：日历内覆盖 19%，样本前缺失。
- 聚类构造行业：缺少真实标签验证，保留单一行业退化设定。
- `graham_score`、`gscore`：C 档（覆盖 55%–70%），仅作稳健性检验。

## 5. 验收门槛

1. 加载器 3 分钟内重建面板并复现 `artifacts/addition/desc_field_coverage.csv`。
2. 风格面板通过 `RiskPanel` 校验（有限值、`market_caps > 0`、单一行业、每月离散度为正）。
3. 116 个月内风格两两月度 `|ρ|` 中位数 < 0.7，各风格 VIF < 5。
4. Part 2 无前视（基准日 `t` 的协方差不受 `t` 之后扰动影响）。
5. `artifacts/part2/P2_Covariance.csv` 通过 `sta4020-check-artifacts`，逐月正定，前 5 特征值占比 < 95%，对角线与实现个股方差同量级。
6. Part 1 在相同 116 月 × 50 只池上对比基线（11）与扩展（11 + ≤ 15）的 Rank IC、ICIR 与相对 1/N 的样本外表现。
7. 报告写明 R2（无行业）、方案 A 早期历史短、`300330.SZ` 处理、缩尾与填补规则及 PIT 证据与局限。

## 6. 里程碑步骤

| 步骤 | 产出 | 预估 |
| --- | --- | --- |
| 1. 加载层 | `src/sta4020_project/descriptors.py` 及对齐/同源测试 | 0.5 天 |
| 2. 风格层 | 8 风格、缩尾、`300330.SZ` 前值填充 -> `artifacts/addition/style_panel.npz` | 1 天 |
| 3a. 风险 A | 扩展 `forecast_risk` + 样本/Ledoit–Wolf -> `artifacts/part2/P2_Covariance.csv` | 1 天 |
| 4. 组合与评估 | Part 3 加掩码 + Part 4 `interim` 标签 | 0.5 天 |
| 3b. 风险 B | 宽截面因子收益 + A/B 对比 | 1 天 |
| 5. 收益扩展 | 预登记滞后一月扩展实验 | 1 天 |
| 6. Part 4 分解 | 因子/特异拆分 + 风格归因 | 0.5 天 |
| 7. 文档 | 计划风险表与报告局限章节 | 0.5 天 |

## 7. 局限性

1. **无行业标签：** 行业轮动并入市场风险。
2. **早期历史短（方案 A）：** 初期仅约两年 50 股因子收益（由方案 B 改善）。
3. **重述口径未文档化：** 公告月更新已验证，但是否存在历史重述回填无法排除。
4. **早期覆盖不均：** 价格字段在 2015–2017 年缺失 12%–15%。
5. **固定池退市股：** `300330.SZ` 自 2023-05 起在策略与 1/N 中权重均为 0。
6. **压缩格式：** 609 MB Deflate64 ZIP（解压 2.59 GiB）依赖 `unzip` 或 `7z`。
7. **单一数据源：** `mktcap` 与 `mcap.pkl` 完全一致，共用同一供应商口径。

## 附录 A：复现命令

~~~bash
unzip -o data/addition/descriptors.zip -d "$HOME/.cache/sta4020/"

.venv/bin/python tools/desc_field_coverage.py \
  --descriptors "$HOME/.cache/sta4020/descriptors.pkl" \
  --universe artifacts/part1/P1_Candidate_Universe.csv \
  --calendar artifacts/part1/P1_Expected_Returns.csv \
  --history-start 2012-10 \
  --out artifacts/addition/desc_field_coverage.csv
~~~
