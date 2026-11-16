#!/usr/bin/env python3
"""Shared OI Wiki knowledge catalog: offline queries and reproducible local updates.

Python 3.8+ standard library only. Source text is never copied into the catalog.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from urllib.request import Request, urlopen
from urllib.parse import urlparse

ROOTS = {'算法基础', '搜索', '动态规划', '字符串', '数学', '数据结构', '图论', '计算几何', '杂项', '专题'}
EXTRA_PAGES = {
    'lang/csl/bitset.md': ('位集', ['数据结构', '位集合']),
    'contest/dictionary.md': ('分段打表', ['竞赛技巧']),
    'contest/io.md': ('读入输出优化', ['竞赛技巧']),
    'contest/common-tricks.md': ('竞赛验证技巧', ['竞赛技巧']),
}
SKIP = {
    'basic/stl-sort.md': '标准库接口教学；排序算法由独立页面收录',
    'string/lib-func.md': '字符串标准库接口教学',
    'math/numeral-sys/intro.md': '纯导览；知识见进位制等页面',
    'math/linear-algebra/index.md': '纯导览；知识见向量、矩阵等页面',
    'misc/endianness.md': '字节序与系统表示，非算法方法',
    'dp/opt/dp-opt.md': '优化导览；具体方法各自收录',
}
MERGE = {
    'graph/dfs.md': 'search/dfs.md', 'graph/bfs.md': 'search/bfs.md',
    'ds/dsu-complexity.md': 'ds/dsu.md', 'topic/dsu-app.md': 'ds/dsu.md',
    'misc/mo-algo-intro.md': 'misc/mo-algo.md', 'basic/use-of-sort.md': 'basic/sort-intro.md',
}
# Canonical display names; original navigation titles remain searchable aliases.
NAMES = {
    'string/sa.md': '后缀数组', 'math/number-theory/mod-arithmetic.md': '模算术',
    'search/astar.md': 'A* 搜索算法', 'search/idastar.md': 'IDA* 搜索算法',
    'graph/2-sat.md': '2-SAT 问题',
    'math/game-theory/intro.md': '博弈论', 'misc/offline.md': '离线算法',
    'misc/space-optimization.md': '空间优化',
    'math/poly/multipoint-eval-interpolation.md': '多项式多点求值',
    'math/poly/shift.md': '多项式平移', 'math/poly/comp-rev.md': '形式幂级数复合',
    'basic/complexity.md': '复杂度分析', 'basic/sort-intro.md': '排序',
    'basic/divide-and-conquer.md': '分治', 'basic/prefix-sum.md': '前缀和',
    'basic/binary.md': '二分查找', 'search/dfs.md': '深度优先搜索',
    'search/bfs.md': '广度优先搜索', 'search/dlx.md': '舞蹈链',
    'search/opt.md': '搜索剪枝', 'dp/basic.md': '动态规划',
    'dp/knapsack/basic.md': '背包动态规划', 'dp/knapsack/advanced.md': '泛化物品背包',
    'string/kmp.md': 'KMP 算法', 'string/z-func.md': 'Z 函数',
    'string/manacher.md': 'Manacher 回文算法', 'math/poly/intro.md': '多项式与形式幂级数',
    'math/number-theory/bezouts.md': '裴蜀定理', 'math/number-theory/fermat.md': '费马小定理',
    'math/number-theory/hyperbola.md': '狄利克雷双曲线法',
    'math/number-theory/primitive-root.md': '原根', 'math/number-theory/residue.md': '高次剩余',
    'math/number-theory/stern-brocot.md': 'Stern–Brocot 树',
    'math/combinatorics/entringer.md': '恩特林格数', 'math/combinatorics/eulerian.md': '欧拉数',
    'math/linear-algebra/product.md': '向量内积',
    'math/linear-algebra/jordan.md': '若尔当标准型', 'math/algebra/basic.md': '抽象代数基础',
    'math/probability/basic-conception.md': '概率论基础',
    'math/probability/exp-var.md': '数学期望', 'ds/heap.md': '堆',
    'ds/seg.md': '线段树', 'ds/seg-merge-split.md': '线段树合并',
    'ds/bst.md': '二叉搜索树', 'ds/treap.md': '树堆', 'ds/sbt.md': '大小平衡树',
    'ds/wblt.md': '重量平衡叶子树', 'ds/sqrt-tree.md': '平方根树',
    'ds/kinetic-tournament-tree.md': '动态锦标赛树', 'ds/kdt.md': 'K 维树',
    'ds/lct.md': '链剖动态树', 'ds/ett.md': '欧拉游览树', 'ds/top-tree.md': '顶树',
    'ds/pq-tree.md': 'PQ 树', 'ds/persistent.md': '可持久化数据结构',
    'ds/seg-beats.md': '区间最值操作', 'graph/flow.md': '网络流',
    'graph/graph-matching/graph-match.md': '图的匹配',
    'graph/tree-ahu.md': 'AHU 树同构算法', 'graph/lgv.md': 'LGV 引理',
    'geometry/triangulation.md': '三角剖分', 'geometry/convex-hull.md': '凸包',
    'misc/random.md': '随机数生成', 'misc/cc-basic.md': '计算理论基础',
    'misc/mo-algo.md': '莫队算法', 'misc/15-puzzle.md': '十五数码问题',
    'misc/kahan-summation.md': 'Kahan 补偿求和', 'misc/fsm.md': '有限状态自动机',
    'misc/odt.md': '珂朵莉树', 'topic/rmq.md': '区间最值查询',
}
# Common synonyms, not assertions about complexity, prerequisites or difficulty.
ALIASES = {
    'basic/amortized-analysis.md': 'Amortized Analysis|摊还分析',
    'basic/enumerate.md': 'Enumeration|暴力枚举', 'basic/simulate.md': 'Simulation',
    'basic/divide-and-conquer.md': 'Divide and Conquer|分而治之',
    'basic/greedy.md': 'Greedy Algorithm', 'basic/binary.md': 'Binary Search|折半查找',
    'basic/binary-lifting.md': 'Binary Lifting', 'basic/prefix-sum.md': 'Prefix Sum|前缀累加',
    'basic/quick-sort.md': 'Quick Sort|Quicksort|快排', 'basic/merge-sort.md': 'Merge Sort',
    'basic/heap-sort.md': 'Heap Sort', 'basic/insertion-sort.md': 'Insertion Sort',
    'basic/selection-sort.md': 'Selection Sort', 'basic/bubble-sort.md': 'Bubble Sort',
    'basic/radix-sort.md': 'Radix Sort', 'basic/counting-sort.md': 'Counting Sort',
    'basic/bucket-sort.md': 'Bucket Sort', 'basic/shell-sort.md': 'Shell Sort',
    'basic/tournament-sort.md': 'Tournament Sort', 'basic/tim-sort.md': 'Timsort',
    'search/dfs.md': 'DFS|Depth First Search|Depth-First Search|DFS（图论）',
    'search/bfs.md': 'BFS|Breadth First Search|Breadth-First Search|BFS（图论）',
    'search/bidirectional.md': 'Bidirectional Search', 'search/astar.md': 'A Star|A*|A星算法',
    'search/idastar.md': 'IDA Star|IDA*', 'search/iterative.md': 'IDDFS|Iterative Deepening',
    'search/backtracking.md': 'Backtracking', 'search/dlx.md': 'DLX|Dancing Links',
    'search/alpha-beta.md': 'Alpha-Beta Pruning|α-β 剪枝',
    'dp/basic.md': 'DP|Dynamic Programming', 'dp/memo.md': 'Memoization|记忆化递归',
    'dp/tree.md': 'Tree DP', 'dp/interval.md': 'Interval DP',
    'dp/state.md': 'Bitmask DP|状态压缩动态规划', 'dp/number.md': 'Digit DP|数位动态规划',
    'dp/plug.md': 'Plug DP', 'dp/dynamic.md': 'DDP|动态动态规划|Dynamic DP',
    'dp/opt/slope.md': 'Convex Hull Trick|CHT', 'dp/opt/wqs-binary-search.md': 'Aliens Trick|WQS 二分',
    'dp/opt/slope-trick.md': 'Slope Trick', 'string/hash.md': 'String Hash|字符串散列',
    'string/trie.md': 'Trie|前缀树|字典树', 'string/kmp.md': 'Knuth-Morris-Pratt|KMP',
    'string/z-func.md': 'Z Algorithm|Z-function|扩展 KMP|exKMP',
    'string/bm.md': 'Boyer-Moore|BM 字符串匹配',
    'string/ac-automaton.md': 'Aho-Corasick Automaton|ACAM|AC 自动机',
    'string/sa.md': 'SA|Suffix Array', 'string/sam.md': 'SAM|Suffix Automaton',
    'string/general-sam.md': 'Generalized Suffix Automaton|广义 SAM',
    'string/pam.md': 'PAM|Eertree|Palindromic Tree|回文自动机',
    'string/manacher.md': 'Manacher|马拉车算法', 'string/suffix-tree.md': 'Suffix Tree',
    'string/lyndon.md': 'Lyndon Factorization', 'string/minimal-string.md': '最小循环表示|Minimal Representation',
    'math/binary-exponentiation.md': 'Binary Exponentiation|快速乘方',
    'math/bignum.md': 'Big Integer|任意精度整数', 'math/number-theory/gcd.md': 'GCD|Greatest Common Divisor',
    'math/number-theory/euler-totient.md': 'Euler Totient Function|Phi 函数',
    'math/number-theory/crt.md': 'CRT|Chinese Remainder Theorem|孙子定理',
    'math/number-theory/lucas.md': 'Lucas Theorem',
    'math/number-theory/mobius.md': 'Mobius Inversion|Möbius Inversion',
    'math/number-theory/dirichlet.md': 'Dirichlet Convolution',
    'math/number-theory/pollard-rho.md': 'Integer Factorization|整数分解',
    'math/number-theory/discrete-logarithm.md': 'Discrete Logarithm',
    'math/number-theory/lift-the-exponent.md': 'LTE|Lifting The Exponent Lemma',
    'math/poly/fft.md': 'FFT|Fast Fourier Transform', 'math/poly/ntt.md': 'NTT|Fast Number Theoretic Transform',
    'math/poly/fwt.md': 'FWT|Fast Walsh Transform|快速沃尔什-哈达玛变换',
    'math/poly/czt.md': 'CZT|Chirp Z Transform', 'math/poly/ogf.md': 'OGF|Ordinary Generating Function',
    'math/poly/egf.md': 'EGF|Exponential Generating Function',
    'math/linear-algebra/basis.md': 'Linear Basis',
    'math/numerical/gauss.md': 'Gaussian Elimination|高斯消元法',
    'math/numerical/interp.md': 'Interpolation', 'math/numerical/integral.md': 'Numerical Integration',
    'math/numerical/newton.md': 'Newton Method|Newton-Raphson',
    'math/combinatorics/polya.md': 'Polya Enumeration|Pólya Enumeration',
    'math/combinatorics/drawer-principle.md': 'Pigeonhole Principle|鸽巢原理',
    'math/combinatorics/inclusion-exclusion-principle.md': 'Inclusion-Exclusion Principle|容斥',
    'math/berlekamp-massey.md': 'BM 递推|Berlekamp-Massey|线性递推最小多项式',
    'ds/dsu.md': 'DSU|Disjoint Set Union|Union Find',
    'ds/fenwick.md': 'BIT|Binary Indexed Tree|Fenwick Tree',
    'ds/seg.md': 'Segment Tree', 'ds/persistent-seg.md': 'Persistent Segment Tree|主席树',
    'ds/treap.md': 'Treap', 'ds/splay.md': 'Splay|伸展树', 'ds/bst.md': 'BST|Binary Search Tree',
    'ds/sgt.md': 'Scapegoat Tree', 'ds/leftist-tree.md': 'Leftist Heap|左偏堆',
    'ds/monotonic-stack.md': 'Monotonic Stack', 'ds/monotonic-queue.md': 'Monotonic Queue',
    'ds/sparse-table.md': 'Sparse Table|ST 表', 'ds/hash.md': 'Hash Table|散列表',
    'ds/lct.md': 'LCT|Link Cut Tree|Link-Cut Tree', 'ds/ett.md': 'ETT|Euler Tour Tree',
    'ds/top-tree.md': 'Top Tree', 'ds/kdt.md': 'KD Tree|K-D Tree|K-Dimensional Tree',
    'ds/huffman-tree.md': 'Huffman Tree|哈夫曼树', 'ds/seg-beats.md': 'Segment Tree Beats|吉司机线段树',
    'graph/lca.md': 'LCA|Lowest Common Ancestor', 'graph/hld.md': 'HLD|树剖|Tree Chain Decomposition',
    'graph/dsu-on-tree.md': 'DSU on Tree|Sack', 'graph/scc.md': 'SCC|Strongly Connected Components',
    'graph/bcc.md': 'BCC|Biconnected Components', 'graph/topo.md': 'Topological Sort',
    'graph/mst.md': 'MST|Minimum Spanning Tree', 'graph/dmst.md': 'Directed MST|最小树形图',
    'graph/2-sat.md': '2SAT|2-Satisfiability', 'graph/flow/max-flow.md': 'Maximum Flow',
    'graph/flow/min-cut.md': 'Minimum Cut', 'graph/flow/min-cost.md': 'Min Cost Flow|最小费用流',
    'graph/graph-matching/bigraph-weight-match.md': '二分图带权匹配',
    'graph/prufer.md': 'Prufer Sequence|Prüfer Sequence',
    'graph/matrix-tree.md': 'Matrix Tree Theorem|Kirchhoff Theorem|基尔霍夫定理',
    'graph/lgv.md': 'Lindstrom-Gessel-Viennot Lemma',
    'geometry/convex-hull.md': 'Convex Hull', 'geometry/half-plane.md': 'Half Plane Intersection',
    'geometry/rotating-calipers.md': 'Rotating Calipers',
    'misc/two-pointer.md': 'Two Pointers|尺取法', 'misc/discrete.md': 'Coordinate Compression',
    'misc/odt.md': 'ODT|Chtholly Tree|颜色段均摊',
    'misc/mo-algo.md': 'Mo Algorithm|Mo\'s Algorithm|普通莫队算法',
    'misc/cdq-divide.md': 'CDQ Divide and Conquer', 'misc/parallel-binsearch.md': 'Parallel Binary Search',
    'misc/fsm.md': 'FSM|Finite State Machine', 'misc/main-element.md': 'Majority Element',
    'misc/simulated-annealing.md': 'SA|Simulated Annealing',
    'misc/hill-climbing.md': 'Hill Climbing', 'topic/rmq.md': 'RMQ|Range Minimum Query',
    'lang/csl/bitset.md': 'Bitset|位向量|位集合',
}

EXTRA_ALIASES = """
basic/construction.md|Constructive Algorithm;构造法
search/heuristic.md|Heuristic Search
dp/count.md|Counting DP;计数动态规划
dp/dag.md|DAG DP;有向无环图动态规划
dp/dp-of-dp.md|DP of DP
dp/probability.md|Probability DP;概率动态规划
dp/opt/quadrangle.md|Quadrangle Inequality Optimization;四边形不等式
ds/aa-tree.md|AA Tree
ds/avl.md|AVL Tree
ds/binary-heap.md|Binary Heap
ds/block-array.md|Block Array
ds/block-list.md|Unrolled Linked List
ds/cartesian-tree.md|Cartesian Tree
ds/decompose.md|Sqrt Decomposition;平方根分治
ds/dividing.md|Partition Tree
ds/finger-tree.md|Finger Tree
ds/global-bst.md|Global Balanced Binary Tree
ds/li-chao-tree.md|Li Chao Segment Tree;Li Chao Tree
ds/linked-list.md|Linked List
ds/llrbt.md|LLRBT;Left Leaning Red Black Tree
ds/pairing-heap.md|Pairing Heap
ds/persistent-balanced.md|Persistent Balanced Tree
ds/persistent-heap.md|Persistent Meldable Heap
ds/persistent-trie.md|Persistent Trie
ds/pq-tree.md|PQ Tree
ds/queue.md|Queue
ds/rbtree.md|Red Black Tree;RB Tree
ds/seg-merge-split.md|Segment Tree Merge
ds/skiplist.md|Skip List
ds/stack.md|Stack
ds/tree-decompose.md|Tree Blocking
geometry/2d.md|2D Computational Geometry
geometry/3d.md|3D Computational Geometry
geometry/inverse.md|Inversion Geometry;圆反演
geometry/nearest-points.md|Closest Pair of Points
geometry/pick.md|Pick Theorem
geometry/random-incremental.md|Randomized Incremental Algorithm
geometry/scanning.md|Sweep Line;扫描线算法
geometry/smallest-enclosing-circle.md|Minimum Enclosing Circle;Smallest Enclosing Circle
geometry/triangulation.md|Triangulation
graph/bi-graph.md|Bipartite Graph
graph/block-forest.md|Block Cut Tree;Block Forest
graph/chord.md|Chordal Graph
graph/color.md|Graph Coloring
graph/connectivity.md|Graph Connectivity
graph/dag.md|DAG;Directed Acyclic Graph
graph/diff-constraints.md|Difference Constraints
graph/dominator-tree.md|Dominator Tree
graph/dynamic-tree-divide.md|Dynamic Centroid Decomposition
graph/euler.md|Eulerian Graph
graph/graph-matching/bigraph-match.md|Bipartite Matching
graph/graph-matching/general-match.md|General Graph Matching
graph/graph-matching/general-weight-match.md|General Weighted Matching
graph/graph-matching/stable-match.md|Stable Matching
graph/graph-random-walk.md|Random Walk on Graphs
graph/hamilton.md|Hamiltonian Graph
graph/kth-path.md|K Shortest Paths;K 短路
graph/max-clique.md|Maximum Clique
graph/mdst.md|Minimum Diameter Spanning Tree
graph/min-cycle.md|Minimum Cycle
graph/mod-shortest-path.md|Residue Shortest Path
graph/node.md|Vertex Splitting;点拆分
graph/planar.md|Planar Graph
graph/shortest-path.md|Shortest Path
graph/steiner-tree.md|Steiner Tree
graph/stoer-wagner.md|Stoer Wagner
graph/tree-center.md|Tree Center
graph/tree-centroid.md|Tree Centroid
graph/tree-diameter.md|Tree Diameter
graph/tree-hash.md|Tree Hashing
graph/tree-random-walk.md|Random Walk on Trees
graph/virtual-tree.md|Virtual Tree
math/algebra/basic.md|Abstract Algebra
math/algebra/field-theory.md|Field Theory
math/algebra/group-theory.md|Group Theory
math/algebra/ring-theory.md|Ring Theory
math/algebra/schreier-sims.md|Schreier Sims
math/binary-set.md|Bitmask Set Operations
math/bit.md|Bitwise Operations;位运算
math/boolean-algebra.md|Boolean Algebra
math/combinatorics/bell.md|Bell Number
math/combinatorics/bernoulli.md|Bernoulli Number
math/combinatorics/catalan.md|Catalan Number
math/combinatorics/combination.md|Permutations and Combinations
math/combinatorics/derangement.md|Derangement;错排
math/combinatorics/fibonacci.md|Fibonacci Sequence
math/combinatorics/partition.md|Partition Number;整数分拆
math/combinatorics/stirling.md|Stirling Numbers
math/combinatorics/vandermonde-convolution.md|Vandermonde Identity;Vandermonde Convolution
math/complex.md|Complex Numbers
math/game-theory/impartial-game.md|Impartial Game
math/game-theory/intro.md|Game Theory
math/game-theory/partizan-game.md|Partizan Game
math/game-theory/zero-sum-game.md|Zero Sum Game
math/linear-algebra/char-poly.md|Characteristic Polynomial
math/linear-algebra/determinant.md|Determinant
math/linear-algebra/diagonalization.md|Matrix Diagonalization
math/linear-algebra/elementary-operations.md|Elementary Matrix Operations
math/linear-algebra/linear-mapping.md|Linear Map
math/linear-algebra/matrix.md|Matrix
math/linear-algebra/product.md|Dot Product;点积
math/linear-algebra/vector.md|Vector
math/linear-algebra/vector-space.md|Vector Space
math/linear-programming.md|Linear Programming;LP
math/matroid.md|Matroid
math/number-theory/bezouts.md|Bezout Identity;Bézout Identity
math/number-theory/congruence-equation.md|Congruence Equation
math/number-theory/continued-fraction.md|Continued Fraction
math/number-theory/factorial.md|Factorial Modulo
math/number-theory/fermat.md|Fermat Little Theorem
math/number-theory/hyperbola.md|Dirichlet Hyperbola Method
math/number-theory/inverse.md|Modular Inverse;乘法逆元
math/number-theory/linear-equation.md|Linear Congruence Equation
math/number-theory/min-25.md|Min25 Sieve;Min_25 Sieve
math/number-theory/mod-arithmetic.md|Modular Arithmetic
math/number-theory/pell-equation.md|Pell Equation
math/number-theory/powerful-number.md|Powerful Number Sieve;PN 筛
math/number-theory/prime.md|Prime Number
math/number-theory/prime-counting.md|Prime Counting
math/number-theory/primitive-root.md|Primitive Root
math/number-theory/quad-residue.md|Quadratic Residue
math/number-theory/quadratic.md|Quadratic Field
math/number-theory/residue.md|Higher Power Residue
math/number-theory/sieve.md|Sieve of Primes
math/number-theory/sqrt-decomposition.md|整除分块;Division Blocking
math/number-theory/stern-brocot.md|Stern Brocot Tree
math/number-theory/zhou.md|Zhou Sieve
math/numeral-sys/balanced-ternary.md|Balanced Ternary
math/numeral-sys/base.md|Numeral Base;进制转换
math/numeral-sys/gray-code.md|Gray Code
math/order-theory.md|Order Theory
math/permutation.md|Permutation
math/poly/comp-rev.md|Formal Power Series Composition
math/poly/elementary-func.md|Polynomial Elementary Functions
math/poly/fundamental.md|Fundamental Theorem of Algebra
math/poly/lagrange-inversion.md|Lagrange Inversion
math/poly/linear-recurrence.md|Linear Recurrence
math/poly/multipoint-eval-interpolation.md|Multipoint Evaluation
math/poly/newton.md|Polynomial Newton Iteration
math/poly/shift.md|Polynomial Shift;Taylor Shift
math/poly/symbolic-method.md|Symbolic Method
math/probability/concentration-inequality.md|Concentration Inequalities
math/probability/exp-var.md|Expectation;Expected Value
math/probability/random-variable.md|Random Variable
math/simplex.md|Simplex Method
math/young-tableau.md|Young Tableau
misc/expression.md|Expression Evaluation
misc/frac-programming.md|Fractional Programming
misc/garsia-wachs.md|Garsia Wachs
misc/hoverline.md|悬线算法
misc/josephus.md|Josephus Problem
misc/mo-algo-on-tree.md|Mo Algorithm on Trees
misc/modifiable-mo-algo.md|Mo Algorithm with Modifications
misc/offline.md|Offline Algorithm
misc/rand-technique.md|Randomized Techniques
misc/rollback-mo-algo.md|Rollback Mo Algorithm
string/main-lorentz.md|Main Lorentz
string/match.md|String Matching;Pattern Matching
string/seq-automaton.md|Subsequence Automaton
string/suffix-bst.md|Suffix Balanced Search Tree
topic/bracket.md|Balanced Bracket Sequence
topic/segment-tree-offline.md|线段树分治;Segment Tree over Time
"""
for _line in EXTRA_ALIASES.strip().splitlines():
    _path, _aliases = _line.split("|", 1)
    ALIASES[_path] = "|".join(filter(None, [ALIASES.get(_path, ""), _aliases.replace(";", "|")]))

# Audited independent methods inside pages: stable suffix, name, exact section, aliases.
# The page heading is checked on every update; examples/implementations are not entries.
SPLIT_RULES = r"""
math/linear-algebra/basis.md
xor|异或线性基|应用|XOR Linear Basis
basic/amortized-analysis.md
aggregate|聚合分析法|聚合分析|Aggregate Analysis
accounting|记账分析法|记账分析|Accounting Method
potential|势能分析法|势能分析|Potential Method
dp/basic.md
lis|最长上升子序列|最长不下降子序列|LIS;Longest Increasing Subsequence
math/number-theory/mod-arithmetic.md
fast-multiplication|快速模乘|快速乘|快速乘;Modular Multiplication
math/number-theory/gcd.md
subtraction|更相减损术|更相减损术|
math/game-theory/impartial-game.md
bash|巴什博弈|Bachet 游戏|Bash Game;Bachet Game
moore-nim|Moore 多堆尼姆博弈|Moore's Nim-k 游戏|Moore Nim
coin-turning|翻硬币博弈|翻硬币游戏|Coin Turning Game
bipartite-game|二分图博弈|二分图博弈|
ds/dsu.md
path-compression|并查集路径压缩|路径压缩|Path Compression
union-by-size|并查集按大小合并|启发式合并|Union by Size
graph/shortest-path.md
spfa|队列优化的贝尔曼–福特算法|队列优化：SPFA|SPFA;Shortest Path Faster Algorithm
graph/dmst.md
tarjan-dmst|Tarjan 最小树形图算法|Tarjan 的 DMST 算法|Tarjan DMST
misc/random.md
fisher-yates|费雪–耶茨随机置换|`random_shuffle`|Fisher Yates Shuffle
misc/space-optimization.md
rolling-array|滚动数组|避免存储不必要的数据|Rolling Array
basic/complexity.md
master-theorem|主定理|主定理|Master Theorem
basic/divide-and-conquer.md
recursion|递归|递归|Recursion
basic/greedy.md
regret|反悔贪心|后悔解法|后悔贪心
basic/insertion-sort.md
binary-insertion|折半插入排序|折半插入排序|Binary Insertion Sort
basic/radix-sort.md
msd|高位优先基数排序|MSD 基数排序|MSD Radix Sort
lsd|低位优先基数排序|LSD 基数排序|LSD Radix Sort
basic/quick-sort.md
three-way|三路快速排序|三路快速排序|Three-Way Quicksort
introsort|内省排序|内省排序|Introsort
bfprt|中位数的中位数算法|中位数中的中位数|BFPRT;Median of Medians
basic/merge-sort.md
inversions|逆序对计数|逆序对|Inversion Counting
basic/prefix-sum.md
difference|差分|差分|Difference Array;差分数组
multidimensional|多维前缀和|二维/多维前缀和|二维前缀和;Multidimensional Prefix Sum
subset-sum|子集和动态规划|特例：子集和 DP|SOS DP;Sum over Subsets DP
prefix-on-tree|树上前缀和|树上前缀和|
difference-on-tree|树上差分|树上差分|
basic/binary.md
answer|二分答案|二分答案|Binary Search on Answer
ternary|三分法|三分法|Ternary Search
search/bidirectional.md
meet-in-the-middle|折半搜索|Meet in the middle|Meet in the Middle;MITM;中途相遇法
search/dlx.md
algorithm-x|X 算法|X 算法|Algorithm X
search/alpha-beta.md
minimax|极小极大搜索|Minimax 算法|Minimax;博弈树搜索
search/opt.md
optimality-pruning|最优性剪枝|最优性剪枝|Optimality Pruning
feasibility-pruning|可行性剪枝|可行性剪枝|Feasibility Pruning
dp/basic.md
lcs|最长公共子序列|最长公共子序列|LCS;Longest Common Subsequence
lnds|最长不下降子序列|最长不下降子序列|LNDS;Longest Nondecreasing Subsequence
dp/knapsack/basic.md
zero-one|0-1 背包|0-1 背包|01 背包;0/1 Knapsack
unbounded|完全背包|完全背包|Unbounded Knapsack
bounded|多重背包|多重背包|Bounded Knapsack
binary-grouping|多重背包二进制分组|二进制分组优化|Binary Grouping
monotonic-queue|多重背包单调队列优化|单调队列优化|
dp/knapsack/advanced.md
grouped|分组背包|分组背包|Grouped Knapsack
rollback|回退背包|回退背包|
kth-best|背包第 k 优解|背包的第 k 优解|
mixed|混合背包|混合背包|Mixed Knapsack
multidimensional|二维费用背包|二维费用背包|Multidimensional Knapsack
dependent|有依赖的背包|有依赖的背包|Dependent Knapsack
dp/tree.md
knapsack|树上背包|树上背包|Tree Knapsack
rerooting|换根动态规划|换根 DP|Rerooting DP;换根 DP
dp/plug.md
contour|轮廓线动态规划|骨牌覆盖与轮廓线 DP|轮廓线 DP;Contour DP
dp/probability.md
expectation|期望动态规划|期望 DP|期望 DP;Expected Value DP
dp/opt/quadrangle.md
divide-conquer|分治优化动态规划|分治|Divide and Conquer DP Optimization
larsch|LARSCH 算法|简化 LARSCH 算法|LARSCH
string/kmp.md
prefix-function|前缀函数|前缀函数|Prefix Function;失配函数
kmp-automaton|KMP 自动机|根据前缀函数构建一个自动机|KMP Automaton
string/trie.md
binary-trie|01 字典树|维护异或极值|01 Trie;Binary Trie
string/bm.md
horspool|Boyer–Moore–Horspool 算法|Boyer–Moore–Horspool 算法|BMH;Horspool Algorithm
sunday|Sunday 字符串匹配算法|Boyer–Moore–Sunday 算法|Sunday Algorithm;Boyer-Moore-Sunday
string/sa.md
sais|SA-IS 后缀排序|SA-IS|SAIS;Induced Sorting
dc3|DC3 后缀排序|DC3|Skew Algorithm;DC3
lcp|最长公共前缀|LCP（最长公共前缀）|LCP;Longest Common Prefix
string/suffix-tree.md
ukkonen|Ukkonen 后缀树算法|Ukkonen 算法|Ukkonen Algorithm
string/lyndon.md
duval|Duval 算法|Duval 算法|Duval Algorithm
math/bit.md
popcount|汉明权重|汉明权重|Popcount;Hamming Weight
math/binary-set.md
submask|子掩码枚举|遍历所有掩码的子掩码|Submask Enumeration;子集枚举
math/bignum.md
karatsuba|Karatsuba 乘法|Karatsuba 乘法|Karatsuba Multiplication
math/number-theory/basic.md
multiplicative-functions|积性函数|积性函数|Multiplicative Function
fundamental-theorem|算术基本定理|算术基本定理|Fundamental Theorem of Arithmetic
math/number-theory/mod-arithmetic.md
barrett|Barrett 约减|Barrett 约减|Barrett Reduction
montgomery|Montgomery 模乘|Montgomery 模乘|Montgomery Multiplication;蒙哥马利乘法
math/number-theory/prime.md
trial-division|试除素性测试|试除法|Trial Division
fermat-test|费马素性测试|Fermat 素性测试|Fermat Primality Test
miller-rabin|Miller–Rabin 素性测试|Miller–Rabin 素性测试|Miller Rabin;MR 素性测试
highly-composite|反素数|反素数|Highly Composite Number
math/number-theory/gcd.md
euclidean|欧几里得算法|欧几里得算法|辗转相除法;Euclidean Algorithm
stein|二进制最大公约数算法|Stein 算法的优化|Stein Algorithm;Binary GCD
extended-euclidean|扩展欧几里得算法|扩展欧几里得算法|exgcd;Extended Euclidean Algorithm
lcm|最小公倍数|最小公倍数|LCM;Least Common Multiple
math/number-theory/sieve.md
eratosthenes|埃拉托斯特尼筛法|埃拉托斯特尼筛法|埃氏筛;Eratosthenes Sieve
linear|线性筛法|线性筛法|欧拉筛;Euler Sieve;Linear Sieve
segmented|分块筛选|分块筛选|Segmented Sieve;分段筛
math/number-theory/pollard-rho.md
pollard-rho|Pollard Rho 质因数分解|Pollard Rho 算法|Pollard's Rho;Pollard Rho
math/number-theory/bezouts.md
diophantine|一次不定方程|一次不定方程|Linear Diophantine Equation
frobenius|弗罗贝尼乌斯硬币问题|Frobenius 硬币问题|Frobenius Coin Problem
math/number-theory/fermat.md
euler|欧拉定理|欧拉定理|Euler Theorem
extended-euler|扩展欧拉定理|扩展欧拉定理|
math/number-theory/crt.md
extended-crt|扩展中国剩余定理|扩展：模数不互质的情况|exCRT;Extended CRT
garner|Garner 算法|Garner 算法|Garner Algorithm
math/number-theory/factorial.md
wilson|威尔逊定理|Wilson 定理|Wilson Theorem
legendre|勒让德阶乘赋值公式|Legendre 公式|Legendre Formula
kummer|Kummer 定理|Kummer 定理|Kummer Theorem
math/number-theory/lucas.md
extended-lucas|扩展卢卡斯定理|exLucas 算法|exLucas;Extended Lucas
math/number-theory/quad-residue.md
legendre-symbol|勒让德符号|Legendre 符号|Legendre Symbol
jacobi-symbol|雅可比符号|Jacobi 符号|Jacobi Symbol
quadratic-reciprocity|二次互反律|二次互反律|Quadratic Reciprocity
cipolla|Cipolla 算法|Cipolla 算法|Cipolla
sqrt-bostan-mori|Bostan–Mori 模平方根算法|Bostan–Mori 算法|
tonelli-shanks|Tonelli–Shanks 算法|Tonelli–Shanks 算法|Tonelli Shanks
math/number-theory/primitive-root.md
order|模意义下的阶|阶|Multiplicative Order
carmichael|卡迈克尔函数|Carmichael 函数|Carmichael Function
math/number-theory/discrete-logarithm.md
bsgs|大步小步算法|大步小步算法|BSGS;Baby Step Giant Step
extended-bsgs|扩展大步小步算法|扩展 BSGS 算法|exBSGS;Extended BSGS
math/number-theory/residue.md
roots-of-unity|单位根|单位根|Roots of Unity
math/number-theory/dirichlet.md
dirichlet-series|狄利克雷生成函数|Dirichlet 生成函数|Dirichlet Series
math/number-theory/mobius.md
mobius-function|莫比乌斯函数|莫比乌斯函数|Mobius Function;Möbius Function
math/number-theory/hyperbola.md
dujiao|杜教筛|杜教筛|Du Jiao Sieve
math/number-theory/prime-counting.md
meissel-lehmer|Meissel–Lehmer 素数计数|Meissel–Lehmer 算法|Meissel Lehmer
lucy|Lucy 素数筛|Lucy 算法|Lucy DP;Lucy Sieve
math/number-theory/euclidean.md
extended|万能欧几里得算法|万能欧几里得算法|
math/number-theory/stern-brocot.md
farey|法里序列|Farey 序列|Farey Sequence
calkin-wilf|Calkin–Wilf 树|Calkin–Wilf 树|Calkin Wilf Tree
math/number-theory/quadratic.md
gaussian|高斯整数|Gauss 整数|Gaussian Integer
eisenstein|艾森斯坦整数|Eisenstein 整数|Eisenstein Integer
math/number-theory/pell-equation.md
pqa|PQa 算法|PQa 算法|PQa
math/poly/fft.md
dft|离散傅里叶变换|离散傅里叶变换|DFT;Discrete Fourier Transform
math/poly/fwt.md
or|按位或卷积|或运算|OR Convolution
and|按位与卷积|与运算|AND Convolution
xor|按位异或卷积|异或运算|XOR Convolution
math/poly/czt.md
bluestein|Bluestein 算法|Bluestein 算法|Bluestein
bostan-schost|Bostan–Schost 算法|Bostan–Schost 算法|Bostan Schost
math/poly/multipoint-eval-interpolation.md
interpolation|多项式快速插值|多项式的快速插值|Fast Polynomial Interpolation
math/poly/elementary-func.md
inverse|多项式求逆|多项式求逆|Polynomial Inverse
sqrt|多项式开方|多项式开方|Polynomial Square Root
division|多项式除法与取模|多项式除法 & 取模|Polynomial Division
log-exp|多项式对数与指数|多项式对数函数 & 指数函数|Polynomial Logarithm;Polynomial Exponential
trig|多项式三角函数|多项式三角函数|
inverse-trig|多项式反三角函数|多项式反三角函数|
math/poly/linear-recurrence.md
fiduccia|Fiduccia 算法|Fiduccia 算法|Fiduccia
bostan-mori|Bostan–Mori 线性递推算法|Bostan–Mori 算法|Bostan Mori
math/poly/shift.md
value-shift|连续点值平移|连续点值平移|
math/poly/comp-rev.md
reversion|形式幂级数复合逆|形式幂级数的复合逆|Series Reversion
math/combinatorics/combination.md
stars-bars|插板法|插板法|Stars and Bars
binomial|二项式定理|二项式定理|Binomial Theorem
binomial-inversion|二项式反演|二项式反演|Binomial Inversion
math/combinatorics/inclusion-exclusion-principle.md
min-max|Min–Max 容斥|Min-max 容斥|Min-Max Inclusion Exclusion
math/combinatorics/fibonacci.md
lucas-sequence|卢卡斯数列|卢卡斯数列|Lucas Sequence
fast-doubling|斐波那契快速倍增|快速倍增法|Fast Doubling
pisano|皮萨诺周期|Pisano 周期|Pisano Period
math/combinatorics/stirling.md
first|第一类斯特林数|第一类斯特林数（Stirling Number）|Stirling Numbers of the First Kind
second|第二类斯特林数|第二类斯特林数（Stirling Number）|Stirling Numbers of the Second Kind
math/combinatorics/partition.md
pentagonal|五边形数定理|五边形数定理|Pentagonal Number Theorem
math/combinatorics/polya.md
burnside|伯恩赛德引理|Burnside 引理|Burnside Lemma
math/linear-algebra/product.md
cross|向量外积|外积|Cross Product;叉积
mixed|向量混合积|混合积|Scalar Triple Product
math/linear-algebra/matrix.md
multiplication|矩阵乘法|矩阵乘法|Matrix Multiplication
recurrence|矩阵加速递推|矩阵加速递推|矩阵快速幂;Matrix Exponentiation
math/linear-algebra/basis.md
zassenhaus|Zassenhaus 线性基求交算法|Zassenhaus 算法|Zassenhaus
math/linear-algebra/char-poly.md
cayley-hamilton|凯莱–哈密顿定理|Cayley–Hamilton 定理|Cayley Hamilton
minimal-polynomial|矩阵最小多项式|最小多项式|Minimal Polynomial
math/linear-algebra/jordan.md
smith|史密斯标准型|Smith 标准型|Smith Normal Form
math/linear-programming.md
duality|线性规划对偶|对偶原理|Linear Programming Duality
integer|整数规划|整数规划|Integer Programming
math/probability/conditional-probability.md
bayes|贝叶斯公式|Bayes 公式|Bayes Theorem
math/probability/exp-var.md
conditional-expectation|条件期望|条件分布与条件期望|Conditional Expectation
variance|方差|方差|Variance
covariance|协方差|协方差与相关系数|Covariance
math/probability/concentration-inequality.md
union-bound|联合界|Union Bound|Union Bound;并集界
markov|马尔可夫不等式|Markov 不等式|Markov Inequality
chebyshev|切比雪夫不等式|Chebyshev 不等式|Chebyshev Inequality
chernoff|切尔诺夫界|Chernoff 不等式|Chernoff Bound
hoeffding|霍夫丁不等式|Hoeffding 不等式|Hoeffding Inequality
math/game-theory/impartial-game.md
nim|尼姆博弈|Nim 游戏|Nim
sg|斯普拉格–格伦迪理论|Sprague–Grundy 理论|SG 定理;SG 函数;Sprague Grundy
wythoff|威佐夫博弈|Wythoff 游戏|Wythoff Game
fibonacci-nim|斐波那契博弈|Fibonacci Nim 游戏|Fibonacci Nim
staircase-nim|阶梯尼姆博弈|阶梯 Nim 游戏|Staircase Nim
misere-nim|反常尼姆博弈|反常 Nim 游戏|Misere Nim
math/numerical/interp.md
lagrange|拉格朗日插值|Lagrange 插值法|Lagrange Interpolation
newton|牛顿插值|Newton 插值法|Newton Interpolation
math/numerical/integral.md
simpson|辛普森积分|普通辛普森法|Simpson Rule
adaptive-simpson|自适应辛普森积分|自适应辛普森法|Adaptive Simpson
math/numerical/gauss.md
gauss-jordan|高斯–约当消元|高斯–约当消元五步骤法|Gauss Jordan Elimination
xor|异或方程组消元|高斯–约当消元法解异或方程组|GF(2) Gaussian Elimination
math/order-theory.md
dilworth|迪尔沃斯定理|Dilworth 定理与 Mirsky 定理|Dilworth Theorem
mirsky|米尔斯基定理|Dilworth 定理与 Mirsky 定理|Mirsky Theorem
math/young-tableau.md
hook-length|勾长公式|勾长公式|Hook Length Formula
math/matroid.md
intersection|拟阵交|拟阵交|Matroid Intersection
ds/queue.md
deque|双端队列|双端队列|Deque;Double Ended Queue
circular|循环队列|循环队列|Circular Queue
ds/hash.md
chaining|拉链散列|拉链法|Separate Chaining
open-addressing|开放寻址散列|闭散列法|Open Addressing
ds/dsu.md
weighted|带权并查集|带权并查集|Weighted DSU
ds/binary-heap.md
dual|对顶堆|对顶堆|Dual Heap
ds/leftist-tree.md
randomized|随机可并堆|随机堆|Randomized Meldable Heap
skew|斜堆|斜堆|Skew Heap
ds/fenwick.md
two-dimensional|二维树状数组|二维树状数组|2D Fenwick Tree
ds/seg.md
dynamic|动态开点线段树|动态开点|Dynamic Segment Tree
lazy|线段树懒惰标记|区间修改与懒惰标记|Lazy Propagation
order-statistics|权值线段树|权值线段树|
ds/seg-merge-split.md
split|线段树分裂|线段树分裂|Segment Tree Split
ds/bst.md
balanced|平衡二叉搜索树|四种平衡性破坏的情况|Balanced BST;平衡树
ds/treap.md
fhq|无旋树堆|无旋 treap|FHQ Treap;无旋 Treap
ds/persistent-balanced.md
treap|可持久化无旋树堆|可持久化无旋转 Treap|Persistent Treap
wblt|可持久化重量平衡叶子树|可持久化 WBLT|Persistent WBLT
graph/dfs.md
dfs-order|深度优先遍历序|DFS 序列|DFS 序;DFS Order
graph/bfs.md
zero-one|0-1 广度优先搜索|双端队列 BFS|01 BFS;0-1 BFS
graph/tree-basic.md
morris|Morris 二叉树遍历|二叉树 Morris 遍历|Morris Traversal
graph/lca.md
binary-lifting|倍增最近公共祖先|倍增算法|Binary Lifting LCA
tarjan|Tarjan 离线最近公共祖先|Tarjan 算法|Tarjan Offline LCA
rmq|欧拉序最近公共祖先|用欧拉序列转化为 RMQ 问题|Euler Tour LCA
graph/hld.md
heavy|重链剖分|重链剖分|Heavy Light Decomposition
long|长链剖分|长链剖分|Long Chain Decomposition
graph/tree-divide.md
centroid|点分治|点分治|Centroid Decomposition
edge|边分治|边分治|Edge Decomposition
graph/topo.md
kahn|Kahn 拓扑排序|Kahn 算法|Kahn Algorithm
critical-path|关键路径法|关键路径和 AOE 网|Critical Path Method;AOE 网
graph/shortest-path.md
floyd|弗洛伊德最短路算法|Floyd 算法|Floyd;Floyd Warshall
bellman-ford|贝尔曼–福特算法|Bellman–Ford 算法|Bellman Ford
dijkstra|迪杰斯特拉算法|Dijkstra 算法|Dijkstra;迪克斯特拉算法
johnson|约翰逊全源最短路算法|Johnson 全源最短路径算法|Johnson Algorithm
graph/mst.md
kruskal|克鲁斯卡尔算法|Kruskal 算法|Kruskal
prim|普里姆算法|Prim 算法|Prim
boruvka|博鲁夫卡算法|Boruvka 算法|Boruvka;Borůvka
second-best|次小生成树|次小生成树|Second Best MST
reconstruction|克鲁斯卡尔重构树|Kruskal 重构树|Kruskal Reconstruction Tree
graph/scc.md
tarjan|Tarjan 强连通分量算法|Tarjan 算法|Tarjan SCC
kosaraju|Kosaraju 算法|Kosaraju 算法|Kosaraju
gabow|Gabow 算法|Gabow 算法|Gabow
graph/bcc.md
edge|边双连通分量|边双连通分量|Edge Biconnected Components
vertex|点双连通分量|点双连通分量|Vertex Biconnected Components
graph/cut.md
articulation|割点|割点|Articulation Point
bridge|桥|割边（有重边时）|Bridge;割边
graph/connectivity.md
menger|门格尔定理|Menger 定理|Menger Theorem
graph/euler.md
hierholzer|欧拉路径构造|欧拉回路/欧拉路径的构造|Hierholzer Algorithm;逐步插入回路法
graph/planar.md
dual|对偶图|对偶图|Dual Graph
euler-formula|平面图欧拉公式|欧拉公式|Euler Polyhedron Formula
graph/chord.md
mcs|最大势搜索|MCS 算法|MCS;Maximum Cardinality Search
graph/flow/max-flow.md
ford-fulkerson|福特–福尔克森增广算法|Ford–Fulkerson 增广|Ford Fulkerson
edmonds-karp|埃德蒙兹–卡普算法|Edmonds–Karp 算法|Edmonds Karp;EK 最大流
dinic|Dinic 最大流算法|Dinic 算法|Dinic;Dinitz
mpm|MPM 最大流算法|MPM 算法|MPM
isap|最短增广路改进算法|ISAP|ISAP;Improved Shortest Augmenting Path
push-relabel|预流推进算法|Push-Relabel 预流推进算法|Push Relabel
hlpp|最高标号预流推进算法|HLPP 算法|HLPP
max-flow-min-cut|最大流最小割定理|最大流最小割定理|Max Flow Min Cut Theorem
graph/flow/min-cost.md
ssp|逐次最短路费用流算法|SSP 算法|SSP;Successive Shortest Path
primal-dual|原始对偶费用流算法|Primal-Dual 原始对偶算法|Primal Dual Min Cost Flow
graph/flow/bound.md
feasible|上下界可行流|无源汇上下界可行流|Feasible Circulation
maximum|上下界最大流|有源汇上下界最大流|
minimum|上下界最小流|有源汇上下界最小流|
graph/graph-matching/graph-match.md
hall|霍尔定理|Hall 定理|Hall Theorem
tutte|图匹配图特定理|Tutte 定理|Tutte Theorem
graph/graph-matching/bigraph-match.md
kuhn|库恩增广匹配算法|Kuhn 算法|Kuhn Algorithm;匈牙利增广路算法
hopcroft-karp|霍普克罗夫特–卡普算法|Hopcroft–Karp 算法|Hopcroft Karp;HK 匹配
dulmage-mendelsohn|杜尔梅奇–门德尔松分解|Dulmage–Mendelsohn 分解|Dulmage Mendelsohn;DM 分解
vertex-cover|二分图最小点覆盖|二分图最小点覆盖|Konig Theorem;Kőnig 定理
path-cover|有向无环图最小路径覆盖|有向无环图最小路径覆盖|DAG Minimum Path Cover
graph/graph-matching/bigraph-weight-match.md
kuhn-munkres|库恩–芒克雷斯算法|Hungarian Algorithm（Kuhn–Munkres Algorithm）|KM 算法;Kuhn Munkres;Hungarian Algorithm
graph/graph-matching/general-match.md
blossom|带花树算法|带花树算法（Blossom Algorithm）|Blossom Algorithm
algebraic|代数一般图匹配|基于高斯消元的一般图匹配算法|Tutte Matrix Matching
graph/graph-matching/stable-match.md
gale-shapley|盖尔–沙普利算法|Gale–Shapley 算法|Gale Shapley;Deferred Acceptance
graph/prufer.md
cayley|凯莱公式|Cayley 公式 (Cayley's formula)|Cayley Formula
graph/matrix-tree.md
best|BEST 定理|BEST 定理|BEST Theorem
graph/dominator-tree.md
lengauer-tarjan|Lengauer–Tarjan 支配树算法|Lengauer–Tarjan 算法|Lengauer Tarjan;LT 算法
geometry/2d.md
ray-casting|光线投射点包含算法|光线投射算法 (Ray casting algorithm)|Ray Casting
winding-number|回转数点包含算法|回转数算法 (Winding number algorithm)|Winding Number
segment-intersection|线段相交判定|快速排斥实验与跨立实验|Segment Intersection
polar-sort|极角排序|极角序|Polar Angle Sort
geometry/distance.md
euclidean|欧氏距离|欧氏距离|Euclidean Distance
manhattan|曼哈顿距离|曼哈顿距离|Manhattan Distance;L1 距离
chebyshev|切比雪夫距离|切比雪夫距离|Chebyshev Distance;L∞ 距离
geometry/triangulation.md
delaunay|德劳内三角剖分|Delaunay 三角剖分|Delaunay Triangulation
voronoi|沃罗诺伊图|Voronoi 图|Voronoi Diagram;泰森多边形
geometry/convex-hull.md
andrew|Andrew 凸包算法|Andrew 算法求凸包|Andrew Monotone Chain;单调链凸包
graham|Graham 扫描法|Graham 扫描法|Graham Scan
minkowski|闵可夫斯基和|闵可夫斯基和|Minkowski Sum
three-dimensional|三维凸包|三维凸包|3D Convex Hull
geometry/scanning.md
orthogonal-range|正交范围查询|B 维正交范围|Orthogonal Range Query
misc/two-pointer.md
cycle-finding|快慢指针判环|在单向链表中找环|Floyd Cycle Finding;龟兔赛跑算法
misc/frac-programming.md
dinkelbach|丁克尔巴赫算法|Dinkelbach 算法|Dinkelbach
misc/random.md
mersenne-twister|梅森旋转随机数生成器|梅森缠绕器|Mersenne Twister;梅森缠绕器
lcg|线性同余随机数生成器|线性同余随机数生成器|LCG;Linear Congruential Generator
xorshift|异或移位随机数生成器|Xorshift|Xorshift
splitmix|SplitMix 随机数生成器|SplitMix|SplitMix
misc/fsm.md
dfa|确定性有限自动机|确定性有限状态自动机|DFA;Deterministic Finite Automaton
nfa|非确定性有限自动机|非确定性有限状态自动机|NFA;Nondeterministic Finite Automaton
dfa-minimization|有限自动机最小化|DFA 最小化|DFA Minimization
misc/expression.md
rpn|逆波兰表达式求值|表达式树与逆波兰表达式|RPN;Reverse Polish Notation
misc/main-element.md
majority-vote|摩尔多数投票算法|在线算法|Boyer Moore Majority Vote;摩尔投票法
topic/rmq.md
four-russians|四毛子算法|Four Russians|Four Russians Method
topic/bracket.md
catalan|括号序列计数|合法括号序列计数|Balanced Bracket Counting
contest/common-tricks.md
differential-testing|对拍|对拍|Differential Testing
memory-pool|内存池|内存池|Memory Pool
"""
SPLITS = {}
for _line in SPLIT_RULES.strip().splitlines():
    if _line.endswith(".md"):
        _path = _line
    else:
        _slug, _name, _section, _aliases = _line.split("|", 3)
        SPLITS.setdefault(_path, []).append((_slug, _name, _section, [a for a in _aliases.split(";") if a]))



def normalize(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    return re.sub(r'[\s_–—−\ufeff\u200b-]+', '', value)


def navigation(text):
    """Parse OI Wiki's nav list only, not general YAML or executable YAML tags."""
    inside, stack, rows = False, [], []
    for line in text.splitlines():
        if line == 'nav:':
            inside = True
            continue
        if not inside or not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line[0].isspace():
            break
        match = re.match(r'^(\s*)-\s+(.+)$', line)
        if not match or ':' not in match[2]:
            raise ValueError('Unsupported navigation syntax: ' + line)
        indent = len(match[1])
        label, value = (part.strip().strip('\'"') for part in match[2].rsplit(':', 1))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if value.endswith('.md'):
            rows.append((label, value, [name for _, name in stack]))
        elif not value:
            stack.append((indent, label))
        else:
            raise ValueError('Unsupported navigation target: ' + value)
    if not rows or not ROOTS.issubset({category[0] for _, _, category in rows}):
        raise ValueError('Missing major navigation categories')
    return rows


def headings(text):
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match[1][0]
            fence = marker if fence is None else (None if marker == fence else fence)
        elif fence is None:
            match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
            if match:
                result.append(match[1])
    return result


def page_url(path):
    tail = path[:-3]
    if tail.endswith('/index'):
        tail = tail[:-5]
    return 'https://oi-wiki.org/' + tail.rstrip('/') + '/'


# On an audited upstream path migration, map the new path[#suffix] to its old ID.
ID_OVERRIDES = {}


def entry_id(path, suffix=''):
    key = path + ('#' + suffix if suffix else '')
    return ID_OVERRIDES.get(key, 'oiwiki.' + path[:-3].replace('/', '.') + ('.' + suffix if suffix else ''))


def read_catalog(path):
    result = json.loads(path.read_text(encoding='utf-8'))
    validate(result)
    return result


def difficulty_index(luogu_id):
    """Public Luogu IDs are 1..8; this catalog's reference indices are 0..7."""
    if type(luogu_id) is not int or not 0 <= luogu_id <= 8:
        raise ValueError('Invalid native Luogu difficulty ID')
    return None if luogu_id == 0 else luogu_id - 1


def problem_distribution(entry, metadata, excluded=()):
    tags = {x['id'] for x in entry.get('luogu_tags', []) if x['relation'] != 'context'}
    samples = [s for s in metadata['problem_samples']
               if s['pid'] not in excluded and tags.intersection(s['tags'])]
    counts = [0] * 8
    for sample in samples:
        index = sample['difficulty_index']
        if index is not None:
            counts[index] += 1
    return {'scope': 'tag_union_curated_sample',
            'distribution': counts if any(counts) else None,
            'sample_size': len(samples),
            'unrated_count': sum(s['difficulty_index'] is None for s in samples),
            'sample_ids': [s['pid'] for s in samples],
            'representative': False, 'population_size': None}


def validate_luogu(catalog):
    metadata = catalog.get('luogu')
    if metadata is None:
        if any(set(e) & {'luogu_tags', 'knowledge_level', 'problem_difficulty'} for e in catalog['entries']):
            raise ValueError('Luogu entry metadata requires its shared snapshot')
        return {}
    if (not isinstance(metadata, dict) or type(metadata.get('schema_version')) is not int or
            metadata['schema_version'] != 1):
        raise ValueError('Invalid Luogu metadata schema')
    scale = metadata.get('difficulty_scale')
    if not isinstance(scale, list) or len(scale) != 8:
        raise ValueError('Expected eight Luogu difficulty references')
    for index, row in enumerate(scale):
        if (type(row.get('index')) is not int or type(row.get('luogu_id')) is not int or
                row['index'] != index or row['luogu_id'] != index + 1 or
                not isinstance(row.get('label'), str) or
                normalize(row['label']) != normalize(row.get('luogu_name', ''))):
            raise ValueError('Luogu index/native-ID/label mismatch')
    if metadata.get('unrated') != {'luogu_id': 0, 'index': None, 'label': '暂无评定'}:
        raise ValueError('Unrated must stay separate from index 0 (入门)')
    for key in ('tags', 'config', 'difficulty_manual'):
        source = metadata.get('sources', {}).get(key, {})
        if not isinstance(source.get('url'), str) or not source['url'].startswith('https://'):
            raise ValueError('Missing Luogu source: ' + key)
        if key != 'difficulty_manual' and (not source.get('retrieved_at') or
                not re.fullmatch(r'[0-9a-f]{64}', source.get('response_sha256', ''))):
            raise ValueError('Missing Luogu snapshot provenance: ' + key)
    types = metadata.get('tag_types', [])
    algorithm_types = [t['id'] for t in types if t.get('type') == 'Algorithm']
    if len(algorithm_types) != 1:
        raise ValueError('Algorithm tag type must be explicitly identified')
    algorithm_type = algorithm_types[0]
    type_ids = {t['id'] for t in types}
    tags = {}
    kinds = {'category', 'topic', 'algorithm', 'technique', 'data_structure', 'language', 'non_algorithm'}
    for tag in metadata.get('tags', []):
        if (not isinstance(tag, dict) or type(tag.get('id')) is not int or tag['id'] in tags or
                not isinstance(tag.get('name'), str) or not tag['name'].strip() or
                tag.get('type') not in type_ids or tag.get('kind') not in kinds):
            raise ValueError('Invalid/duplicate Luogu tag')
        if (tag['type'] != algorithm_type) != (tag['kind'] == 'non_algorithm'):
            raise ValueError('Non-algorithm taxonomy mismatch')
        tags[tag['id']] = tag
    if not tags:
        raise ValueError('Empty Luogu tag snapshot')
    for tag in tags.values():
        seen, cursor = set(), tag
        while cursor.get('parent') is not None:
            parent = cursor['parent']
            if type(parent) is not int or parent not in tags or parent in seen:
                raise ValueError('Invalid/cyclic Luogu tag hierarchy')
            seen.add(parent)
            cursor = tags[parent]
    samples = {}
    for sample in metadata.get('problem_samples', []):
        pid = sample.get('pid')
        if (not isinstance(pid, str) or not re.fullmatch(r'P[1-9][0-9]*', pid) or pid in samples or
                sample.get('url') != 'https://www.luogu.com.cn/problem/' + pid or
                not isinstance(sample.get('name'), str) or not sample['name'].strip() or
                not sample.get('retrieved_at') or
                not re.fullmatch(r'[0-9a-f]{64}', sample.get('response_sha256', ''))):
            raise ValueError('Invalid Luogu problem sample')
        if sample.get('difficulty_index') != difficulty_index(sample.get('luogu_difficulty_id')):
            raise ValueError('Sample difficulty index mismatch: ' + pid)
        tids = sample.get('tags')
        if (not isinstance(tids, list) or len(tids) != len(set(tids)) or
                any(type(t) is not int or t not in tags for t in tids)):
            raise ValueError('Invalid problem sample tags: ' + pid)
        samples[pid] = sample
    mapped = equivalent = references = provisional = contexts = 0
    for entry in catalog['entries']:
        links = entry.get('luogu_tags')
        if not isinstance(links, list):
            raise ValueError('Every adapted entry needs luogu_tags')
        seen = set()
        for link in links:
            tid = link.get('id')
            if (type(tid) is not int or tid in seen or tid not in tags or
                    tags[tid]['type'] != algorithm_type or
                    link.get('relation') not in ('equivalent', 'broader', 'context') or
                    not isinstance(link.get('note'), str) or not link['note'].strip()):
                raise ValueError('Invalid Luogu mapping: ' + entry['id'])
            if tags[tid]['kind'] in ('category', 'language') and link['relation'] != 'context':
                raise ValueError('Category/language tags are context only: ' + entry['id'])
            seen.add(tid)
        mapped += any(x['relation'] != 'context' for x in links)
        equivalent += any(x['relation'] == 'equivalent' for x in links)
        contexts += bool(links) and not any(x['relation'] != 'context' for x in links)
        knowledge = entry.get('knowledge_level', {})
        interval, confidence = knowledge.get('range'), knowledge.get('confidence')
        evidence = knowledge.get('evidence')
        if (confidence not in ('unknown', 'provisional', 'reference') or
                not isinstance(evidence, list) or
                any(not isinstance(v, str) or not v.startswith('https://') for v in evidence) or
                not isinstance(knowledge.get('note'), str) or not knowledge['note'].strip()):
            raise ValueError('Invalid knowledge reference: ' + entry['id'])
        if confidence == 'unknown':
            if interval is not None:
                raise ValueError('Unknown knowledge reference must have null range')
        elif (not isinstance(interval, list) or len(interval) != 2 or
              any(type(v) is not int for v in interval) or
              not 0 <= interval[0] < interval[1] <= 7 or not evidence):
            raise ValueError('Knowledge reference needs an evidenced interval: ' + entry['id'])
        if confidence == 'reference' and not any(s['url'] in evidence for s in samples.values()):
            raise ValueError('Reference requires a verified problem anchor: ' + entry['id'])
        references += confidence == 'reference'
        provisional += confidence == 'provisional'
        if entry.get('problem_difficulty') != problem_distribution(entry, metadata):
            raise ValueError('Stale/invalid tag-sample distribution: ' + entry['id'])
    return {'luogu_algorithm_tags': sum(t['type'] == algorithm_type for t in tags.values()),
            'mapped_entries': mapped, 'unmapped_entries': len(catalog['entries']) - mapped,
            'equivalent_mapped_entries': equivalent, 'broader_only_mapped_entries': mapped - equivalent,
            'context_only_entries': contexts, 'knowledge_references': references,
            'provisional_knowledge_references': provisional,
            'unknown_knowledge_references': len(catalog['entries']) - references - provisional,
            'problem_samples': len(samples), 'representative_sample': False}


def preserve_luogu(old, new):
    """An OI Wiki rebuild must not silently discard curated Luogu annotations."""
    if 'luogu' not in old:
        return new
    new['luogu'] = copy.deepcopy(old['luogu'])
    previous = {e['id']: e for e in old['entries']}
    for entry in new['entries']:
        annotation = previous.get(entry['id'], {})
        entry['luogu_tags'] = copy.deepcopy(annotation.get('luogu_tags', []))
        entry['knowledge_level'] = copy.deepcopy(annotation.get('knowledge_level', {
            'range': None, 'confidence': 'unknown', 'evidence': [], 'note': '新增条目，待独立校准'}))
        entry['problem_difficulty'] = problem_distribution(entry, new['luogu'])
    return new


def entry_view(entry, catalog, excluded=(), knowledge_only=False, identity_only=False):
    if identity_only:
        return {k: copy.deepcopy(v) for k, v in entry.items()
                if k in ('id', 'name', 'aliases', 'category', 'source_url', 'section')}
    result = copy.deepcopy(entry)
    if 'luogu' not in catalog:
        return result
    tags = {t['id']: t for t in catalog['luogu']['tags']}
    result['luogu_tags'] = [dict(link, name=tags[link['id']]['name'], kind=tags[link['id']]['kind'])
                            for link in result['luogu_tags']]
    # Do not let the target's cached public label leak through its reference anchor.
    forbidden = {'https://www.luogu.com.cn/problem/' + pid for pid in excluded}
    if forbidden.intersection(result['knowledge_level']['evidence']):
        result['knowledge_level'] = {'range': None, 'confidence': 'unknown', 'evidence': [],
                                    'note': '本参考包含被排除题目的证据，本次隐藏以避免循环校准'}
    result['problem_difficulty'] = problem_distribution(entry, catalog['luogu'], excluded)
    if knowledge_only:
        result.pop('problem_difficulty', None)
    return result


def find_tags(metadata, query):
    matches = [t for t in metadata['tags'] if str(t['id']) == query or normalize(t['name']) == normalize(query)]
    if not matches:
        raise ValueError('Unknown Luogu tag ID/name: ' + query)
    return matches


def refresh_luogu(catalog, pids):
    """Bounded explicit refresh of already observed public resources, no scanning."""
    if 'luogu' not in catalog:
        raise ValueError('Initialize and review mappings before refreshing Luogu metadata')
    if len(pids) > 40 or len(set(pids)) != len(pids) or any(not re.fullmatch(r'P[1-9][0-9]*', p) for p in pids):
        raise ValueError('Refresh accepts at most 40 distinct explicit P-series IDs, never a range scan')
    result = copy.deepcopy(catalog)
    metadata = result['luogu']
    def fetch(url):
        time.sleep(2)
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; CPScore catalog reference check)',
                                        'Referer': 'https://www.luogu.com.cn/'})
        with urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise ValueError('Public resource unavailable; stop refresh')
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError('Public resource exceeds 4 MB')
        return raw, {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                     'response_sha256': hashlib.sha256(raw).hexdigest()}
    raw, source = fetch('https://www.luogu.com.cn/_lfe/tags')
    snapshot = json.loads(raw)
    old_tags = {t['id']: t for t in metadata['tags']}
    new_tags = []
    for tag in snapshot['tags']:
        if tag['id'] not in old_tags or any(tag[k] != old_tags[tag['id']][k] for k in ('name', 'type', 'parent')):
            raise ValueError('Tag taxonomy changed; review semantic mappings before refreshing')
        new_tags.append(dict(tag, kind=old_tags[tag['id']]['kind']))
    if {t['id'] for t in new_tags} != set(old_tags):
        raise ValueError('Tag IDs disappeared; review before refreshing')
    metadata['tags'], metadata['tag_types'] = sorted(new_tags, key=lambda t: t['id']), snapshot['types']
    metadata['sources']['tags'] = dict(source, version=snapshot['_version'])
    raw, source = fetch('https://www.luogu.com.cn/_lfe/config')
    config = json.loads(raw)
    if {d['id'] for d in config['ProblemDifficulty']} != set(range(9)):
        raise ValueError('Difficulty IDs changed; review numbering before refresh')
    for row in metadata['difficulty_scale']:
        actual = next((d for d in config['ProblemDifficulty'] if d['id'] == row['luogu_id']), None)
        if not actual or normalize(actual['name']) != normalize(row['label']):
            raise ValueError('Difficulty taxonomy changed; review numbering and labels')
    metadata['sources']['config'] = dict(source, version=config['_version'])
    samples = {s['pid']: s for s in metadata['problem_samples']}
    changed = set()
    for pid in pids:
        url = 'https://www.luogu.com.cn/problem/' + pid
        raw, source = fetch(url)
        match = re.search(r'<script[^>]+id="lentille-context"[^>]*>(.*?)</script>', raw.decode('utf-8'), re.S)
        if not match:
            raise ValueError('No public page data; stop without bypassing login or access restrictions')
        page = json.loads(match[1])
        problem = page.get('data', page.get('currentData', {})).get('problem', {})
        if problem.get('pid') != pid:
            raise ValueError('Problem identity mismatch')
        previous = samples.get(pid)
        if previous and (previous['luogu_difficulty_id'] != problem['difficulty'] or
                         set(previous['tags']) != set(problem['tags'])):
            changed.add(url)
        samples[pid] = dict(source, pid=pid, name=problem['name'], tags=problem['tags'],
                            luogu_difficulty_id=problem['difficulty'],
                            difficulty_index=difficulty_index(problem['difficulty']))
    metadata['problem_samples'] = [samples[p] for p in sorted(samples)]
    for entry in result['entries']:
        entry['problem_difficulty'] = problem_distribution(entry, metadata)
        reference = entry['knowledge_level']
        if changed.intersection(reference['evidence']) and reference['confidence'] == 'reference':
            reference['confidence'] = 'provisional'
            reference['note'] += '；参考题元数据发生变化，需复核原区间，不自动随标签或题目等级调整门槛'
    validate(result)
    return result


