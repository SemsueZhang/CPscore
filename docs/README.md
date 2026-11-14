# Skill 使用说明

按要完成的任务选择技能。每份说明介绍所需材料、调用方式、结果含义，以及对应案例或已有评测。

| 任务 | 使用说明 | 技能入口 |
| --- | --- | --- |
| 题面审核 | [cp-statement-review](cp-statement-review.md) | [SKILL.md](../skills/cp-statement-review/SKILL.md) |
| 题解审核 | [cp-editorial-review](cp-editorial-review.md) | [SKILL.md](../skills/cp-editorial-review/SKILL.md) |
| 标程审核 | [cp-solution-review](cp-solution-review.md) | [SKILL.md](../skills/cp-solution-review/SKILL.md) |
| 数据审核 | [cp-data-review](cp-data-review.md) | [SKILL.md](../skills/cp-data-review/SKILL.md) |
| 题目质量评分 | [cp-quality-review](cp-quality-review.md) | [SKILL.md](../skills/cp-quality-review/SKILL.md) |
| 洛谷难度预测 | [cp-difficulty-luogu](cp-difficulty-luogu.md) | [SKILL.md](../skills/cp-difficulty-luogu/SKILL.md) |
| 比赛总评 | [cp-contest-review](cp-contest-review.md) | [SKILL.md](../skills/cp-contest-review/SKILL.md) |
| 选手表现预测 | [cp-performance-predict](cp-performance-predict.md) | [SKILL.md](../skills/cp-performance-predict/SKILL.md) |

## 专题总结

- [题目难度评价现状总结](difficulty-assessment-summary.md)：当前目标、历史结果及验证边界。
- [Difficulty 版本记录](difficulty-versions.md)：新旧版本与专家规则的更新流程。原 [cp-difficulty-rate](cp-difficulty-rate.md) 作为历史说明及 CF/AT 工具入口保留。

## 材料评分

题面、题解、标程和数据审核从 10 分起，按已确认的独立根因扣分：

```text
评分 = 10 − 10×Fatal数 − 2×Major数 − Minor数
```

评分允许负分。同一根因只按最高等级扣一次。四类审核各自定义缺陷等级，例如错误程序本身的严重程度不能直接作为数据缺陷的等级。一般未证实疑点不扣实质错误分；题解审核采用下述严格通过策略。

关键核验完成后，9～10 分为“优秀，具备推荐资格”，6～8 分为“尚可，值得打磨”，5 分及以下为“不合格，存在重大问题”。题面与数据审核的未完成状态按各自协议处理，不能把暂定高分视为完整结论。

题面与题解使用同源的格式脚本和[共用格式协议](../shared/review-format/format.md)。脚本优先静态检查，审核 LLM 对不确定项作有来源证据的复核，再交脚本统一计分。同类已确认错误 1～2 处 Major −2、至少 3 处 Fatal −10，同类只扣一次，不跨文章累计；Warning 不充当已确认次数。两个技能均可单独复制安装。

题解审核全程由机器判断，数学、教学、表达与格式共用上述分数，不重复设置子分。适用必查项不能严格确认合规时，按 Major −2 计入“无法确认合规”，区别于已证实违规，具体范围和去重见[题解评分协议](../skills/cp-editorial-review/references/scoring.md)。报告同时给合规结论与数值档次；存在任何未通过项都判不合规，只有合规且达优秀档才具备推荐资格。此状态只评价题解材料，不直接替代题目质量等级、难度或比赛总评。

## 其他结果

- **题目质量**依据人类题解和先例，综合考点原创性与算法设计质量，使用 A+ / A / B+ / B / C / D / F / S。A+、A、B+ 面向正式比赛，B、C 面向训练，D、F 不推荐作为原创赛题，S 单列为研究问题。
- **难度预测**给出洛谷原生 1～8 档及独立解题的主要障碍。K/T/I 仅用于分析，不强制数值化。0 表示未知，不参与 Benchmark 计分。
- **比赛总评**评价题目组合，给出推荐、合格或不合格。
- **表现预测**给出选手可能的路线、时间和得分区间，不作质量评级。

## 安装与报告

安装和调用见[安装说明](../install.md)。每个技能的执行规则保存在自己的 `SKILL.md` 与随包 Reference 中，可独立安装，无需同时复制本目录或其他技能。

默认在对话中交付 Markdown 报告，需要文件时在请求中指定保存位置。报告中的实测、证明、预测和修改建议各有不同的证据含义，有限测试不替代证明，建议也不代表已经修复。

[返回项目首页](../README.md)
