# 工程计划

[English](PLAN.md) | 简体中文

当前状态：中期与期末流程均已在 50 只股票、116 期月度样本外收益上跑通。

## 1. 截止时间

| 里程碑 | 日期 | 权重 | 要求 |
| --- | --- | --- | --- |
| 中期讨论 | 11 月 23 日 – 11 月 27 日 | 20% | 各部分基准结果、端到端运行、期末模型方案（小组自行预约时段）。 |
| 汇报幻灯片 | 12 月 13 日 23:59:59 | 40% | 最终模型、相对 1/N 的样本外结果、归因解读与批判性分析。 |
| 最终报告 + 代码 + 数据 | 12 月 18 日 23:59:59 | 40% | 各部分书面章节、可复现代码及所需数据。 |

本仓库集成流程确保中期与期末结果走同一套代码路径。

## 2. 项目进展

### 数据（齐备）

| 文件 | 内容 | 形状 / 范围 |
| --- | --- | --- |
| `data/monthly_returns.pkl` | 月度简单总收益率，宽表 | 355 x 5378，1995-02 .. 2024-08 |
| `data/price.h5` | 日度复权价格及交易日历 | 324 MB，需 `h5py` |
| `data/mcap.pkl` | 月末市值，宽表 | 356 x 5634 |
| `data/daily_amount.pkl` | 日度成交额 | 186 MB |
| `data/BLACKLIST.pkl`, `data/UNTRADABLE.pkl` | 逐日排除标记 | 日度 |
| `data/FF5.csv` | Fama–French 五因子 | 357 行，截至 2024-09 |
| `data/risk_free.csv` | 日度无风险利率 | 7223 行 |
| `data/zz500.pk` | 中证 500 日行情 | 4346 x 7 |
| `data/addition/descriptors.zip` | 213 个月度描述变量，见[评估文档](ADDITION_DATA_ASSESSMENT.zh-CN.md) | 6128 只，1999-12 .. 2026-08，解压 2.59 GiB |

所有数据均不含行业分类（见风险 R2）。

### Part 1 — 收益率模型

- 资产池：2014-12-30 选定的 50 只固定资产（`artifacts/part1/P1_Candidate_Universe.csv`）；样本外始于 2014-12-31，首期目标月为 2015-01-31。
- `artifacts/part1/P1_Expected_Returns.csv`：116 个预测基准日 x 50 只资产（FM 模型下月简单收益率预测）。
- `artifacts/part1/Actual_Returns.csv`：116 个月实际收益率（2015-01-31 .. 2024-08-31）。
- 运行方式见 [Part 1 指南](../part1_return_model/README.md)；`uv run sta4020-check-artifacts` 核验 0 项契约错误。

### Part 2 — 风险模型

- 样本协方差、Ledoit–Wolf 与八风格因子模型均已生成 116 个正定 50 × 50 协方差块。
- 因子模型 A 基于 50 只资产自 2013-01 起的扩展历史；模型 B 基于自 2005-02 起市值前 800 只股票估计因子收益。两者均采用单一市场行业组。
- 自 2023-05 月末起，活跃截面剔除退市股 `300330.SZ`，并保留其退市前最后特异方差。

### Part 3 — 投资组合构建

- 五种组合在 116 个月内全部运行完成；月末供应商标记排除 0 至 9 只资产（`300330.SZ` 自 2023-05 起权重为 0）。
- 中期 10% 权重上限实验保存在 `artifacts/part3/interim-10pct/`。

### Part 4 — 评估

- 主中期评估位于 `part4_evaluation/reports/interim-10pct/REPORT.md`（10% 权重上限，10 bp 单边成本）；无上限及协方差对照标签为 `interim`、`sample-risk`、`ledoit-wolf`。
- 策略、1/N 基准与归因使用同一可交易池及持仓漂移成本口径。

## 3. 产物接口

各部分通过包含显式 `Date` 列的长表或宽表 CSV 交接，单位统一为月度小数简单收益率。日期对齐 `Actual_Returns.csv` 的日历月末；月末 `t` 的预测对应严格晚于 `t` 的首个实际月末。

