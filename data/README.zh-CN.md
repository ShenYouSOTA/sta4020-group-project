# 原始数据

[English](README.md) | 简体中文

原始数据文件共 530 MB（另有 609 MB 的 `addition/`，见下文），不提交到仓库，而是随课程材料分发。运行任何依赖真实数据的代码之前，请先将这些文件复制到此目录。代码只使用相对于仓库根目录的路径，因此各台机器只需保持相同的目录结构，无需使用相同的绝对路径。

| 文件 | 形状或大小 | 内容 |
| --- | --- | --- |
| monthly_returns.pkl | 355 x 5378 | 月度简单总收益率，以月末日期为索引，每列对应一个股票代码。 |
| price.h5 | 324 MB | 每日复权价格和交易日历（需要 h5py，默认未安装）。 |
| mcap.pkl | 356 x 5634 | 月末市值。 |
| daily_amount.pkl | 186 MB | 每日成交额。 |
| BLACKLIST.pkl | 按日期 | 当日不得持有的股票。 |
| UNTRADABLE.pkl | 按日期 | 当日不能交易的股票（停牌、涨跌停）。 |
| FF5.csv | 357 行 | Fama–French 五因子：日期以及 MKT、SMB、HML、RMW、CMA。 |
| risk_free.csv | 7223 行 | 每日无风险利率，包含日期和 RF。 |
| zz500.pk | 4346 x 7 | 中证 500 日线行情。 |

数据来源：第 1 部分的交付材料（原始 ZIP 压缩包保存在 `_incoming/` 中，同样不提交到仓库）。本项目不会修改此目录中的任何文件；如需清洗或转换文件，请将处理代码写入 `src/sta4020_project/`，以便复现该步骤。

### 新增：`addition/`（描述变量）

| 文件 | 形状或大小 | 内容 |
| --- | --- | --- |
| addition/descriptors.zip | 609 MB（解压后 2.59 GiB） | 213 个横截面描述变量：动量、波动、规模与价值、质量与盈利、成长、杠杆与流动性、评分卡、分析师预期。结构为 `OrderedDict[str, Series]`，索引为 `(date, asset)`，6128 只股票 × 321 个月末**交易日**（1999-12-30 至 2026-08-31）。不含行业分类。 |

接入前的三个注意点（详见 [docs/ADDITION_DATA_ASSESSMENT.zh-CN.md](../docs/ADDITION_DATA_ASSESSMENT.zh-CN.md)）：

- 压缩方法为 Deflate64，Python 标准库 `zipfile` 与 bsdtar 都解不开，必须用 `unzip` 或 7z。
- 日期是当月**最后交易日**，而预测日历是**日历**月末；必须按 `Period('M')` 对齐，按日期等值连接只能命中 78/116。
- 逐字段覆盖率与可用档位见 `artifacts/addition/desc_field_coverage.csv`（由 `tools/desc_field_coverage.py` 生成）。

使用以下命令检查目录结构：

~~~bash
uv run sta4020-check-data
~~~