def write_catalog(path, catalog):
    validate(catalog)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def validate(catalog, source=None):
    ids, names = set(), set()
    if not isinstance(catalog, dict):
        raise ValueError('Catalog must be an object')
    if not isinstance(catalog.get('source'), dict) or not isinstance(catalog.get('entries'), list):
        raise ValueError('Catalog requires source metadata and an entries list')
    if type(catalog.get('schema_version')) is not int or catalog['schema_version'] != 1 or not catalog.get('entries'):
        raise ValueError('Invalid or empty catalog')
    for entry in catalog['entries']:
        if not isinstance(entry, dict):
            raise ValueError('Knowledge entries must be objects')
        if 'section' in entry and (not isinstance(entry['section'], str) or not entry['section'].strip()):
            raise ValueError('Invalid source section')
        if set(entry) - {'id', 'name', 'aliases', 'category', 'source_url', 'section',
                         'luogu_tags', 'knowledge_level', 'problem_difficulty'}:
            raise ValueError('Unexpected entry fields')
        for key in ('id', 'name', 'source_url'):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError('Missing entry field: ' + key)
        if not re.fullmatch(r'oiwiki\.[a-z0-9.-]+', entry['id']) or entry['id'] in ids:
            raise ValueError('Invalid or duplicate ID: ' + entry['id'])
        if normalize(entry['name']) in names:
            raise ValueError('Duplicate canonical name: ' + entry['name'])
        ids.add(entry['id']); names.add(normalize(entry['name']))
        for key in ('category', 'aliases'):
            if not isinstance(entry.get(key), list) or any(not isinstance(x, str) or not x.strip() for x in entry[key]):
                raise ValueError('Invalid ' + key + ': ' + entry['id'])
        if not entry['category'] or len(set(map(normalize, entry['aliases']))) != len(entry['aliases']):
            raise ValueError('Empty category or duplicate aliases: ' + entry['id'])
        url = urlparse(entry['source_url'])
        if url.scheme != 'https' or url.netloc != 'oi-wiki.org' or url.query or url.fragment or '..' in url.path.split('/'):
            raise ValueError('Invalid source URL: ' + entry['source_url'])
        if source:
            rel = url.path.strip('/')
            page = source / 'docs' / (rel + '.md')
            if not page.is_file():
                page = source / 'docs' / rel / 'index.md'
            if not page.is_file():
                raise ValueError('Missing source: ' + entry['source_url'])
            if entry.get('section') and entry['section'] not in headings(page.read_text(encoding='utf-8')):
                raise ValueError('Missing source section: ' + entry['id'])
    if source:
        metadata = catalog['source']
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        if revision != metadata['revision']:
            raise ValueError('Source revision differs from the catalog snapshot')
        if hashlib.sha256((source / 'mkdocs.yml').read_bytes()).hexdigest() != metadata['navigation_sha256']:
            raise ValueError('Navigation hash differs from the catalog snapshot')
        for path, expected in metadata['pages_sha256'].items():
            if '..' in Path(path).parts or Path(path).is_absolute():
                raise ValueError('Invalid source path')
            if hashlib.sha256((source / 'docs' / path).read_bytes()).hexdigest() != expected:
                raise ValueError('Source hash differs: ' + path)
    if not ROOTS.issubset({e['category'][0] for e in catalog['entries']}):
        raise ValueError('Incomplete major category coverage')
    return {'entries': len(ids), 'categories': dict(sorted(Counter(e['category'][0] for e in catalog['entries']).items())),
            **validate_luogu(catalog)}


