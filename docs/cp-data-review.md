# 数据审核

评价原测试集和判定机制区分正确程序与错误程序的能力。提供题面、题解、参考程序、原测试集与答案、Checker／Interactor、时空限制、子任务权重与分组依赖。只有生成器时，应能按原参数和种子重建原集。

```text
$cp-data-review 结合 statement.md、editorial.md 和 std.cpp，审核原测试集与正式计分规则，给出错解成绩和补点建议。
```

报告给出 10 分制评分与完成状态。每项列独立错解机制、证错依据、原集成绩、正常部分分、额外收益、相关计分单元与修正建议。按实际评测失真定级，不以固定分数或点数比例机械划线。

漏检结论同时需要证实候选错误，以及其在原集上实际获得不应取得的成绩。正确慢解和正常部分分不算漏洞。外加反例只用于证错与补点，不并入原集成绩；修订后另行实测。无执行条件时说明未实测范围，不编造通过率或数据完备性。

[技能入口](../skills/cp-data-review/SKILL.md) · [核验方法](../skills/cp-data-review/references/verification.md) · [评分协议](../skills/cp-data-review/references/scoring.md) · [返回目录](README.md)
