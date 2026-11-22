# STA4020 期末小组项目

[English](README.md) | 简体中文

项目分为四部分：预测预期收益（Part 1）、估计风险结构（Part 2）、构建投资组合（Part 3），以及进行样本外评估（Part 4）。每位成员负责一部分，各占 25%；最终展示幻灯片与报告按小组统一评分。

建议先读[工程计划](docs/PLAN.zh-CN.md)，了解截止时间、各部分交换文件的格式约定、任务分工和风险清单。

下面的命令均从仓库根目录运行。代码中的路径也以仓库根目录为基准，不依赖当前工作目录、仓库的位置或运行者的用户名。

## 环境要求

- [uv](https://docs.astral.sh/uv/) 是唯一需要单独安装的工具。如果本机没有符合要求的 Python（3.11 或更高版本），uv 会自动获取。

依赖版本锁定在仓库中的 [uv.lock](uv.lock)：运行依赖包括 NumPy、pandas、SciPy 和 Matplotlib，开发依赖包括 pytest。成员使用同一份锁文件，才便于比较结果。请用 `uv add` 或 `uv lock` 更新依赖，不要手动修改锁文件。

## 初始化

~~~bash
uv sync
~~~

该命令会根据锁文件创建 `.venv`，并以可编辑模式安装项目。这样就能导入 `sta4020_project`，并在该环境中使用下面的命令。`uv run` 每次执行前都会同步环境，也可以跳过这一步直接运行命令。

## 快速开始

~~~bash
uv run pytest                    # 运行共享代码的单元测试
uv run sta4020-sample            # 用模拟文件做端到端冒烟测试
uv run sta4020-check-data        # 检查原始数据文件是否齐全
uv run sta4020-check-artifacts   # 检查 Part 1 和 Part 2 的 CSV 格式
~~~

冒烟测试使用 Part 3 压缩包附带的 20 只股票、24 个月的模拟面板数据运行 Part 3，再将组合权重交给 Part 4 评估，生成 `part4_evaluation/reports/sample/REPORT.md`。这样在真正的 Part 2 和 Part 3 输出就绪之前，就能验证各环节能否衔接起来。

实际输入就绪后，构建并评估真实投资组合：

~~~bash
uv run python part3_portfolio/Part3.py                    # -> artifacts/part3
uv run sta4020-evaluate --tag run1 --cost-bps 10          # -> part4_evaluation/reports/run1
~~~

默认参数 `--cost-sweep 0,10,30,50` 会生成交易成本敏感性分析表；传入 `--cost-sweep ''` 可跳过此表。

## 原始数据

原始数据约 530 MB，由课程资料提供，不纳入版本控制。请将文件复制到 `data/`，保留原文件名，再运行 `uv run sta4020-check-data`。目录结构和文件含义见[数据说明](data/README.zh-CN.md)。只有使用日频数据时才需要读取 `price.h5` 并安装 h5py，因此默认依赖不包含它；如有需要，运行 `uv add h5py`。

## 目录一览

| 路径 | 用途 | 负责人 |
| --- | --- | --- |
| `data/` | 原始数据：5,378 只股票的月收益率、日价格、市值、成交额、黑名单、FF5、无风险利率和中证 500 指数数据。原始文件不提交。 | 共享 |
| `docs/` | 项目要求 PDF 和课程幻灯片。 | 共享 |
| [工程计划](docs/PLAN.zh-CN.md) | 截止时间、接口、分工和风险。 | 共享 |
| `part1_return_model/` | Part 1 的 notebook 和[原始中文说明](part1_return_model/README_PART1_ORIGINAL.md)，按收到的版本保留。 | Part 1 |
| `part2_risk_model/` | 随仓库附带的 Part 2 软件包（`import risk_model`）、测试和规格说明。参见[上游 README（英文）](part2_risk_model/README.md)和[来源说明（英文）](part2_risk_model/PROVENANCE.md)。 | Part 2 |
| `part3_portfolio/` | 投资组合构建脚本，默认在 `artifacts/` 下读写文件。参见[组合构建指南](part3_portfolio/README.zh-CN.md)。 | Part 3 |
| `part4_evaluation/` | Part 4 评估输出；每个运行标签下有 `tables/`、`figures/` 和 `REPORT.md`，生成的文件不提交。 | Part 4 |
| `src/sta4020_project/` | 共享代码：文件格式约定、指标、统计推断、回测引擎、归因、报告、检查和命令行入口。 | Part 4（共享） |
| `artifacts/part1/` | Part 1 输出：预期收益、实际收益和候选股票池。 | Part 1 |
| `artifacts/part2/` | Part 2 输出：`P2_Covariance.csv`。 | Part 2 |
| `artifacts/part3/` | Part 3 输出：`Portfolio_Weights.csv`。 | Part 3 |
| `artifacts/sample/` | Part 3 压缩包中的 20 只股票、24 个月的模拟面板，仅用于冒烟测试。 | 测试数据 |
| `tests/` | 共享代码的单元测试。 | 共享 |
| `_incoming/` | 用于追溯来源的原始压缩包，不提交。 | 共享 |

项目不依赖 Makefile 或 Shell 脚本来串联流程。所有任务都通过 [pyproject.toml](pyproject.toml) 的 `[project.scripts]` 所声明的命令，或通过 `uv run python <file>` 执行。

## 各部分的交付物

各部分只交换四个 CSV 文件，具体格式见工程计划中的[产物接口](docs/PLAN.zh-CN.md#3-产物接口)。除此之外，各部分互不依赖，因此可以单独重跑，也可以替换模型而不改动其他部分。

- Part 1 → `artifacts/part1/P1_Validated_Expected_Returns.csv`（默认输入）和 `Actual_Returns.csv`；原始预测 `P1_Expected_Returns.csv` 保留作备用。
- Part 2 → `artifacts/part2/P2_Covariance.csv`。
- Part 3 → `artifacts/part3/Portfolio_Weights.csv`。
- Part 4 → `part4_evaluation/reports/TAG/REPORT.md` 及相关表格和图表。

## 协作约定

- 每个部分使用一个分支，通过 Pull Request 合并至 `main`。涉及跨部分交接的改动，以交付文件的格式约定作为审查清单。
- 不要提交 `data/` 中的原始数据或 `_incoming/` 中的压缩包；仓库已配置忽略规则。
- 请求审查前，运行 `uv run pytest`、`uv run sta4020-check-data` 和 `uv run sta4020-check-artifacts`。
- 只引用 `part4_evaluation/reports/` 下报告中的数值，不引用临时 notebook 单元格的结果。
- 每次生成报告使用独立的运行标签，不覆盖旧标签对应的目录，以便复现幻灯片中的数值。

### 双语文档维护

英文是默认入口，自有文档的简体中文版使用 `.zh-CN.md` 后缀，并在页首互相链接。修改运行命令、路径、接口或协作约定时，请在同一个 Pull Request 中同步两种语言。上游文档、课程资料及自动生成的报告保留原样。

## 获取仓库副本

仓库是私有的。协作者需要先接受仓库所有者的邀请，再用自己的凭据克隆；其他步骤不依赖个人配置。

~~~bash
git clone https://github.com/ShenYouSOTA/sta4020-group-project.git
cd sta4020-group-project
uv sync
# 将原始数据复制到 data/ 后：
uv run sta4020-check-data && uv run pytest && uv run sta4020-sample
~~~

如果新克隆的目录由其他用户创建，导致无法写入 `.git`，这是本机的目录权限问题。请修正本地副本的所有权，不要在代码中加入只适用于本机的路径。
