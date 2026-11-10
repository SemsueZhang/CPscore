# 打分规则与报告格式

题面 `statement`、程序 `solution`、题解 `editorial` 使用统一的 10 分制。打分智能体填写核验记录，Python 工具校验、按根因去重、算分并生成报告。新颖度使用[独立评级](novelty.md)。

## 创建与生成报告

```sh
python3 -m cpscore init-report --scope statement,solution,editorial --output review.json
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore score review.json --output review.md
```

创建骨架后先填写记录，再运行校验和算分。安装后将 `python3 -m cpscore` 替换为 `python3 <实际技能目录>/scripts/cpscore.py`。

输入格式以 `cpscore/schemas/report.schema.json` 为准，输出格式以 `scored-report.schema.json` 为准。安装后均在 `.cpscore/runtime/cpscore/schemas/`。已有报告先读取，只更新本技能负责的对象，保留用户的 `scope` 和其他对象记录。

## 范围、版本与核验项

顶层字段为 `schema_version: "2.0"`、`review_id`、`snapshot`、`scope`、`objects`、`validations`。`scope` 选择本次打分对象，`objects` 始终保留三个对象，每个包含 `artifact_version`、`coverage`、`findings`。范围外对象的覆盖状态保持 `unchecked`，findings 为空。

`snapshot` 包含 `id`、正整数 `revision`、`supersedes`。首轮 revision 为 1，supersedes 为 null。材料更新后换新 id、递增 revision，以 supersedes 引用上轮 id，并重新核验当前材料。`artifact_version` 推荐填写文件 SHA256，也可使用对应材料的版本标签。

覆盖项、问题及已执行核验统一使用以下证据格式，两个版本字段必须与所属对象当前版本一致：

```json
{"snapshot_id": "本轮ID", "artifact_version": "材料版本", "location": "文件行号、章节或原文引用", "observation": "实际核验与观察"}
```

`coverage` 必须保留各对象的全部固定键：

| 对象 | 覆盖键 |
| --- | --- |
| statement | `definition`、`io`、`constraints`、`boundaries`、`samples` |
| solution | `algorithm`、`correctness`、`complexity`、`implementation` |
| editorial | `claims`、`reasoning`、`proof`、`complexity` |

每项为 `{status, evidence, reason}`，按实际核验情况填写：

| status | 填写要求 |
| --- | --- |
| `unchecked` | evidence 为空数组，reason 为 null |
| `checked` | evidence 包含当前版本的具体核验记录，reason 可为 null |
| `blocked` | reason 说明缺少材料或无法继续的原因 |
| `not_applicable` | reason 和当前版本 evidence 同时说明无需此项的原因 |

所有项均为 `checked` 或 `not_applicable` 时，该对象的 `completion` 为 `complete`，否则为 `incomplete`。总评要求 scope 内所有对象完成覆盖。没有已核验覆盖项且没有 finding 时分数为 `null`，单独填写 validation 不产生分数。

## 问题分级与证据

以可正式交付选手使用的材料为标准核验。数学推导和语义分析优先，有限测试用于核验具体输入。文风、命名、主观难度、原创性和个人算法偏好不扣分。官方来源、已有 AC 或修复容易不改变已确认问题的分级。

| rule_id | severity | 适用情况 |
| --- | --- | --- |
| `incorrect_sample` | fatal | 正式样例输入、输出或解释与题意矛盾，导致错误答案或非法样例 |
| `wrong_answer` | fatal | 合法输入上的答案错误 |
| `invalid_algorithm` | fatal | 算法不能覆盖声明的合法输入或保证所声称结论 |
| `invalid_proof` | fatal | 关键证明存在无效推理或被证伪断言 |
| `ambiguous_answer` | fatal | 合理解释导致不同合法答案，或无法确定合法性 |
| `incomplete_explanation` | minor | 可以补足但影响理解、复现或验证的必要解释缺漏 |
| `local_presentation` | minor | 有具体影响的局部误述，核心答案与论证仍成立 |
| `other` | 显式填写 fatal 或 minor | 说明实质影响及分级理由 |

例如，求和题正式样例把 `1 + 2` 写成 `4`，按 Fatal 处理。上下文已唯一确定含义但缺少必要明示，按 Minor 处理。标准结论和面向目标读者的常规推导可以省略，必要论证缺漏与无效核心证明分别按 Minor、Fatal 处理。

