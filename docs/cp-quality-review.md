# 题目质量评分

依据人类题解，检索先例并评价考点原创性与算法设计质量。提供完整题面、约束、人类题解及已知相关来源；缺少核心算法或关键观察时暂不定级。

```text
$cp-quality-review 依据 statement.md 和人类题解 editorial.md，检索先例并评价考点原创性与算法设计质量。
```

输出 A+、A、B+、B、C、D、F 或 S，附用途、核心考点、先例对应和决定性设计理由。A+、A、B+ 面向正式比赛，B、C 面向训练，D、F 不推荐作为原创赛题；S 是严重不适合竞赛的研究问题。边界见[评级协议](../skills/cp-quality-review/references/rating.md)，不按观察数量或分项平均定级。

理解给定解法，不独立解题或探索额外算法。检索覆盖 CPRet、arXiv 和普通网页，阅读接近来源核对条件；论文重合须同时满足重要性和赛时难以独立推导的门槛，不按命中数量降级。无网络或来源不可访问时说明实际范围，不宣称完成查重。

可选[检索脚本](../skills/cp-quality-review/scripts/retrieve.py)负责候选索引、原文缓存和分段读取，不负责评级。[检索说明](../skills/cp-quality-review/references/retrieval.md)提供调用与回退方式；没有 Python 时直接使用宿主工具。

[技能入口](../skills/cp-quality-review/SKILL.md) · [报告协议](../skills/cp-quality-review/references/report.md) · [返回目录](README.md)
