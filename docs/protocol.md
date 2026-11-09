# CPscore 审查协议 1.0

本协议适用于恰好三个审查对象：题面 `statement`、程序 `solution`、题解 `editorial`。三个 Agent Skills 分别审查一个对象，也可读取其他材料进行交叉核验。模型负责提出和核实问题，共享代码负责输入校验、去重、状态与算分。不得手工填写模型自评总分。

## 证据与审查范围

`scope` 是本轮需要交付的对象。`objects` 始终包含三个对象，各自记录 `review_status`、`artifact_version` 和 `findings`。没有实际审查的对象保持 `not_reviewed`，不包含 findings，其分数为 `null`。scope 外对象也必须如此。只有完成声明范围的审查才设为 `reviewed`。仅有片段材料或测试通过不能隐含完整审查。

每项发现都需要当前材料中的明确位置、观察与复现推导。数学论证和语义分析优先，有限测试可辅助核验具体断言，不能证明一般正确性。确认问题前，应检查反例合法性、预期答案和因果影响。未执行的测试必须写明未执行原因，不能生成通过记录。编译成功、程序运行、输出独立核验是不同证据。

问题的 `severity` 为 `fatal` 或 `minor`。`fatal` 表示使目标对象的核心正确性、答案确定性或合法可判定性失效的实质问题。`minor` 表示影响局部准确性或必要理解、但未使核心结论失效的问题。个人文风、命名、篇章偏好、主观难度、原创性或“应该使用另一种算法”都不在评分范围。

问题的 `status` 为 `confirmed`、`suspected` 或 `resolved`。确认必须有足以复核的推导、矛盾或合法反例。`suspected` 保留真实未决疑点，尤其疑似致命问题不得提升为确认或静默删去。`resolved` 表示已在当前材料版本重新核验修复，而非仅提出建议。JSON 校验能检查记录的完整性与一致性，不能替人验证数学证据是否为真。

## 唯一计分规则

每个已审查对象初始 10 分。已确认致命根因扣 10 分，已确认轻微根因扣 1 分，最低为 0 分。6 分及以上为通过。只有 `confirmed` 扣分，`suspected` 与 `resolved` 不扣分。

`root_cause_id` 是唯一去重键。只有机制相同且同一修复能消除各处问题时，才可共用 ID，并为每个受影响对象保留证据定位。文本相似或结果相同本身不构成同根因。同一根因在同一对象只扣一次，跨对象总评也只扣一次。不同证据或不同表述不产生额外扣分。相关但不同根因不能为减少扣分强行合并。同一根因的严重程度与状态必须一致，否则输入被拒绝。

总评对 scope 内已审查对象的全部已确认根因合并去重，从 10 分扣除，**不平均三个对象分数**。未审查对象的分数为 `null`。scope 内仍有对象未审查，总评完成状态为 `pending`。只有部分对象已审查时，可显示这些证据产生的暂定分数，但不能宣称整体审查完成。

存在未决 `suspected fatal` 或未审查的 scope 对象时，审核状态优先为 `pending`，即使已确认扣分使当前分数降到 5 分或 0 分也如此，`qualified` 为 `null`。只有这些阻碍均已排除，才按分数低于 6 判为 `fail`、至少 6 判为 `pass`。scope 内完全没有对象审查时，总分为 `null` 且为 `pending`。不在 scope 的对象为 `not_reviewed`。

## 输入与输出结构

源码中的 `cpscore/schemas/report.schema.json` 是输入的结构定义，`cpscore/schemas/scored-report.schema.json` 定义评分输出。项目安装后位于 `.cpscore/runtime/cpscore/schemas/`。不得增加未声明字段。初始化命令生成可直接填写的完整骨架：

```sh
python3 -m cpscore init-report --scope statement,solution,editorial --output review.json
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore score review.json --output review.md
```

安装后的技能将 `python3 -m cpscore` 替换为 `python3 <技能目录>/scripts/cpscore.py`，无需全局安装 CPscore。生成骨架后的对象状态仍是 `not_reviewed`，不能直接当作无错误审查结果。

顶层字段：`schema_version: "1.0"`、`review_id`、`snapshot`、`scope`、`objects`、`validations`。`snapshot` 包含 `id`、正整数 `revision`、`supersedes`。首轮 revision 为 1 且 supersedes 为 null。后续复审应递增 revision，使用新的 id，并以 supersedes 引用上轮 id。`artifact_version` 推荐使用对应文件的 SHA256。使用用户版本标签时，审查者负责保证该标签准确对应实际文件。

每个 finding 必填以下字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 全报告唯一的问题 ID |
| `root_cause_id` | 同根因去重 ID，跨对象可共用 |
| `severity` | `fatal` 或 `minor` |
| `status` | `confirmed`、`suspected` 或 `resolved` |
| `title`, `description` | 问题与影响 |
| `evidence` | 至少一条当前版本证据 |
| `reproduction` | `steps` 非空数组、`expected`、`actual`。可写数学复现，不强制执行程序 |
| `repair` | 修复建议与执行状态，不能省略 |

`evidence` 每条为 `{snapshot_id, artifact_version, location, observation}`。snapshot_id 必须等于当前 snapshot.id，artifact_version 必须等于所属对象当前版本。描述位置应足以让另一位审查者定位，例如文件行号、章节与原文引用。

`repair` 为 `{suggestion, auto_fixable, status, patch, verification}`。auto_fixable 为布尔值。status 可为 `not_attempted`、`proposed`、`applied`、`blocked`。patch 是补丁字符串或 null，verification 为核验步骤字符串数组。仅建议修复时用 proposed，不得假记 applied。applied 必须对应 resolved 且有非空 verification，并在当前版本 evidence 中说明修复核验。自动修复仍须遵守用户对修改材料的授权。

`validations` 每条为 `{id, name, object, status, command, outcome, reason, evidence}`。object 在 scope 内。已执行用 `status: "executed"`，outcome 为 passed、failed 或 inconclusive，reason 为 null，evidence 非空。未执行用 `status: "unexecuted"`，outcome 为 null，evidence 为空，reason 解释原因。command 可为 null，因为数学手算也能成为核验。

需要执行待审程序、外部参考程序或用户提供的生成器与验证器时，使用共享入口的 `check-candidate`、`bench` 与已准备的受限容器，不直接在宿主执行这些程序。先用命令的 `--help` 读取参数。不可用时保留 unexecuted 原因，不自动下载镜像、不退回宿主、不记为通过。`check-candidate` 的有限对拍和 `bench` 的环境计时只产生辅助证据，不自动确认 finding 或修改分数。源码中完整用法见 `docs/validation.md`。

输出包含原始 `review`、每对象 `objects` 结果与 `overall`。每项评分包含分数、判定、扣分根因、关联 finding 与证据引用，以及未决、疑似和已解决 ID。Markdown 报告保留问题、证据、复现、修复、已执行和未执行核验，不只输出一个数字。

## 修复与复审

保存旧轮报告，修改材料后产生新 snapshot 与对应 artifact_version。旧证据不能直接用于新版本确认、扣分或宣称修复。复核后可保留根因 ID 并更新状态，但所有保留的证据与核验记录都必须重新绑定并描述当前版本。工具会拒绝旧 snapshot 或旧 artifact_version，不能只改 ID 伪装重新核验。

本地校验只检查当前报告的结构与交叉字段约束，不持有历史数据库，无法自行证明 revision 真正递增、supersedes 存在或材料确实变更。审查者应保留文件版本与历史报告供复查。
