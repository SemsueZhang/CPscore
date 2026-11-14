# 题解审核

`cp-editorial-review` 只依据原稿检查算法、关键声明、证明、整个输入域、数值范围与复杂度，并检查读者能否沿原文理解解法。审核者不替作者补条件、补核心证明或另找算法后判原稿成立。

内容与格式分别审核、分别报告，再按同根因合并评分；全程由机器判断，不设人工审批或独立子 Agent。

## 材料与调用

提供完整题面、约束、题解及其中声明正确的实现。多种做法都交付时全部纳入审核；投稿来源资格须明确审核用途和适用规则。

```text
$cp-editorial-review 结合 statement.md 审核 editorial.md，给出评分、具体缺口与修改方向。
```

## 审核重点

- 逐项核对实质声明的前提、原文依据、正确性与用途，不用删除测试豁免错误声明，不强制为常规知识展开证明。
- 原稿须覆盖所有合法输入、边界、中间数值及总成本。关键论证缺失、擅自限制参数、漏处理溢出或讲述不清且无实现可对照时 Fatal，不能脑补后放行。完整清楚的纯文字题解仍可合规。
- 每篇检查人类思维：需重新发现非平凡联系、重组推导才能理解时 Fatal，给具体阅读阻塞；不把算法难度本身判成表达错误。
- 代码仅作一次静态对照，检查与正文及数值／边界的一致性。默认不编译、运行、造小数据或对拍；数学推算与文字样例逐步手算保留。代码验证仅在用户另行明确要求时执行。
- 逐项指出防御性表达、车轱辘话、叙事拖延、语义失联和题外表演；删除或合并没有信息收益的部分，有用的回顾、边界解释与失败路线保留。
- 多类显著机械化迹象贯穿原稿时，明确报告“本文大概率由 AI 生成”并给原文依据，注明属于文本迹象判断。概率倾向不额外扣分，也不冒充来源已证实。
- 成段题外煽动或表演、低俗配图、明确黄赌毒内容及与解题无关的现实政治宣传、动员、攻击和影射直接 Fatal；单句轻微求赞、求通过通常 Minor。题目背景与必要引用不按词命中。
- 保留声明及必查范围的状态。重审说明新增、撤销与改级理由；收尾核对覆盖和证据，不重复全文审判，不增加多轮投票。

具体分级、未确认范围与去重见[评分协议](../skills/cp-editorial-review/references/scoring.md)。同一数值缺口在正文和代码中出现只计一次，同根因的表达标签不叠加；不同根因分别判断。外部评分表单独映射，不将 AIGC 倾向、声明矛盾和实际来源事实自动互换。

报告给原文位置、短摘录、失效依据、影响及最小修改方向，不代写完整解法或证明。题外严重内容应明确批评稿件本身，不能用空泛标签或辱骂替代理由。

## 格式脚本

题解与题面使用同源的 Python 3.8+ 标准库脚本和[格式协议](../skills/cp-editorial-review/references/format.md)，独立安装即可使用：

```sh
python3 skills/cp-editorial-review/scripts/format_lint.py --check
python3 skills/cp-editorial-review/scripts/format_lint.py editorial.md
python3 skills/cp-editorial-review/scripts/format_lint.py --decisions /tmp/review.json editorial.md
```

格式脚本不受“默认不运行被审代码”的限制。LLM 核验候选、跳过范围和静态遗漏，允许新增及重新归类，经来源绑定接口提交脚本合并。单篇同类独立 Confirmed 为 1～2 处时 Major、至少 3 处 Fatal，同类只扣一次；Warning 不充当确定次数。

不安装环境，不修改原稿。脚本失败时 LLM 补查已有材料，剩余核验缺口如实报告；源码检查不代表目标页面已实渲染，静态代码对照不代表评测通过。

## 案例与验证边界

本地 `tests/editorial/` 中的教学对照及走查覆盖清晰、简洁、缺关键联系和机械表达等材料，格式漏检复盘保留十篇已见文章的历史开发记录。测试目录不随仓库提交，这些材料也不代表独立模型评测或专家 Gold。

[《货币系统》](../examples/editorial-review.md)和[长春 L《故事》](../examples/editorial-review-story.md)保留旧版 8/10 的评分、补证及有限核验，用于历史对照；没有按当前禁止代补关键论证的规则重评，也不代表当前会默认运行代码。

## 执行规则

[技能入口](../skills/cp-editorial-review/SKILL.md) · [数学与内容核验](../skills/cp-editorial-review/references/verification.md) · [教学与表达审核](../skills/cp-editorial-review/references/pedagogy.md) · [共用格式协议](../skills/cp-editorial-review/references/format.md) · [评分协议](../skills/cp-editorial-review/references/scoring.md)

[返回说明目录](README.md)
