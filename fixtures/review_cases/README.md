# 打分测试数据

`cases.json` 为题面、程序和题解打分技能分别提供 correct、fatal、major、minor、boundary 五类预期结果。其中历史 ID `editorial_minor` 保留便于追踪，现按核心最优性证明缺失判 Major（7 分），另有正确算法但证明漏洞的 Major 和局部公式错误的 Minor。`context/` 保存任务定义，`artifacts/` 保存打分材料。

材料由下列题目摘编、限制规模或施加变异，使用时以本目录任务定义为准：

| 来源 | 任务模型 |
| --- | --- |
| [P5020 / NOIP 2018 货币系统](https://www.luogu.com.cn/problem/P5020) | 无限张正面额货币的金额可表示性 |
| [P1083 / NOIP 2012 借教室](https://www.luogu.com.cn/problem/P1083) | 闭区间占用、订单顺序和首次失败编号，使用正容量及正需求 |
| [P17832 / CSP-S 2026 地铁](https://www.luogu.com.cn/problem/P17832) | 站厅、站台和地铁网络中的最小步行时间 |

`sources` 保存来源和上下文，`coverage_templates` 保存共享核验记录，每例的 `coverage_overrides` 覆盖不同项，`adjudication` 保存预期分级和结果。boundary 用于检查常规符号、标准算法及合理省略是否被误扣分。

运行数据与算分测试：`python3 -m unittest tests.test_review_fixtures -v`。测试只读取材料及预期结果。测试智能体时，将 artifact 与对应 context 交给技能，再将生成报告与 adjudication 比较。

`solution_major` 的判据是 64 位 CPython 中至少 76.29 MiB 的确定性无用列表分配，不声称已测得超时或超内存。`statement_major` 明示可能单向却不给方向字段，读者必须通过树的桥割和全体有序站对可达性推导出每条线双向，属于核心规则的实质说明缺漏。形式化定义本身和文字风格不作为扣分理由。以上为人工裁定的回归材料，不能当作真实模型评审成功记录。
