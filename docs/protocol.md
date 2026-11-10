# 打分规则与报告格式

题面 `statement`、程序 `solution`、题解 `editorial`、测试数据 `data` 使用统一的 10 分制。打分智能体填写核验记录，Python 工具校验、按根因去重、算分并生成报告。新颖度使用[独立评级](novelty.md)。

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

顶层字段为 `schema_version: "3.0"`、`review_id`、`snapshot`、`scope`、`objects`、`validations`。`scope` 选择本次打分对象，`objects` 始终保留原三个对象，选择data时另含data对象（旧三对象报告无需增加字段），每个包含 `artifact_version`、`coverage`、`findings`。范围外对象的覆盖状态保持 `unchecked`，findings 为空。

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
| data | `integrity`、`judging`、`mechanisms`、`execution`、`scoring` |

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

统一使用 Fatal（−10）、Major（−3）、Minor（−1）。No Issue（0）不写成缺陷。只有确认的真实缺陷扣分，疑点保留 suspected。Major 是有证据的重要质量缺陷，不能作为不确定时的默认等级。不得刻意凑扣分，材料优秀时允许自然获得 10 分。修复难易不决定严重程度。同一错误的多个后果不能重复计分。

| rule_id | severity | 适用情况 |
| --- | --- | --- |
| `incorrect_sample` | fatal | 正式样例输入、输出或解释有已确认的实质错误 |
| `wrong_answer` | fatal | 合法输入上的答案错误 |
| `invalid_algorithm` | fatal | 核心算法或结论错误，或无法满足约束 |
| `ambiguous_answer` | fatal | 合理解释导致不同答案，或无法确定合法性 |
| `invalid_proof` | major | 证明有实质漏洞，但算法与结论已由独立有效论证确认成立 |
| `incomplete_explanation` | major / minor | 缺失核心依据、非平凡观察为 Major，非关键必要说明的小缺漏为 Minor |
| `quality_defect` | major | 已确认的重要非致命实现、性能或交付质量缺陷 |
| `local_presentation` | minor | 确有理解/核验影响的局部误述 |
| `other` | fatal / major / minor | 其他真实缺陷，说明具体影响及分级依据 |

原三个 Skill 的对象标准如下。数据对象的错误机制、部分分、独立反例与实测门槛见[数据手册](data.md)，其 `data_*` 规则仅用于data，原正确性规则不用于data（`other`除外）。

| 对象 | Fatal | Major | Minor / No Issue |
| --- | --- | --- | --- |
| 题面 | 实质歧义改变答案、必要约束缺失、正式样例错误、定义重大矛盾、判定规则不明 | 核心语义唯一但重要特有规则严重缺漏，需非平凡推断或大幅整理 | 易由明确上下文/惯例补足的局部规则或符号缺漏为 Minor，故事、文风、篇幅和排版偏好不扣分 |
| 标程 | WA、可触发且导致失败的 UB/运行错误、算法不满足约束、有充分证据的资源/环境违例 | 算法正确但有客观证据的重要可靠性、性能余量或工程缺陷，显著影响稳定运行、核验或维护 | 局部错误注释或有实际影响的非关键冗余为 Minor，代码长度、无详细注释、数据结构和风格偏好不扣分 |
| 题解 | 核心算法被证伪、数学错误导致解法不成立、复杂度实质错误使算法无法满足要求 | 算法正确但缺核心依据/非平凡观察，证明存在可由其他有效论证修复的实质漏洞，关键转换或复杂度缺必要论证 | 非关键必要推导/公式/复杂度说明的局部问题为 Minor，标准算法/定理、常规推导、简洁完整证明和等价实现不扣分 |

证明不完整不等于算法错误。先判断算法及核心结论，再分级。不能仅凭“可补证”把核心证明缺失降为 Minor，也不能把所有证明问题判 Fatal。《货币系统》缺少每个不可约面额在任意等价系统中必选的最优性依据是 Major（7 分），算法用 gcd 替代整个系统且被 [2,3] 反驳才是 Fatal（0 分）。性能问题结合数据范围、目标环境和实际证据，超时猜测保持 suspected，不因有更快算法而扣分。

finding 必填 `id`（全报告唯一）、`root_cause_id`、`rule_id`、`severity`、`status`、`title`、`description`、非空 `evidence`、`reproduction`、`repair`。Major/Minor 还必须填写非空 `impact`，说明对实际理解、验证、维护或运行质量的具体影响及分级理由。不能仅重复“有缺陷”。

| status | 使用条件 |
| --- | --- |
| `confirmed` | 已独立核实的推导、矛盾或合法反例，明确说明因果影响 |
| `suspected` | 尚有证据缺口，必须用非空 `evidence_gap` 说明缺什么 |
| `resolved` | 已在当前材料版本复核修复，附当前版本证据 |

能手算、补证或用极小实例裁定的问题继续核验。反例需核实输入合法性、期望答案和实际结果。`reproduction` 为 `{steps, expected, actual}`，steps 是非空数组，可以用数学推导复现。

## 算分与判定

有核验活动的对象从 10 分开始，只对 confirmed 独立根因扣分：

```text
score = max(0, 10 - 10 * fatal_count - 3 * major_count - minor_count)
```