| 文件 | 产出方 | 使用方 | 格式 |
| --- | --- | --- | --- |
| `artifacts/part1/P1_Expected_Returns.csv` | Part 1 | Part 3 | 宽表：`Date` + 各资产列（下月预期简单收益率）。 |
| `artifacts/part1/Actual_Returns.csv` | Part 1 | Part 3, Part 4 | 宽表，列相同；`Date` 为收益实现月末。 |
| `artifacts/part1/P1_Candidate_Universe.csv` | Part 1 | 全部 | 50 只资产总名单。 |
| `artifacts/part2/P2_Covariance.csv` | Part 2 | Part 3 | 长表：`Date`, `Asset_1`, `Asset_2`, `Covariance`。每期完整 `N x N` 对称正定块，月度单位。 |
| `artifacts/part3/Portfolio_Weights.csv` | Part 3 | Part 4 | 长表：`Date`, `Model`, `Asset`, `Weight`。纯多头，按 `(Date, Model)` 权重和为 1。 |
| `artifacts/part3/OOS_Portfolio_Returns.csv` | Part 3 | Part 4 | `Date`, `Model`, `Portfolio_Return`（仅核对；Part 4 基于权重重算）。 |

契约规则：

1. 资产池取三个核心文件的交集，至少 20 只资产。
2. 资产代码与 `P1_Candidate_Universe.csv` 完全一致。
3. 收益预测与协方差均采用单月小数单位。
4. 缺失月份直接报错，不填零。
5. 语义变更时新增文件，不改动既有文件含义。

集成提交前运行 `uv run sta4020-check-artifacts` 核验。

## 4. 工作拆解

### Part 1 — 收益率模型

- 记录模型阶梯（历史均值、IC + FM 岭回归、提升树），并核查 2014-12-31 选池环节的前视隔离。

### Part 2 — 风险模型

- 面板适配器从 `monthly_returns.pkl`、`risk_free.csv`、`mcap.pkl` 与 `descriptors.zip` 构造超额收益、市值与八个风格暴露（规则见[评估文档](ADDITION_DATA_ASSESSMENT.zh-CN.md) §4.1）：规模、价值、动量、短期反转、残差波动、流动性、质量、杠杆。
- 方案 A 使用 2013-01 起的 50 只平衡面板扩展窗口（首期 24 个月）；方案 B 自 2005 年起在宽截面估计因子收益。
- 退市股 `300330.SZ` 保持 `N = 50`，沿用最后市值/风格并冻结退市前特异方差。
- 在相同窗口上对比样本协方差、Ledoit–Wolf 与因子模型，以样本外实现波动率与 QLIKE 评价校准度。

### Part 3 — 投资组合构建

- 通过 `uv run python part3_portfolio/Part3.py` 运行，支持 `--max-weight`（如 0.10）、换手惩罚与风险厌恶系数。
- 完成风险厌恶系数（2, 5, 10）与 Black–Litterman 先验（`1/N` vs 市值加权）敏感性分析。
- 应用 `BLACKLIST.pkl` 与 `UNTRADABLE.pkl` 掩码；`300330.SZ` 自 2023-05 起权重为 0。
- 正式指标统一由 Part 4 报告。

### Part 4 — 评估

已实现：契约校验、四项核心指标及 Sortino/Calmar/胜率/换手率、对齐的 `1/N` 基准、Memmel 夏普检验、Newey–West 詹森阿尔法、精确 `gap = signal + timing` 归因、分阶段表格、权重诊断、图表与 Markdown 报告。

待完善分析：

1. 0、10、30、50 bp 成本敏感性与策略排名变化解读（`--cost-sweep`）。
2. 分阶段解读（2015 股灾、2018 去杠杆、2021–2022 回撤、2023–2024），对应至 Part 1–3 建模选择。
3. 归因分析：区分信号倾斜与择时/执行贡献。
4. 权重诊断（有效持仓数、最大权重、换手率）与 Part 2 协方差条件数的关联。
5. 可选：折减夏普比率（Deflated Sharpe Ratio）与现实检验自助法。

**依赖顺序：** `data -> Part 1 产物 -> Part 2 协方差 -> Part 3 权重 -> Part 4 报告`

## 5. 风险

