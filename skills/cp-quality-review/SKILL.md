---
name: cp-quality-review
description: 以给定题解为起点，检查替代解法并检索先例，评价算法竞赛题目的考点原创性与算法设计质量，给出 A+、A、B+、B、C+、C、D、F 或 S。
---

# 题目质量评分

依据给定人类题解、已核实替代路线和先例，评价核心考点原创性及算法设计。使用宿主工具，可独立安装。

算法知识、洛谷标签和知识门槛统一查询 `CPSCORE_CATALOG`（仓库默认 `resources/algorithm-catalog/`）中的 `catalog.json`；可用 `catalog.py search/get/tag/levels`，无 Python 时读同一 JSON。按 `luogu_tags.relation` 区分同义、较宽与上下文。`knowledge_level` 是知识参考，`problem_difficulty` 是非代表性标签样本，均不直接决定整题难度或选手掌握度。目录缺失时保留文字名、报告依赖缺失，不编造 ID／难度，不复制目录数据。

## 流程

1. 理解完整题面、约束和各给定解法，整理关键观察、转化、技术依赖、推导与复杂度，注明所评路线。
2. 按[替代解法检查](references/rubric.md#替代解法检查)主动检查朴素方法、步骤简化、常见转化或绕过核心考点的具体候选；核实完整算法、正确性、全范围复杂度及实现条件。不要求从零求解或穷举另解。
3. 按[检索协议](references/retrieval.md)覆盖 CPRet、arXiv 和普通网页，阅读接近原文，比较条件、可复用步骤与独立亮点。论文重合按[论文门槛](references/rubric.md#论文先例门槛)判断重要性和赛时可推导性。检索发现的新路线同样须核实；需要缓存时用随包 `scripts/retrieve.py`。
4. 按[评级协议](references/rubric.md)核对从先例到本题需要独立推出的步骤，重评实际核心考点，再判断设计质量、加号标准及 S 资格。
5. 按[报告协议](references/report.md)交付；改变结论的另解及待核实候选前置说明，核心材料缺口不靠猜测补全。
