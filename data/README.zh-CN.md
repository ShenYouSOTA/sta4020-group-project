# 原始数据

[English](README.md) | 简体中文

原始数据不纳入 git（基础文件 530 MB，另含 609 MB 的 `addition/`）。运行依赖真实数据的命令前请先将数据复制到本目录；代码均使用相对于仓库根目录的路径。

| 文件 | 形状 / 大小 | 内容 |
| --- | --- | --- |
| `monthly_returns.pkl` | 355 x 5378 | 月度简单总收益率，月末索引，每列一只股票。 |
| `price.h5` | 324 MB | 每日复权价格与交易日历（需 `h5py`）。 |
| `mcap.pkl` | 356 x 5634 | 月末市值。 |
| `daily_amount.pkl` | 186 MB | 每日成交额。 |
| `BLACKLIST.pkl` | 按日期 | 当日禁止持有的股票。 |
| `UNTRADABLE.pkl` | 按日期 | 当日不可交易的股票（停牌、涨跌停）。 |
| `FF5.csv` | 357 行 | Fama–French 五因子：日期、MKT、SMB、HML、RMW、CMA。 |
| `risk_free.csv` | 7223 行 | 每日无风险利率（日期、RF）。 |
| `zz500.pk` | 4346 x 7 | 中证 500 日线行情。 |

数据来源：Part 1 交付材料（原始压缩包保存在 `_incoming/`，不提交）。原始文件保持只读；清洗与转换逻辑写入 `src/sta4020_project/`。

## 新增：`addition/`（描述变量）

| 文件 | 形状 / 大小 | 内容 |
| --- | --- | --- |
| `addition/descriptors.zip` | 609 MB（解压后 2.59 GiB） | 213 个横截面描述变量（`OrderedDict[str, Series]`，索引为 `(date, asset)`，覆盖 6,128 只股票 × 321 个月末交易日，1999-12-30 至 2026-08-31）。不含行业分类。 |

接入要点（详见 [docs/ADDITION_DATA_ASSESSMENT.zh-CN.md](../docs/ADDITION_DATA_ASSESSMENT.zh-CN.md)）：

- 压缩格式为 Deflate64，需使用 `unzip` 或 `7z` 解压（Python `zipfile` 与 `bsdtar` 不支持）。
- 描述变量日期为月末交易日，预测日历为日历月末；需按 `Period('M')` 对齐（按日期等值连接仅命中 78/116 个月）。
- 逐字段覆盖率与可用档位见 `artifacts/addition/desc_field_coverage.csv`（由 `tools/desc_field_coverage.py` 生成）。

校验目录结构：

~~~bash
uv run sta4020-check-data
~~~