def build(source):
    source = source.resolve()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'mkdocs.yml', 'docs'], cwd=source).returncode:
        raise ValueError('Update source contains uncommitted changes')
    nav_bytes = (source / 'mkdocs.yml').read_bytes()
    rows = navigation(nav_bytes.decode('utf-8'))
    entries, pages, exclusions = [], {}, Counter()
    for label, path, category in rows:
        if category[0] not in ROOTS and path not in EXTRA_PAGES and path not in SPLITS:
            exclusions['non_algorithm_sections'] += 1
            continue
        if path.endswith('/index.md') or path in SKIP:
            exclusions['overview_or_non_algorithm_pages'] += 1
            continue
        raw = (source / 'docs' / path).read_bytes()
        pages[path] = hashlib.sha256(raw).hexdigest()
        if path in MERGE:
            exclusions['merged_duplicate_pages'] += 1
        elif path == 'contest/common-tricks.md':
            exclusions['section_only_pages'] += 1
        else:
            name, groups = EXTRA_PAGES.get(path, (NAMES.get(path, label), category))
            composite = path in {'math/probability/exp-var.md', 'math/linear-algebra/product.md'} or bool(re.search(r'[&|与]', label))
            aliases = ([label] if not composite and label != '基本概念' else []) + ALIASES.get(path, '').split('|')
            # Parenthesized nav abbreviations are also names provided by the source.
            aliases += re.findall(r'[（(]([A-Za-z][A-Za-z0-9 *-]*)[）)]', label)
            aliases = list({normalize(a): a for a in aliases if a and normalize(a) != normalize(name)}.values())
            entries.append({'id': entry_id(path), 'name': name, 'aliases': aliases,
                            'category': groups, 'source_url': page_url(path)})
        for suffix, name, section, aliases in SPLITS.get(path, []):
            if section not in headings(raw.decode('utf-8')):
                raise ValueError('Split section changed: ' + path + ': ' + section)
            entries.append({'id': entry_id(path, suffix), 'name': name, 'aliases': aliases,
                            'category': EXTRA_PAGES.get(path, ('', category))[1],
                            'source_url': page_url(path), 'section': section})
    for entry in entries:
        entry['aliases'] = list({normalize(a): a for a in entry['aliases']
                                 if normalize(a) != normalize(entry['name'])}.values())
    result = {'schema_version': 1, 'source': {
        'name': 'OI Wiki', 'repository': 'https://github.com/OI-wiki/OI-wiki', 'revision': commit,
        'navigation_url': 'https://github.com/OI-wiki/OI-wiki/blob/' + commit + '/mkdocs.yml',
        'navigation_sha256': hashlib.sha256(nav_bytes).hexdigest(),
        'pages_sha256': dict(sorted(pages.items())), 'navigation_pages': len(rows),
        'exclusions': dict(exclusions),
        'attribution': 'OI Wiki Team and contributors; names and classifications extracted and normalized by CPScore',
        'license': 'CC BY-SA 4.0 with upstream SATA notice; see docs/algorithm-catalog.md',
    }, 'entries': sorted(entries, key=lambda e: e['id'])}
    validate(result, source)
    return result


