# 程序运行测试数据

任务：读取 n（1 ≤ n ≤ 100），再读取 n 个 [-10^9, 10^9] 内的整数，输出总和及换行。

- `correct.py`、`correct.cpp` 和 `oracle.py` 输出总和，`wrong.py`、`wrong.cpp` 输出总和加一。
- `validator.py` 检查输入格式和范围，`generator.py SEED CASE_INDEX` 按种子和索引生成合法输入。
- `sample.in`、`sample.out` 是样例，`invalid.in` 是非法输入。
- 其他程序用于触发编译失败、超时、输出超限、隔离检查和工具故障。

检查命令及参数见[程序运行工具](../../docs/validation.md)。运行单元测试：`python3 -m unittest tests.test_validation -v`。
