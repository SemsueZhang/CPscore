# CPscore 审查协议 2.0

本协议适用于题面 `statement`、程序 `solution`、题解 `editorial` 三个正确性对象。模型提出并核实问题，代码校验记录、去重、算分与生成报告。新颖度由[独立技能](novelty.md)处理，不增加正确性对象或换算扣分。分数必须由共享代码产生。

## 范围、版本与覆盖

顶层字段为 `schema_version: "2.0"`、`review_id`、`snapshot`、`scope`、`objects`、`validations`。`scope` 声明本轮交付对象，`objects` 始终包含三个对象，每个仅记录 `artifact_version`、`coverage` 和 `findings`，没有可手填的 `review_status`。scope 外对象所有覆盖项保持 `unchecked`，findings 为空。

`snapshot` 包含 `id`、正整数 `revision`、`supersedes`。首轮 revision 为 1、supersedes 为 null。复审递增 revision，换新 id，以 supersedes 引用上轮 id。对象 `artifact_version` 推荐用文件 SHA256，人工标签由审查者负责对应实际材料。所有覆盖、finding 和已执行核验证据使用同一格式：

```json
{"snapshot_id": "本轮ID", "artifact_version": "所属材料版本", "location": "文件行号、章节或原文引用", "observation": "实际核验与观察"}
```

snapshot_id 必须等于当前 snapshot.id，artifact_version 必须等于所属对象当前版本。换版本后须重新核验，不能仅替换 ID 沿用旧证据。本地校验不持有历史数据库，不能证明材料确实变更、supersedes 存在或自然语言证据为真。

coverage 是固定键的 map，不是自由文本清单：

| 对象 | 必须逐项保留的覆盖键 |
| --- | --- |
| statement | `definition`、`io`、`constraints`、`boundaries`、`samples` |
| solution | `algorithm`、`correctness`、`complexity`、`implementation` |
| editorial | `claims`、`reasoning`、`proof`、`complexity` |

每项为 `{status, evidence, reason}`，evidence 为上述证据数组，reason 为 null 或非空字符串：

| status | 要求与含义 |
| --- | --- |
| `unchecked` | 尚未核验，evidence 必须为空数组、reason 为 null，不代表无错误 |
| `checked` | 必须有当前版本证据，说明该项实际核验了什么，可同时有 findings |
| `blocked` | 必须有 reason，说明缺少材料或无法继续的具体原因 |
| `not_applicable` | 必须同时有 reason 和当前版本证据，说明为何本对象无需此项 |

所有项均为 checked 或 not_applicable 时，该对象 `completion: complete`，否则为 `incomplete`。完成表示声明范围经过核验，并不表示对象正确。仅有部分材料、样例通过或填写“已看过”不能替代相应覆盖证据。没有 checked/not_applicable 覆盖项且没有 finding 时，分数为 null，blocked/unchecked 或单独的 validation 不会产生默认 10 分。

## 分级与确认门槛

按可以正式交给选手使用的要求主动核验。官方来源、已有 AC、作者意图可猜、审查者能替作者补全或修复容易，都不能抵消已经确认的缺陷。不设找错数量或目标分数。公认定义、标准结论与面向目标读者的常规推导可直接引用，不要求重新证明。文风、变量命名、篇章偏好、主观难度、原创性及个人算法偏好不扣分。

每项 finding 使用 `rule_id`，以下规则固定 severity，不能按修复成本改级：

| rule_id | severity | 适用情况 |
| --- | --- | --- |
| `incorrect_sample` | fatal | 正式样例输入、输出或解释与题意矛盾，形成错误答案或非法样例 |
| `wrong_answer` | fatal | 合法输入上程序或公开声称的答案错误 |
| `invalid_algorithm` | fatal | 算法规则不能覆盖声明的合法输入或不能保证所声称结论 |
| `invalid_proof` | fatal | 关键证明含无效推理或被证伪的断言，不能建立所声称结论 |
| `ambiguous_answer` | fatal | 合理解释导致不同合法答案，或合法性无法确定 |
| `incomplete_explanation` | minor | 可核验补足但确实影响理解、复现或验证的必要解释缺漏 |
| `local_presentation` | minor | 有具体影响的局部误述，核心答案与论证仍确定成立 |
| `other` | 显式填 fatal 或 minor | 其他实质问题，必须说明其影响及分级理由 |

正反例：正式样例要求求和却把 `1 + 2` 的输出写成 `4`，应按 incorrect_sample 判 Fatal，即使只是笔误且一字可修。强领域惯例和上下文已唯一确定双向通行，但遗漏必要明示，可按 incomplete_explanation 判 Minor。仅仅偏好另一种措辞不扣分，牵强的替代读法不构成 ambiguous_answer。可补足的必要论证缺漏是 Minor，被证伪的关键引理或无效的核心证明是 Fatal，标准结论与常规推导省略不扣分。三个正确性技能使用同一口径。

`status` 为 confirmed、suspected 或 resolved。confirmed 必须有可复核推导、矛盾或合法反例，先独立核验反例输入、期望答案与因果影响。suspected 保留真实未决疑点，必须填写非空 `evidence_gap`，说明尚缺什么证据，不能冒充确认或静默丢弃。其他状态的 evidence_gap 可省略、为 null 或作说明。能够手算、补证或用极小实例裁定时继续核验，不把已确认缺漏搁置为待定。resolved 必须已在当前版本复核修复，修复建议本身不改变状态。

