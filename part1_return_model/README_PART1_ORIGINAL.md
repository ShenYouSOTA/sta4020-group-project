# STA4020 Return Model

用沪深 A 股历史数据预测个股次月简单总收益。主 notebook 在样本外开始前锁定 50 支股票，随后按月更新这批股票的预期收益，并比较模型组合、固定池等权组合和市场基准。

## 运行

使用 Python 3.11。在 `return-model/` 目录下运行以下命令，然后在 JupyterLab 中选择安装了依赖的 Python 内核并运行所有单元格。

```sh
python -m pip install -r requirements.txt
python -m jupyterlab notebooks/Part1_Return_Model.ipynb
```

- [Part1_Return_Model.ipynb](notebooks/Part1_Return_Model.ipynb) 生成固定股票池、次月预测和实际收益，包含交易成本回测。
- [Part1_Return_Model_Comparison.ipynb](notebooks/Part1_Return_Model_Comparison.ipynb) 读取上述固定池和实际收益，在同一股票池上比较预测模型。项目已附上主 notebook 的输出，可直接运行比较。要从原始数据重现全部结果，先运行主 notebook，再运行比较 notebook。

两个 notebook 都支持以项目根目录或 `notebooks/` 为内核工作目录。把整个 `return-model/` 一起移动即可继续使用，相对路径会指向项目内的输入和输出。

## 数据与输出

| 路径 | 内容 |
| --- | --- |
| `data/monthly_returns.pkl` | 个股月收益和次月预测标签 |
| `data/price.h5` | 日度复权收盘价和交易日历 |
| `data/mcap.pkl`、`data/daily_amount.pkl` | 月末市值和日成交额 |
| `data/BLACKLIST.pkl`、`data/UNTRADABLE.pkl` | 逐日黑名单和不可交易记录 |
| `data/FF5.csv`、`data/risk_free.csv` | Fama–French 五因子和无风险收益率 |
| `data/zz500.pk` | 中证 500 价格指数 |
| `docs/` | STA4020 预期收益建模第 3 至 6 讲课件 |

| `part1_output/` 中的文件 | 内容 |
| --- | --- |
| `P1_Candidate_Universe.csv` | 锁定的 50 支股票、入池排名和信号日期 |
| `P1_Expected_Returns.csv` | 主模型对固定池的次月预期收益 |
| `Actual_Returns.csv` | 同一固定池的实际月收益 |
| `P1_Validated_Expected_Returns.csv` | 比较 notebook 用样本外开始前的验证期选定模型后生成的次月预期收益 |

两份预测表的 `Date` 是调仓月的日历月末。匹配实际收益时，将预测月份加一个月。收益率均以小数表示。
