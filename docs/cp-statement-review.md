# 题面审核

检查题面能否明确规定合法输入、操作和接受条件，以及样例、阅读体验与格式是否合规。提供完整题面、约束、样例及必要附件，注明目标读者和发布平台。

```text
$cp-statement-review 审核 statement.md，结合附件核对样例，给出评分、依据和修改建议。
```

报告先给 10 分制评分、档次和完成状态，再分别说明内容与格式问题、证据、影响和最小修改方向。可选建议和未决问题单列；只审核时不修改原题面。

只依据原稿还原任务，不替作者补条件或关键论证。样例逐步手算；附代码默认仅作一次静态对照，不自动编译运行。全文检查包括人类思维、表达和题外内容；AIGC 判定须给文本依据，内部材料分按具体缺陷去重，外部表按评分协议映射。

格式辅助可在仓库内运行；安装后使用对应 Skill 内的脚本路径：

```sh
python3 skills/cp-statement-review/scripts/format_lint.py --check
python3 skills/cp-statement-review/scripts/format_lint.py statement.md
```

格式复核与计数见[格式协议](../skills/cp-statement-review/references/format.md)。脚本不代替内容审核；没有 Python 时由宿主 LLM 继续核验并记录剩余缺口。只有截图或 PDF 不能证明 Markdown 源码合规。

[技能入口](../skills/cp-statement-review/SKILL.md) · [评分协议](../skills/cp-statement-review/references/scoring.md) · [语义判断示例](../examples/statement-review-cases/README.md) · [返回目录](README.md)