| 编号 | 风险 | 影响 | 缓解措施 |
| --- | --- | --- | --- |
| R1 | A 早期历史偏短；B 采用宽截面市值基准。 | 协方差偏差随市场状态与基准变化。 | 同日历对比样本与 Ledoit–Wolf 估计。 |
| R2 | 缺失行业分类。 | 行业块退化为市场截距。 | 列为局限；依赖八个风格因子。 |
| R3 | 模拟测试集仅 24 个月。 | 不足 60 个月要求。 | 仅作冒烟测试；报告仅引用真实数据生成的 `reports/`。 |
| R4 | 跨部分资产池不一致。 | 权重错配。 | 以 `P1_Candidate_Universe.csv` 为准，`checks.py` 强制交集校验。 |
| R5 | 选池或协方差窗口前视偏差。 | 样本外结论失效。 | 审计窗口边界；基准日 `t` 仅用 `<= t` 数据。 |
| R6 | 不可交易股票进入组合。 | 虚高业绩。 | Part 3 应用掩码；Part 4 报告换手与成本拖累。 |
| R7 | 成本假设过于乐观。 | 高估净收益。 | 在报告与幻灯片展示 0–50 bp 敏感性。 |
| R8 | 中期讨论临近。 | 占总成绩 20%。 | 展示端到端流程与各部分基准指标。 |
| R9 | 可复现性。 | 影响代码评分。 | 锁定 `uv.lock`、单元测试与单命令流水线。 |
| R10 | `300330.SZ` 于 2023 年退市（2023-06 起收益为 0）。 | 最小方差优化器将其视作无风险资产。 | Part 3 与 1/N 自 2023-05 起设权重为 0；Part 2 冻结退市前特异方差。 |
| R11 | A 早期历史短；描述变量重述口径未文档化。 | 早期协方差噪声大；存在潜在回填可能。 | 写入局限；使用模型 B 延长因子历史。 |

## 6. 集成工作流

- 分支 `part1/`、`part2/`、`part3/`、`part4/` 通过 PR 合入 `main`。
- 涉及 `artifacts/` 的 PR 需附 `uv run sta4020-check-artifacts` 输出。
- 每次运行冻结至 `part4_evaluation/reports/<tag>/`，记录配置与清单。
- 在仓库根目录通过 `uv` 执行：

~~~bash
uv run sta4020-check-data
uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline
~~~

## 7. 决策记录

| 日期 | 决策 | 原因 |
| --- | --- | --- |
| 2026-11-21 | 独立设立 `group-project` 仓库。 | 隔离小组交付物与个人课程作业及提交历史。 |
| 2026-11-21 | 直接纳入 `part2_risk_model/`（移除子模块）。 | 评分压缩包会丢失子模块或嵌套 `.git` 目录；来源见 `PROVENANCE.md`。 |
| 2026-11-21 | 默认采用新版 FM 预测与 50 股池。 | 替代旧验证版面板。 |
| 2026-11-21 | 单边交易成本参数化（0、10、30、50 bp）。 | 10 bp 为基准假设，敏感性表展示排名反转阈值。 |
| 2026-11-21 | 报告数值仅取自 `part4_evaluation/reports/`。 | `Part3.py` 未计入成本、1/N 基准与统计检验。 |
| 2026-11-22 | Part 2 接入 `descriptors.zip`；中期用方案 A，期末用方案 B。 | A 无需改包即可跑通；B 将因子历史延长至 2005 年。 |
| 2026-11-22 | Part 1 扩展至多 15 个预先登记、滞后一月的描述变量。 | 避免倒数第二交易日信号前视与 213 字段多重检验过拟合。 |

## 8. 完成标准

- 四个产物通过 `sta4020-check-artifacts` 校验（50 只资产、>= 60 个样本外月份）。
- 汇总表在同一口径下对比各策略与 `1/N` 的四项核心指标。
- 对各策略与 `1/N` 进行正式统计检验，区分统计显著性与经济幅度。
- 包含成本敏感性表与分阶段结果表。
- Part 4 结合 Part 1–3 具体建模选择解释绩效差异。
- 从干净仓库加 `data/` 目录出发可复现全部报告数值。