固定整数权重，无小数或自由调整。同根因不重复扣分，suspected/resolved 不扣分。1 Major + 1 Minor = 6，2 Major = 4，1 Major + 2 Minor = 5，Fatal 与任意其他缺陷合计最低 0。

`root_cause_id` 是唯一去重键。机制相同、同一修复能消除相关问题，且各对象均有自身证据时，才共用 ID。跨对象 severity 和 status 均可不同，同一对象同根因的 status 必须一致，避免互相矛盾的修复状态。相同对象的重复观察取最高严重程度。

对象按自身 confirmed 根因扣分，总评合并 scope 内根因，不取平均。聚合状态按 `confirmed > suspected > resolved`，严重程度只从该状态的记录中取最高级别。因此只要还有 confirmed，就按当前已确认且未修复对象的最高级别扣一次。全部修复时扣分归零，只剩疑点时不扣分。输出 `local_states` 保留各对象 severity、status、points 和证据引用。

例如同根因在题面 confirmed Minor、题解 confirmed Major 时，对象分别为 9、7 分，总评为 7 分。题解修复并复核后总评为 9 分，全部修复后 10 分。若题解仍有 suspected Fatal，即使题面同根因 confirmed Minor，也必须保留该未决 Fatal，不能让聚合状态掩盖它。

`completion` 独立由覆盖决定。判定顺序如下：

| 条件 | qualification | tier | recommendable |
| --- | --- | --- | --- |
| 已确认扣分使分数低于 6，无论覆盖和未决状态 | fail | unacceptable | false |
| 9～10 分、覆盖完成、无任何 suspected Fatal | pass | excellent | true |
| 6～8 分、覆盖完成、无任何 suspected Fatal | pass | acceptable | false |
| 其他情况，包括 score=null | undetermined | undetermined | null |

6 分是合格线，9 分是推荐线。6～8 分表示基本合格、值得打磨。9～10 分不要求完美，但不能有实质性质量缺陷。未完成的暂定 10 分不能称优秀。已确认缺陷累计使分数低于 6，即使审核未完成也可确认不合格。

输出包含原始 `review`、各对象结果、`overall`、`root_causes`。`confirmed_counts` 按实际扣分的去重根因分级统计，不按 finding 数量计数。`pending_finding_ids` 包含每一个 suspected Fatal，`suspected_finding_ids` 包含全部疑点，`resolved_finding_ids` 保留已解决记录。Markdown 首先展示总分、质量档次、合格/推荐判定、计数，然后展示根因、证据、影响、疑点及覆盖状态。

## 交付结果

交付填写后的 `review.json`、工具生成并校验的 `scored.json` 和 `review.md`。最终回复概述范围内各对象及总评的分数、`tier`、`qualification`、`recommendable`、`completion`，列出决定结果的主要问题或未决事项，并附报告链接。只有部分核验完成时如实说明，不能只报分数而省略未完成状态。

同时进行新颖度审查时，按[新颖度手册](novelty.md)逐题给出等级、题目分析与判据来源。C+/F由先例关系、合适度和质量共同决定，局部证明错误按修复与替代解法的核验结果评价。这些判断独立于本协议的confirmed证据要求、扣分规则与覆盖状态。

## 修复与运行记录

`repair` 为 `{suggestion, auto_fixable, status, patch, verification}`。status 支持 `not_attempted`、`proposed`、`applied`、`blocked`。patch 为补丁字符串或 null，verification 为核验步骤数组。建议修复填 proposed，实际修改须遵循用户授权。applied 必须对应 resolved，并有非空 verification 和当前版本证据。

`validations` 每条为 `{id, name, object, status, command, outcome, reason, evidence}`，object 必须在 scope 内：

- `executed`：outcome 为 passed、failed 或 inconclusive，reason 为 null，evidence 包含当前版本记录。
- `unexecuted`：outcome 为 null，evidence 为空数组，reason 说明未执行原因。

手算时 command 可为 null。执行候选程序、oracle、生成器或校验器时使用 `check-candidate` 或 `bench`，先读取对应的 `--help`。数据对象可用 `test-data` 在冻结原集上批量执行，见[数据手册](data.md)。隔离不可用时记 unexecuted。运行结果经核实后再填写 findings，不自动扣分。

## 旧报告迁移

```sh
python3 -m cpscore migrate old.json -o new.json
```

协议 3.0 显式取代 1.0/2.0，包版本为 0.3.1。`score`/`validate` 拒绝旧协议，不会静默重算。2.0 的 `invalid_proof=fatal` 和 `incomplete_explanation=minor` 不再能直接沿用，旧问题需按算法是否成立及缺漏重要性重新裁定。`schema --kind report-v2` 可查看冻结的旧结构。

迁移接受旧输入或带 `review` 的旧评分报告，只校验旧 review 的结构，不认证旧模型分数。迁移把旧源保存在 `new.json.legacy.json`，路径、SHA256 和版本写入 `new.json.migration.json`，拒绝覆盖已有目标。新报告使用新快照 ID 并链接旧快照，保留材料版本标签，范围内覆盖项为 blocked。读取旧证据作为线索，重新核验当前材料并填写覆盖与问题，旧分数、findings 和完成结论不自动继承。
