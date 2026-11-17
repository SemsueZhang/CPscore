---
name: cp-statement-review
description: 依据原稿审核算法竞赛题面的任务规格、约束、样例与阅读质量，分任务记录、补查遗漏并评分；用户明确要求时加审格式。
---

# 题面审核

读取完整题面、约束、样例和必要附件，固定目标读者、材料语言与发布规范。默认审核正确性、阅读与文风，用户明确要求格式审核（包括含格式评分项的外部评分表）时启用格式任务。只审核时不改原稿。

算法知识、洛谷标签和知识门槛统一查询 `CPSCORE_CATALOG`（仓库默认 `resources/algorithm-catalog/`）中的 `catalog.json`；可用 `catalog.py search/get/tag/levels`，无 Python 时读同一 JSON。按 `luogu_tags.relation` 区分同义、较宽与上下文。`knowledge_level` 是知识参考，`problem_difficulty` 是非代表性标签样本，均不直接决定整题难度或选手掌握度。目录缺失时保留文字名、报告依赖缺失，不编造 ID／难度，不复制目录数据。

## 审核流程

1. 按[覆盖协议](references/coverage.md)建立带原文位置的章节、规则、重要声明、约束、样例及附件对象，确定各对象的适用检查项。保留首尾、附注、引用、图片和代码块的审核范围。
2. 分别完成下列任务，各自产生对象级结果与依据。宿主支持时可按需委派专项，其余顺序执行；内容核验从定义还原任务，再从输出、样例及边界反查规则。按实际执行记录路线与委派范围。
   - **内容** 按[规格核验](references/specification.md)审核任务与接受条件、输入输出、范围、操作、数学声明、样例、附件及来源合规。静态核对附件代码，逐步手算样例。
   - **阅读** 按[阅读与表达](references/readability.md)和[文风问题](references/writing-issues.md)检查规则组织、信息主次及实际阅读负担，逐类记录依据。题面以明确任务、规则、约束和接受条件为目标。
   - **格式（启用时）** 按[格式协议](references/format.md)逐类检查全文；有 Python 时运行随包 Linter 并按[接口](references/format-tool.md)裁定每项候选、补充静态遗漏。
3. 执行[覆盖检查与补查](references/coverage.md#覆盖检查与补查)，补齐缺失任务、对象、检查项和未处理候选，核实依据不足的通过结论。已有拒绝理由仍完成其他适用项。
4. 合并所有候选并据原文核实，按[评分协议](references/scoring.md)去重计分。撤销或改级记录依据；重审说明结论变化。

## 报告

默认对话输出 Markdown，仅要求保存时写报告文件。以 `# CPScore · 题面审核` 开头，给合规结论、10 分制评分及档次，注明实际审核范围及格式是否启用。审核未完成时说明缺口，分数仅计已确认问题。

按“内容问题”“格式问题”列出已确认问题，文风归入内容；格式任务未启用或无问题时省略相应清单。每项写类别、级别／扣分、位置、短摘录、依据、影响及具体改法，同根因合并并保留各处证据。主线不突出时说明应表达的核心、遮蔽它的内容及调整顺序。样例有误时给实际手算。覆盖记录用于内部查漏。

评价文章质量。平台的 AI 辅助创作资格或披露义务仅凭直接证据核验。注明材料和规则版本，启用脚本时记录脚本版本，可取得时记录模型及推理设置；区分静态核验与实际通过。

## 随包工具

在 Skill 目录运行，Python 3.8+ 标准库。覆盖记录接口见[覆盖协议](references/coverage.md)，格式命令仅用于已启用的任务。

```sh
python3 scripts/check_coverage.py /tmp/review.json
python3 scripts/format_lint.py /path/to/statement.md
python3 scripts/format_lint.py --decisions /tmp/format-decisions.json /path/to/statement.md
```
