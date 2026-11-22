# Part 1：预期收益模型

正式交付采用新版 [FM 岭回归](notebooks/Part1_Return_Model.ipynb)：每月用 72 个已实现收益月，从 11 个候选特征中按 Rank IC 与 BY 校正筛选因子；首次预测锁定 50 只股票，后续仅在固定池内更新预测。[浅层提升树](notebooks/Part1_Return_Model_Tree.ipynb)独立锁池用于对照，产物写入独立目录。建模细节见[构建逻辑](logic_readme.md)。

## 运行方式

在仓库根目录使用 Python 3.11/3.12 运行，按[数据说明](../data/README.zh-CN.md)放置原始数据后，在同一 Jupyter 内核中依次执行：

~~~sh
python -m pip install -r part1_return_model/requirements.txt
python -m jupyterlab part1_return_model/notebooks
~~~

1. 运行 FM notebook，更新 [artifacts/part1](../artifacts/part1/) 下的候选池、预期收益和实际收益。
2. 运行树模型 notebook，将树模型三个 CSV 写入 `artifacts/part1/tree/`。
3. Part 2 与 Part 3 需基于新版候选池重算协方差与权重。预测表 `Date` 为调仓月末，对应下一月末实现收益（小数表示）。

[旧比较 notebook](notebooks/Part1_Return_Model_Comparison.ipynb)与[旧说明](README_PART1_ORIGINAL.md)仅作历史存档，勿与新版股票池混用。
