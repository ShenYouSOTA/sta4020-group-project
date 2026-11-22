# STA4020 期末小组项目

[English](README.md) | 简体中文

本项目包含四个部分：预期收益预测（Part 1）、风险结构估计（Part 2）、投资组合构建（Part 3）与样本外评估（Part 4）。每位成员负责一部分（各占 25%）；最终幻灯片与报告按小组统一评分。

截止时间、产物契约、任务分工与风险清单见[工程计划](docs/PLAN.zh-CN.md)。所有命令均从仓库根目录运行，代码中的路径均相对于根目录解析。

## 环境与初始化

- 仅需安装 [uv](https://docs.astral.sh/uv/)（自动获取 Python ≥ 3.11 并同步 [uv.lock](uv.lock)）。
- 通过 `uv add` 或 `uv lock` 更新依赖。

~~~bash
uv sync    # 可选；`uv run` 每次运行会自动同步环境
~~~

## 快速开始

~~~bash
uv run pytest                    # 共享代码单元测试
uv run sta4020-sample            # 20 只股票、24 个月模拟面板冒烟测试 -> part4_evaluation/reports/sample/REPORT.md
uv run sta4020-check-data        # 检查原始数据文件
uv run sta4020-check-artifacts   # 检查 Part 1 与 Part 2 CSV 契约
~~~

使用 Part 1 预测与本地课程数据复现中期回测（因子模型需支持 Deflate64 的 `unzip` 及约 2.6 GiB 临时空间）：

~~~bash
uv run --extra risk sta4020-build-risk --method factor
uv run python part3_portfolio/Part3.py --max-weight 0.10 --output-dir artifacts/part3/run1
uv run sta4020-check-artifacts --weights artifacts/part3/run1/Portfolio_Weights.csv
uv run sta4020-evaluate --tag run1 --cost-bps 10 --weights artifacts/part3/run1/Portfolio_Weights.csv
~~~

- **协方差对比：** 将 `sta4020-build-risk` 的 `--method` 改为 `sample` 或 `ledoit-wolf` 并指定 `--output`，再通过 `--covariance` 传给 Part 3，使用独立的输出目录与报告标签。
- **可交易性：** 主预测默认在 Part 3 与 Part 4 应用月末交易限制；自定义预测可在两端同时传入 `--tradability-data`。
- **成本敏感性：** 默认开启 `--cost-sweep 0,10,30,50`；传入 `--cost-sweep ''` 可跳过。

## 期末实验

将数据放入 `data/` 后从仓库根目录运行。`final` 扩展包含 Part 1 日频特征所需的 `h5py`。若已有解压的描述变量文件，可传入 `--descriptors /path/to/descriptors.pkl`。

~~~bash
OPENBLAS_NUM_THREADS=1 uv run --locked --extra risk --extra final python -m sta4020_project.final_pipeline
uv run --locked --extra risk --extra final pytest tests part2_risk_model/tests
typst compile --root . docs/final_report.typ part4_evaluation/reports/final/Final_Report.pdf
typst compile --root . docs/final_slides.typ part4_evaluation/reports/final/Final_Slides.pdf
~~~

重跑时使用新标签（如 `--tag final-recheck`），编译 Typst 时传入 `--input tag=final-recheck`。产物与清单保存在 `part4_evaluation/reports/final/`，实验规则见[期末实验设计](docs/FINAL_EXPERIMENT_DESIGN.md)。

## 原始数据

`data/` 不纳入版本控制（530 MB 课程数据）。复制文件至 `data/` 后运行 `uv run sta4020-check-data`，文件格式见[数据说明](data/README.zh-CN.md)。`price.h5` 需要 `h5py`（已包含在 `final` 扩展中，或运行 `uv add h5py`）。

## 目录一览

| 路径 | 用途 | 负责人 |
| --- | --- | --- |
| `data/` | 原始数据（不提交）。 | 共享 |
| `docs/` | 项目要求、课程幻灯片、工程计划、报告与展示源码。 | 共享 |
| `part1_return_model/` | FM 与树模型 notebook；见 [Part 1 指南](part1_return_model/README.md)。 | Part 1 |
| `part2_risk_model/` | 随仓库附带的 Part 2 软件包（`risk_model`）、测试与规格；见 [PROVENANCE.md](part2_risk_model/PROVENANCE.md)。 | Part 2 |
| `part3_portfolio/` | 组合构建命令行脚本（`Part3.py`）；见[组合构建指南](part3_portfolio/README.zh-CN.md)。 | Part 3 |
| `part4_evaluation/` | Part 4 评估输出（按标签存放 `tables/`、`figures/`、`REPORT.md`，不提交）。 | Part 4 |
| `src/sta4020_project/` | 分层包：`shared/`（契约、数据、描述变量缓存、可交易性、配置）、`part1/`、`part2/`、`part4/` 与 `pipeline/`。 | 共享 |
| `artifacts/part1/` | Part 1 输出：预期收益、实际收益与候选股票池。 | Part 1 |
| `artifacts/part2/` | Part 2 输出：`P2_Covariance.csv`。 | Part 2 |
| `artifacts/part3/` | Part 3 输出：`Portfolio_Weights.csv`。 | Part 3 |
| `artifacts/sample/` | 20 只股票、24 个月模拟面板（仅用于冒烟测试）。 | 测试数据 |
| `tests/` | 共享代码单元测试。 | 共享 |
| `_incoming/` | 原始交付压缩包（不提交）。 | 共享 |

所有任务均通过 [pyproject.toml](pyproject.toml) 的 `[project.scripts]` 或 `uv run python <file>` 执行。

## 各部分交付物

各部分仅通过[工程计划](docs/PLAN.zh-CN.md#3-产物接口)中定义的四个 CSV 契约交互：

- **Part 1** → `artifacts/part1/P1_Expected_Returns.csv`（FM 预测）、`Actual_Returns.csv`、`P1_Candidate_Universe.csv`
- **Part 2** → `artifacts/part2/P2_Covariance.csv`
- **Part 3** → `artifacts/part3/Portfolio_Weights.csv`
- **Part 4** → `part4_evaluation/reports/TAG/REPORT.md` 及配套表格与图表

## 协作约定

- 每部分使用独立分支，通过 Pull Request 合入 `main`；跨部分边界改动需核验产物契约。
- 不提交 `data/` 与 `_incoming/`。
- 提交审查前运行 `uv run pytest`、`uv run sta4020-check-data` 与 `uv run sta4020-check-artifacts`。
- 报告数值仅引用 `part4_evaluation/reports/` 下的输出。
- 每次评估使用独立的运行标签目录，保证结果可复现。
- **双语文档：** 英文为默认入口，简体中文版使用 `.zh-CN.md` 后缀。修改命令、路径或接口时同步更新双语文档；上游文档、课程资料及自动生成报告保持原样。

## 克隆与初始化

~~~bash
git clone https://github.com/ShenYouSOTA/sta4020-group-project.git
cd sta4020-group-project
uv sync
# 将原始数据复制到 data/ 后：
uv run sta4020-check-data && uv run pytest && uv run sta4020-sample
~~~
