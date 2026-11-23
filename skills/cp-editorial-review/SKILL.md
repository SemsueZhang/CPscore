---
name: cp-editorial-review
description: 依据原稿审核算法竞赛题解的数学、算法、论证和样例，分任务记录、补查遗漏并评分。文风、格式与代码按需审核。
---

# 题解审核

## 审核标准与范围

CPScore 的审核结论和评分只依据本技能所列规则。发布平台、原文链接、稿件栏目或作者声明均不触发外部规范核验。用户明确要求核验平台规范或按外部评分表评分时，另行报告结果。

取得题面、全部约束和完整题解，确定目标读者。默认审核内容，合并询问尚未明确的文风与格式选项，可先核验内容。代码仅在用户明确要求时核验。只审核时保留原稿。

## 审核流程

1. 固定原文版本，按下述协议建立对象及适用检查项。
2. 分任务核验并记录路线、执行者、范围及对象级结果。有条件时可委派专项。正向推导结论，逆向反查前提、边界与反例。
   - **内容** 每次读取[内容核验](references/content.md)。检查全部方案的数学、论证、输入覆盖、复杂度、数值、样例和来源，逐步手算正文演示。启用代码时按其中的静态对照核验每份实现。
   - **文风** 启用时读取[文风](references/writing.md)及[阅读路径](references/content.md#教学与阅读路径)。提取各段核心与新增信息，对可删并、重组处实际比较改前改后。
   - **格式** 启用时按[格式协议](references/format.md)逐类核查全文，运行 Linter、裁定候选并补静态遗漏。工具不可用时按同一协议核查。
3. 按覆盖检查补齐遗漏及证据不足项。已有拒绝理由仍查完其他适用项。
4. 按[量规](references/rubric.md)核实、去重、评分并报告。重审说明新增、撤销与改级及原文依据。独立评测隔离历史结论。

## 审核对象与记录

按章节或主要段落建立带稳定 ID 和原文位置的对象，覆盖首尾、附注、引用、图片与代码块。另列重要声明、关键推导、各方案、样例及必要附件。仅在启用代码核验时获取专用附件并为每份实现单列 `content.code`。委派时沿用同一对象和检查项。

每条结果给具体依据。核验通过时写明所查关系或边界。候选保留位置、核实结论与证据，按根因合并时保留涉及的各处位置及影响。

## 覆盖检查与补查

对照全文和各 Reference 检查对象、适用维度、对象级结果及候选裁定，含启用时的格式结果。有 Python 时运行 `scripts/check_coverage.py`，否则按同一字段人工核对。工具检查记录和来源绑定，主审核实对象是否齐全、依据是否成立。定向补查遗漏、未确定和依据不足项，撤销或改级保留原文证据。剩余缺口按量规报审核未完成。

## 记录接口

覆盖记录可暂存 `/tmp/review.json`，与格式裁定文件各自独立。

```json
{
  "version": 2,
  "reading_requested": false,
  "format_requested": false,
  "sources": [{"id": "s1", "path": "/tmp/original.md", "sha256": "原文件字节的SHA256"}],
  "objects": [{
    "id": "p1", "source": "s1", "start": 0, "end": 23,
    "excerpt": "该对象起始处的原文短摘录",
    "checks": ["content.rules"]
  }],
  "results": [
    {"object": "p1", "check": "content.rules", "status": "issue", "basis": "原文未规定空区间是否参与计数", "findings": ["f1"]}
  ],
  "findings": [{"id": "f1", "objects": ["p1"], "status": "confirmed", "basis": "指出缺少定义的原句及其对计数的影响"}]
}
```

- `reading_requested`、`format_requested` 按已确定的任务范围显式填写布尔值。旧版记录（`version: 1`）沿用文风必查的覆盖规则。
- `sources` 登记原稿与范围内附件，参考题面可作外部依据。相对路径以记录文件所在目录为准。保留原始换行，以 UTF-8 解码后的字符计算零起点左闭右开 `start/end`。`excerpt` 为范围起始的非空精确摘录。图示通过文字锚点记录核验结果及未取得范围。
- `checks` 在判断前确定，采用 `content.`、`reading.` 或 `format.` 前缀，后缀为具体维度。每个启用任务须覆盖登记来源的所有非空白内容。章节对象可与重要声明对象重叠，漏列的声明先补对象再入账。
- `results` 按对象与检查项一一对应，`status` 取 `checked/issue/uncertain/not_applicable`，`basis` 非空。不适用须给适用性理由。`issue` 关联已确认发现，`findings` 是候选问题 ID 列表。
- 顶层 `findings` 的 `status` 取 `confirmed/rejected/uncertain`，每项须有原文对象、核实依据且被相应结果引用。确认后的级别、类别、影响和修改建议按报告及评价量规给出。

工具输出 `records_complete/incomplete/invalid`，分别退出 0/1/2。

## 报告

默认在对话给 Markdown，要求保存时写报告文件。以 `# CPScore · 题解审核` 开头，给合规和完成状态、10 分制评分及档次、文风／格式／代码启用情况及未核验缺口。列材料与规则版本、使用的脚本版本及可取得的模型和推理设置。

按“内容问题”“格式问题”列确认缺陷，文风归入内容，省略空的格式清单。各项给类别、级别／扣分、位置、短摘录、依据、影响和改法。主线问题写明应保留的核心、遮蔽信息和调整顺序，样例有误给手算。覆盖记录供内部查漏。静态核验与实际通过分别说明。

## 随包工具

在 Skill 目录运行，Python 3.8+ 标准库。覆盖工具读取上述记录，格式命令用于已启用的任务，接口见[格式审核](references/format.md#来源绑定与合并)。

```sh
python3 scripts/check_coverage.py /tmp/review.json
python3 scripts/check_coverage.py /tmp/review.json --format-scan /tmp/format-scan.json
python3 scripts/format_lint.py /path/to/editorial.md
python3 scripts/format_lint.py --decisions /tmp/format-decisions.json /path/to/editorial.md
```
