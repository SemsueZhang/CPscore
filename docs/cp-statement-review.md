# 题面审核

提供完整题面、约束、样例及必要附件，注明目标读者、材料语言和发布规范。

```text
$cp-statement-review 审核 statement.md，结合附件核对样例，给出评分、依据和修改建议。
```

报告总评先给 AIGC 裁定，再给合规结论、10 分制评分及档次，随后列“内容问题”与“格式问题”。内容用紧凑覆盖表交代定义、任务与接受条件、输入输出、范围、操作边界、数学声明、样例及附件的依据，另查阅读理解、病句及投稿内容。确认一项错误后仍继续查其余维度；报告列全独立问题，去重计分保留具体证据。

只依原稿还原任务，不代补规则或关键论证，题面不承担公开解法的义务。完整审核执行两遍，每遍覆盖内容、文风和格式，逐步手算样例、静态核对附件代码。两遍发现取并集，按根因合并计分，保留证据与发现遍次，不自动编译运行。每项缺陷给位置、短摘录、影响和最小修改方向，未核验范围明确注明。只审核时不修改原稿，重审说明结论变化。

循环说明与信息倒置纳入文风分类。每次按[文风分类](../skills/cp-statement-review/references/ai-style-patterns.md)逐类裁定，确认任一类即在总评首句写 **“本文为 AIGC”**，无需另找生成记录；未确认时写“未检出明显 AIGC 文风”，未核验范围另注。具体文风问题列入内容，给类别、级别、位置、短摘录、影响范围、机制和最小修改方向；每类至少 Major，广泛影响阅读或阻断核心理解时 Fatal，标签本身不另扣分。标题、加粗、列表或数学错误本身不触发 AIGC。内容、文风与格式按[评分协议](../skills/cp-statement-review/references/scoring.md)去重。

格式脚本可在仓库中运行，安装后使用对应 Skill 内的路径：

```sh
python3 skills/cp-statement-review/scripts/format_lint.py statement.md
```

LLM 须逐项裁定候选，并按全部规范类别补查全文、记录覆盖状态；排除理由应说明上下文与允许依据，尤其核实列表正文归属及同组标题标点。按[格式协议](../skills/cp-statement-review/references/format.md)合并全部独立位置，同类 1～2 处 Major、至少 3 处 Fatal。没有 Python 时继续核验，不因工具故障扣稿件分；截图或 PDF 不能证明 Markdown 源码合规。

[技能入口](../skills/cp-statement-review/SKILL.md) · [文风分类](../skills/cp-statement-review/references/ai-style-patterns.md) · [返回目录](README.md)
