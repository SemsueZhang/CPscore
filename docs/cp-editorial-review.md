# 题解审核

检查题解中的声明、推导、全题覆盖、教学表达和格式。提供题面、全部约束、完整题解及其中声明正确的所有做法，注明目标读者和投稿规范。

```text
$cp-editorial-review 结合 statement.md 审核 editorial.md，给出评分、依据和修改建议。
```

报告先给合规结论、10 分制评分和档次，再分别列内容与格式问题，说明位置、短摘录、失效依据、影响及最小修改方向。无问题时概述适用范围的核验依据；重审说明结论变化。

只依据原文，不代补条件、初始化、关键证明或正确代码，再把修复版当成原稿成立。覆盖全部合法输入、数值范围和总成本，手算样例，代码默认只作一次静态对照。人类思维、表达、AIGC 与题外内容按证据判断；内部材料分按根因去重，外部 AIGC 项采用评分协议中的审核判定。

格式辅助可在仓库内运行；安装后使用对应 Skill 内的脚本路径：

```sh
python3 skills/cp-editorial-review/scripts/format_lint.py --check
python3 skills/cp-editorial-review/scripts/format_lint.py editorial.md
```

LLM 仍须检查脚本未覆盖的材料，并按[复核接口](../skills/cp-editorial-review/references/format.md#llm-格式复核接口)合并证据。没有 Python 时按同一协议继续审核，不因工具故障扣稿件分。静态对照不代表编译运行通过，源码扫描不代表页面已实渲染。

[技能入口](../skills/cp-editorial-review/SKILL.md) · [评分协议](../skills/cp-editorial-review/references/scoring.md) · [返回目录](README.md)