finding 必填 `id`（全报告唯一）、`root_cause_id`、`rule_id`、`severity`、`status`、`title`、`description`、非空 `evidence`、`reproduction`、`repair`。

| status | 使用条件 |
| --- | --- |
| `confirmed` | 已独立核实的推导、矛盾或合法反例，明确说明因果影响 |
| `suspected` | 尚有证据缺口，必须用非空 `evidence_gap` 说明缺什么 |
| `resolved` | 已在当前材料版本复核修复，附当前版本证据 |

能手算、补证或用极小实例裁定的问题继续核验。反例需核实输入合法性、期望答案和实际结果。`reproduction` 为 `{steps, expected, actual}`，steps 是非空数组，可以用数学推导复现。

## 算分与判定

有核验活动的对象从 10 分开始，每个 confirmed fatal 根因扣 10 分，confirmed minor 扣 1 分，最低 0 分。suspected 和 resolved 不扣分。

`root_cause_id` 是去重键。机制相同、同一修复能消除相关问题，且各对象均有自身证据时，才共用 ID。同根因 severity 必须一致，跨对象 status 可不同。对象按自身 confirmed 根因扣分，总评合并 scope 内的 confirmed 根因，每个只扣一次，不取平均。

根因聚合状态按 `confirmed > suspected > resolved` 计算，同时保留各对象的 `local_states`。任一范围内对象仍为 confirmed，总评就保留该根因扣分。

`completion` 由覆盖决定，`qualification` 按以下顺序计算：

| 条件 | qualification |
| --- | --- |
| 已确认扣分使分数低于 6 | `fail` |
| 分数至少 6、覆盖完成、没有 suspected fatal | `pass` |
| 其余情况，包括分数为 null | `undetermined` |

因此只确认一个 Fatal、其余尚未核验时，结果为 `0 / fail / incomplete`。覆盖完成但仍有 suspected fatal、尚无确认扣分时，结果为 `10 / undetermined / complete`。

输出包含原始 `review`、各对象结果、`overall`、`root_causes`，保留扣分、证据引用、未决和已解决问题。Markdown 报告展示覆盖、问题、复现、修复与核验记录。

## 交付结果

交付填写后的 `review.json`、工具生成并校验的 `scored.json` 和 `review.md`。最终回复概述范围内各对象及总评的分数、`qualification`、`completion`，列出决定结果的主要问题或未决事项，并附报告链接。只有部分核验完成时如实说明，不能只报分数而省略未完成状态。

同时进行新颖度审查时，按[新颖度手册](novelty.md)逐题给出等级、题目分析与判据来源。C+/F由先例关系、合适度和质量共同决定，局部证明错误按修复与替代解法的核验结果评价。这些判断独立于本协议的confirmed证据要求、扣分规则与覆盖状态。

## 修复与运行记录

`repair` 为 `{suggestion, auto_fixable, status, patch, verification}`。status 支持 `not_attempted`、`proposed`、`applied`、`blocked`。patch 为补丁字符串或 null，verification 为核验步骤数组。建议修复填 proposed，实际修改须遵循用户授权。applied 必须对应 resolved，并有非空 verification 和当前版本证据。

`validations` 每条为 `{id, name, object, status, command, outcome, reason, evidence}`，object 必须在 scope 内：

- `executed`：outcome 为 passed、failed 或 inconclusive，reason 为 null，evidence 包含当前版本记录。
- `unexecuted`：outcome 为 null，evidence 为空数组，reason 说明未执行原因。

手算时 command 可为 null。执行候选程序、oracle、生成器或校验器时使用 `check-candidate` 或 `bench`，先读取对应的 `--help`。隔离不可用时记 unexecuted。运行结果经核实后再填写 findings，不自动扣分。

## 旧报告迁移

```sh
python3 -m cpscore migrate old.json -o new.json
```

迁移把旧源保存在 `new.json.legacy.json`，路径、SHA256 和版本写入 `new.json.migration.json`，拒绝覆盖已有目标。新报告的范围内覆盖项为 blocked。读取旧证据作为线索，重新核验当前材料并填写覆盖与问题，旧分数、findings 和完成结论不自动继承。
