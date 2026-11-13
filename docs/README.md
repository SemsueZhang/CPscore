# Skill 使用说明

按要完成的任务选择技能。每份说明介绍所需材料、调用方式、结果含义，以及对应案例或已有评测。

| 任务 | 使用说明 | 技能入口 |
| --- | --- | --- |
| 题面审核 | [cp-statement-review](cp-statement-review.md) | [SKILL.md](../skills/cp-statement-review/SKILL.md) |
| 题解审核 | [cp-editorial-review](cp-editorial-review.md) | [SKILL.md](../skills/cp-editorial-review/SKILL.md) |
| 标程审核 | [cp-solution-review](cp-solution-review.md) | [SKILL.md](../skills/cp-solution-review/SKILL.md) |
| 数据审核 | [cp-data-review](cp-data-review.md) | [SKILL.md](../skills/cp-data-review/SKILL.md) |
| 题目质量评分 | [cp-quality-review](cp-quality-review.md) | [SKILL.md](../skills/cp-quality-review/SKILL.md) |
| 题目难度评定 | [cp-difficulty-rate](cp-difficulty-rate.md) | [SKILL.md](../skills/cp-difficulty-rate/SKILL.md) |
| 比赛总评 | [cp-contest-review](cp-contest-review.md) | [SKILL.md](../skills/cp-contest-review/SKILL.md) |
| 选手表现预测 | [cp-performance-predict](cp-performance-predict.md) | [SKILL.md](../skills/cp-performance-predict/SKILL.md) |

## 专题总结

- [题目难度评价现状总结](difficulty-assessment-summary.md)：当前三维标准、总档形成方式、平台换算及验证范围。

## 材料评分

题面、题解、标程和数据审核从 10 分起，按已确认的独立根因扣分：

```text
评分 = 10 − 10×Fatal数 − 2×Major数 − Minor数
```

评分允许负分。同一根因只按最高等级扣一次，疑点不扣分。四类审核各自定义缺陷等级，例如错误程序本身的严重程度不能直接作为数据缺陷的等级。

关键核验完成后，9～10 分为“优秀，具备推荐资格”，6～8 分为“尚可，值得打磨”，5 分及以下为“不合格，存在重大问题”。结果还需结合未核验范围和未决疑点阅读。题面、题解与数据审核在关键核验未完成时按各自协议标记暂定分及完成状态，不能把暂定高分视为完整审核结论。

## 其他结果

- **题目质量**依据人类题解和先例，综合考点原创性与算法设计质量，使用 A+ / A / B+ / B / C / D / F / S。A+、A、B+ 面向正式比赛，B、C 面向训练，D、F 不推荐作为原创赛题，S 单列为研究问题。
- **难度评定**给出 K/T/I 三维、整题总档和平台参照，和材料质量分分别判断。
- **比赛总评**评价题目组合，给出推荐、合格或不合格。
- **表现预测**给出选手可能的路线、时间和得分区间，不作质量评级。

## 安装与报告

安装和调用见[安装说明](../install.md)。每个技能的执行规则保存在自己的 `SKILL.md` 与随包 Reference 中，可独立安装，无需同时复制本目录或其他技能。

默认在对话中交付 Markdown 报告，需要文件时在请求中指定保存位置。报告中的实测、证明、预测和修改建议各有不同的证据含义，有限测试不替代证明，建议也不代表已经修复。

[返回项目首页](../README.md)
