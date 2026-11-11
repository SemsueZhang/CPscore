# 西安赛站解法与核验

[解法分析](../contest-review-xian-2026-solutions.md)包含 A、B、E、F、L 的推导，以及 D 的公开路线来源。这里保存 A、B、E 的 C++ 程序和可独立运行的核验脚本。L 的 `verify_l.py` 同时包含重建策略与模拟交互器。

在仓库根目录编译，无第三方 Python 依赖：

```sh
c++ -std=c++17 -O2 examples/contest-review-xian-2026/solve_a.cpp -o /tmp/cpscore-a
c++ -std=c++17 -O2 examples/contest-review-xian-2026/solve_b.cpp -o /tmp/cpscore-b
c++ -std=c++17 -O2 -DCP_RANDOM_SEED=712367821 examples/contest-review-xian-2026/solve_e.cpp -o /tmp/cpscore-e
```

```sh
python3 examples/contest-review-xian-2026/verify_a.py --solver /tmp/cpscore-a
python3 examples/contest-review-xian-2026/verify_a_cpp.py --solver /tmp/cpscore-a --large
python3 examples/contest-review-xian-2026/verify_b.py --solver /tmp/cpscore-b
python3 examples/contest-review-xian-2026/verify_e_geometry.py
python3 examples/contest-review-xian-2026/verify_e.py --solver /tmp/cpscore-e --cases 100 --large
python3 examples/contest-review-xian-2026/benchmark_e.py --solver /tmp/cpscore-e
python3 examples/contest-review-xian-2026/verify_l.py
```

E 可另用 `-DCP_BLOCK_SIZE=16` 编译，在小数组上增加完整块、边界块和代表更换的覆盖。省略 `CP_RANDOM_SEED` 时从系统随机源初始化。随机性影响运行时间，所有结果均由精确判断得到。

A 和 B 的搜索分别检查计数公式与最优代价。E 的脚本使用逐元素更新作为比较对象。L 的脚本既检查固定仙人掌，也保留相容图集合模拟自适应回答。有限核验不替代文中的证明，本地耗时不保证评测机性能，程序未提交 OJ。
