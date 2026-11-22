# Part 1：预期收益模型

以新版 [FM 岭回归](notebooks/Part1_Return_Model.ipynb) 为正式交付。它每月用 72 个已实现收益月，从 11 个候选特征中按 Rank IC 和 BY 校正筛选因子。首次预测锁定 50 只股票，之后只更新固定池内的预测。[浅层提升树](notebooks/Part1_Return_Model_Tree.ipynb) 独立锁池，用于比较，不覆盖主模型产物。完整建模口径见[构建逻辑](logic_readme.md)。

## 如何运行

在小组项目根目录运行，建议使用 Python 3.11 或 3.12。先按[数据说明](../data/README.zh-CN.md)放置原始数据，再在同一个 Jupyter 内核环境中依次运行两个 notebook 的全部单元格：

~~~sh
python -m pip install -r part1_return_model/requirements.txt
python -m jupyterlab part1_return_model/notebooks
~~~

1. 先运行 FM notebook，更新 [artifacts/part1](../artifacts/part1/) 下的候选池、预期收益和实际收益。
2. 再运行树模型 notebook；它会用主模型产物核对 FM 复现结果，并把树模型的三个 CSV 单独写入 `artifacts/part1/tree/`。
3. Part 2 和 Part 3 要按新版候选池重新生成协方差和权重，不能复用旧池产物。预测表的 `Date` 为调仓月末，与下一月月末的实现收益对齐；收益为小数。

[旧比较 notebook](notebooks/Part1_Return_Model_Comparison.ipynb) 和[旧说明](README_PART1_ORIGINAL.md)仅供历史复现。旧的验证版预测不是新版股票池的输入，不要与新实际收益或新协方差混用。