数学推导和语义分析优先，有限测试只能核验具体断言，未找到反例、随机对拍一致或已有 AC 不构成一般证明。编译成功、程序实际运行、输出已独立核实应分别记录。

## 算分与独立判定

有审查活动的对象从 10 分开始，每个 confirmed fatal 根因扣 10 分，confirmed minor 扣 1 分，最低 0 分。suspected 与 resolved 不扣分。10 分只表示本次已核验范围内没有确认应扣分的问题。

`root_cause_id` 是唯一去重键。只有机制相同、同一修复能够消除相关问题，且每个对象均有自身证据，才能共用 ID。相似文本、相同错误结果或因果相关不足以合并根因。同一根因在对象内与总评分别只扣一次。同根因 severity 必须一致，跨对象 status 可以不同：题面已修复不能替程序中的未解决错误免扣分。

总评对 scope 内全部 confirmed 根因合并去重，从 10 分扣除，**不平均对象分数**。只要同根因仍在任何 scope 内对象 confirmed，总评就扣一次。该根因的聚合状态优先级为 confirmed > suspected > resolved，并保留各对象的 `local_states`。对象仅按自己的 confirmed 状态扣分。

每对象及总评分别输出两个独立字段：

- `completion`：complete 或 incomplete，只由覆盖项决定。总评要求 scope 内所有对象覆盖完成。
- `qualification`：pass、fail 或 undetermined，按以下顺序计算。

| 条件 | qualification |
| --- | --- |
| 已确认扣分使分数低于 6 | `fail`，无论是否未完成或仍有 suspected fatal |
| 分数至少 6、覆盖完成、没有未决 suspected fatal | `pass` |
| 其余，包括没有审查活动而 score 为 null | `undetermined` |

例如只确认一个 Fatal、其余覆盖尚未完成时，结果为 score 0、qualification fail、completion incomplete。覆盖已完成但留有 suspected fatal，且没有确认扣分时为 score 10、qualification undetermined、completion complete。疑点不会扣分，也不能用完成标记将它消除。

## 记录与代码入口

输入结构以 `cpscore/schemas/report.schema.json` 为准，评分输出以 `scored-report.schema.json` 为准，安装后位于 `.cpscore/runtime/cpscore/schemas/`。不得增加未声明字段。

```sh
python3 -m cpscore init-report --scope statement,solution,editorial --output review.json
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore score review.json --output review.md
```

安装后将 `python3 -m cpscore` 换成 `python3 <实际技能目录>/scripts/cpscore.py`。先解析实际路径并正确引用空格，不依赖当前工作目录。新骨架所有 coverage 项均为 unchecked，不能作为无错误结论。已有报告须先读，保留用户 scope 与其他对象，只更新本技能负责的对象。交叉核验发现其他对象自身问题时说明归属和复核建议，不冒充完成其审查。

finding 必填 `id`（全报告唯一）、`root_cause_id`、`rule_id`、`severity`、`status`、`title`、`description`、非空 `evidence`、`reproduction` 和 `repair`。reproduction 为 `{steps, expected, actual}`，steps 为非空数组，可用数学推导复现，不强制运行程序。

repair 为 `{suggestion, auto_fixable, status, patch, verification}`。status 是 not_attempted、proposed、applied 或 blocked，patch 为补丁字符串或 null，verification 为核验步骤数组。applied 必须对应 resolved，并有非空 verification 和当前版本证据。仅建议修复应为 proposed，修改材料仍遵循用户授权。

validations 每条为 `{id, name, object, status, command, outcome, reason, evidence}`，object 在 scope 内。executed 记录 passed/failed/inconclusive、reason null、非空当前版本证据。unexecuted 记录 outcome null、evidence 空数组、reason 说明未执行原因。command 可为 null，因为手算也能成为核验。未执行不能记录为通过。

执行待审程序、外部 oracle、生成器或验证器时，使用 `check-candidate` 或 `bench` 的受限容器，先读 `--help`。隔离不可用时记 unexecuted，不下载镜像、不在宿主裸跑。具体参数和证据解释集中于[隔离验证手册](validation.md)。这些工具不自动确认 finding 或扣分，性能计时不能直接证明目标机超时。

输出保留原始 review、各对象结果、overall 与 root_causes。结果包含分数、qualification、completion、扣分及证据引用、未决与已解决 finding。overall 用 completed_objects/incomplete_objects 列出 scope 覆盖完成度，aggregation 为 `unique_root_causes_across_in_scope_objects`。根因与扣分记录保留 local_states 的 `{object, status, points, finding_ids, evidence_refs}`，以说明跨对象修复差异。Markdown 报告同时交付覆盖、问题、证据、复现、修复与实际核验范围。

结构校验与派生分数重算能发现记录不一致，不能保证自然语言证明真实、覆盖证据充分或审查找全错误。

## 迁移与复审

v1 报告不能直接按 v2 评分。迁移使用独立输出路径：

```sh
python3 -m cpscore migrate old.json -o new.json
```

迁移将旧源逐字节保存在 `new.json.legacy.json`，将路径、SHA256 与版本写入 `new.json.migration.json`，拒绝覆盖任意已有目标文件。历史 schema 校验仅检查旧记录结构，不认证旧派生分数。

新报告中 scope 内所有覆盖项为 blocked，明确要求重新审查，不自动继承 findings、旧分数或完成结论。先读取保留的旧证据作为线索，再核验当前材料，按 v2 重新填写覆盖与问题。新旧报告分别保存。后续材料修复仍须新 snapshot、新 artifact_version 和本轮证据，不能只改标签或自动沿用旧结论。