def emit(value):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=Path(os.environ.get('CPSCORE_CATALOG') or str(Path(__file__).parent)))
    commands = parser.add_subparsers(dest='command', required=True)
    search = commands.add_parser('search', help='Search names, aliases, IDs and category paths')
    search.add_argument('query', nargs='?', default='')
    search.add_argument('--category', default='')
    search.add_argument('--limit', type=int, default=20)
    search.add_argument('--offset', type=int, default=0)
    search.add_argument('--luogu-tag', help='exact Luogu tag ID or name; no fuzzy equivalence')
    search.add_argument('--exclude-problem', action='append', default=[])
    search.add_argument('--knowledge-only', action='store_true')
    search.add_argument('--identity-only', action='store_true', help='hide all external annotations in blind evaluation')
    get = commands.add_parser('get'); get.add_argument('id')
    get.add_argument('--exclude-problem', action='append', default=[])
    get.add_argument('--knowledge-only', action='store_true')
    get.add_argument('--identity-only', action='store_true')
    tag = commands.add_parser('tag', help='reverse lookup from an exact Luogu tag ID/name')
    tag.add_argument('query')
    tag.add_argument('--exclude-problem', action='append', default=[])
    tag.add_argument('--knowledge-only', action='store_true')
    tag.add_argument('--identity-only', action='store_true')
    commands.add_parser('levels', help='0..7 reference indices and 1..8 public IDs')
    commands.add_parser('stats', help='mapping coverage and evidence counts')
    commands.add_parser('categories')
    check = commands.add_parser('validate'); check.add_argument('--source', type=Path)
    update = commands.add_parser('update'); update.add_argument('--source', required=True, type=Path)
    update.add_argument('--accept-source-moves', action='store_true',
                        help='Accept audited URL/section moves; dropped IDs are still rejected')
    refresh = commands.add_parser('refresh-luogu', help='bounded, explicit refresh; stop on taxonomy changes or access restrictions')
    refresh.add_argument('--pid', action='append', default=[], help='one explicit problem ID; repeat at most 40 times')
    args = parser.parse_args()
    try:
        if any(not re.fullmatch(r'P[1-9][0-9]*', pid) for pid in getattr(args, 'exclude_problem', [])):
            raise ValueError('exclude-problem requires an explicit P-series problem ID')
        if getattr(args, 'knowledge_only', False) and getattr(args, 'identity_only', False):
            raise ValueError('Choose either knowledge-only or identity-only')
        if args.catalog.is_dir():
            args.catalog = args.catalog / 'catalog.json'
        if args.command == 'update':
            result = build(args.source)
            if args.catalog.exists():
                old = read_catalog(args.catalog)
                identities = {e['id']: (e['source_url'], e.get('section')) for e in result['entries']}
                dropped = [e['id'] for e in old['entries'] if e['id'] not in identities]
                moved = [e['id'] for e in old['entries'] if e['id'] in identities and
                         identities[e['id']] != (e['source_url'], e.get('section'))]
                if dropped or (moved and not args.accept_source_moves):
                    raise ValueError('Review ID migration before replacing catalog: ' + str(dropped + moved))
                result = preserve_luogu(old, result)
            write_catalog(args.catalog, result)
            emit(validate(result, args.source)); return
        catalog = read_catalog(args.catalog)
        if args.command == 'refresh-luogu':
            result = refresh_luogu(catalog, args.pid)
            write_catalog(args.catalog, result)
            emit(validate(result))
        elif args.command == 'validate':
            emit(validate(catalog, args.source))
        elif args.command == 'stats':
            emit(validate(catalog))
        elif args.command == 'levels':
            if 'luogu' not in catalog:
                raise ValueError('Luogu adaptation is not available in this catalog')
            emit({'scale': catalog['luogu']['difficulty_scale'], 'unrated': catalog['luogu']['unrated'],
                  'note': 'Reference indices 0..7; public IDs and existing CPScore output levels 1..8; unrated=0 is not index 0'})
        elif args.command == 'tag':
            if 'luogu' not in catalog:
                raise ValueError('Luogu adaptation is not available in this catalog')
            matches = find_tags(catalog['luogu'], args.query)
            tids = {t['id'] for t in matches}
            emit({'tags': matches, 'entries': [entry_view(e, catalog, args.exclude_problem, args.knowledge_only, args.identity_only)
                  for e in catalog['entries'] if tids.intersection(x['id'] for x in e['luogu_tags'])]})
        elif args.command == 'categories':
            counts = Counter('/'.join(e['category'][:n]) for e in catalog['entries'] for n in range(1, len(e['category']) + 1))
            emit(dict(sorted(counts.items())))
        elif args.command == 'get':
            match = next((e for e in catalog['entries'] if e['id'] == args.id), None)
            if match is None:
                raise ValueError('Unknown knowledge ID: ' + args.id)
            emit(entry_view(match, catalog, args.exclude_problem, args.knowledge_only, args.identity_only))
        else:
            if args.limit < 1 or args.offset < 0:
                raise ValueError('limit must be positive and offset must be nonnegative')
            query, category = normalize(args.query), normalize(args.category)
            matches = []
            tags = {t['id']: t for t in catalog.get('luogu', {}).get('tags', [])}
            selected_tags = None
            if args.luogu_tag:
                if 'luogu' not in catalog:
                    raise ValueError('Luogu adaptation is not available in this catalog')
                selected_tags = {t['id'] for t in find_tags(catalog['luogu'], args.luogu_tag)}
            for e in catalog['entries']:
                fields = [e['id'], e['name']] + e['aliases'] + ['/'.join(e['category'])]
                fields += [tags[x['id']]['name'] for x in e.get('luogu_tags', [])]
                if category and not normalize('/'.join(e['category'])).startswith(category):
                    continue
                if selected_tags is not None and not selected_tags.intersection(x['id'] for x in e.get('luogu_tags', [])):
                    continue
                if not query or any(query in normalize(field) for field in fields):
                    exact = any(query == normalize(field) for field in fields[:2] + e['aliases'])
                    matches.append((not exact, e['id'], e))
            matches.sort(key=lambda row: row[:2])
            emit({'total': len(matches), 'offset': args.offset, 'limit': args.limit,
                  'has_more': args.offset + args.limit < len(matches),
                  'entries': [entry_view(row[2], catalog, args.exclude_problem, args.knowledge_only, args.identity_only)
                              for row in matches[args.offset:args.offset + args.limit]]})
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
