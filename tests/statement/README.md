# CPScore 1.0 题面审核能力评测

本目录评测 `cp-statement-review`，不改变 Skill 或评分协议，不依赖其他七个 Skills。Python 3.9+ 标准库即可运行确定性检查，真实审核单独调用宿主或导入原始输出。普通 CI 不调用模型。

两个问题分别保存：`results/final/` 是旧版与改进版 Skill 的对照；**它没有无 CPScore 基线**。用户澄清的“CPScore harness 对比直接审题”见 [harness-vs-direct/](results/harness-vs-direct/README.md)，新增 `--direct` 条件复用相同题面和模型，单独记录收益与开销。

## 数据与 Gold

[manifest.json](manifest.json) 固定 40 个家族、56 个正式版本：24 个正确原始题面、16 个缺陷原始题面，以及正确家族派生的 16 个缺陷变体。另有 4 个只增加空行的等价版本，仅用于稳定性诊断，不计入 56 个正式版本。题面、约束、样例均为本轮自主构造，不是从互联网采集的官方题。

- `cases/` 仅存题面，不含标签、预期分数或修复答案。
- `gold/` 每个版本一份 JSON，记录家族、切分、输入域、接受关系、独立根因、原句、等级、证据、反例和条件性修订。`statement_sha256` 绑定题面，`expected_score` 由现有协议计算。
- `scripts/oracles.py` 用独立小模型、精确有理数、枚举及信息下界核验样例或证据。它不判断任意自然语言，也不证明大规模算法正确。
- `scripts/evaluate.py` 管理冻结计划、隔离调用、导入、根因裁定、四项指标和报告。
- `scripts/test_evaluation.py` 是离线单元测试。里面明确标记的合成解析/统计数据不是模型回答，不写入实际评测结果。
- `scripts/audit_archive.py` 离线审计本轮完整 Codex 存档的冻结数据、原始回答、256 个会话、精确中性载荷及 40 份修订核验程序，不调用模型。
- `scripts/compare_harness.py` 比较 CPScore 与直接组；`--audit` 离线核对复用及新增的 255 个不同会话、直接组载荷与 19 份实际修订核验程序，不调用模型。
- `results/` 保存冻结计划、执行状态、原始报告、提取结果、裁定和报告；失败调用也保留。

五种特殊类型直接复用正式 Benchmark，不另建题库：交互、通信、构造及多阶段模拟各有 4 道基础题，浮点另含一个零总量边界原始题，共 5 道，均含正确与缺陷题。另有普通序列、图、树、字符串、动态维护、最短路等题，包含明显错误和需要具体解释或反例才能裁定的问题。

Gold 由本轮宿主模型构造，并经书面论证和独立程序检查，**未经人类专家确认**。正确题的 `completeness_review` 主动记录边界与判定核验，不以“未植入错误”作为正确证据。`st-030-base` 的多级编号组织与 `st-039-base` 的背景映射有具体阅读负担，但 Major 的显著程度仍待独立读者确认，标为 `needs_review`，不计入已确认缺陷指标。

输入域同时保存输入契约与完整范围原文；变体的实际关系与正确基础版的 `reference_relation` 分开。`check_defect_witness` 逐项核验能程序化的反例，并区分数学证据、规范适用及文字核对。对交互边数题，正确反驳是“存在未询问边”，不能用图的数量大于回复叶子数代替，因为题目只要求总边数。

生成者已经见到全部题目与 Gold。开发/留出切分只用于防止后续调参泄漏，不能让当前构造者成为认知盲评者。被测模型固定为计划中的模型；它与生成者未建立独立性，可能相同，应视为模型自建数据评测，不能当作独立专家验证。

## 先运行离线检查

在仓库根目录执行：

```sh
python3 tests/statement/scripts/evaluate.py validate --smoke
python3 tests/statement/scripts/evaluate.py validate
python3 tests/statement/scripts/test_evaluation.py
```

检查包括数量、家族隔离、Gold 字段及原句、题面哈希、根因唯一、预期计分、正确原始题的正式样例解析、有限证据模型、等价文本和五类覆盖。它们不是 Skill 效果验证。现有 CI 运行第三条及本轮存档审计，均不调用模型。

可给 `validate` 增加 `--output tests/statement/results/deterministic-checks.json` 保存逐版本检查及验证范围。

## 冻结版本与运行条件

旧版为 `db9e9f6fba2370ce04a6b4c0f60b1608f48ae2d8`，改进版为 `5af3cda53b95ef963c81ff0cd6abd3658836d072`。两者评分协议相同，差异是核验方法与 Reference 组织。计划从 Git 读取完整包并固定提交及包哈希，不把当前未提交文件当作已测试版本。浅克隆缺少历史时，先按仓库策略取回这两个公开提交，不能用当前 Skill 冒充旧版。

默认固定 `gpt-6.1-sol`、`xhigh`，可在创建计划时显式更换；同一对照不能混用模型、effort、提示或工具权限。记录的是 CLI 请求的模型标识，不保证供应商别名永不变化。保存宿主版本、全部命令、UTC 日期、题面哈希、Skill 提交、状态及原始输出。宿主配置为只读沙箱、无审批交互、独立临时会话，不启用网页搜索；不加载用户配置，认证仍使用已有登录。不安装框架、不配置 API key、不把用户目录当作试验工作区。

每次被测工作目录仅包含 `material.md`、`request.txt` 及 `.agents/skills/cp-statement-review/`。Gold、manifest、结果、预期和其他 Skills 都留在目录外。目录隔离及提示不等同于操作系统禁止读取一切外部文件，实际宿主权限和全局上下文仍是验证限制；可检查每次 `payload` 清单及事件日志。

### Smoke Test 与正式评测

```sh
python3 tests/statement/scripts/evaluate.py plan --suite smoke --split development --output tests/statement/results/smoke-plan.json
python3 tests/statement/scripts/evaluate.py run --plan tests/statement/results/smoke-plan.json --output tests/statement/results/smoke --workers 4
```

`run` 是唯一调用模型的命令，默认串行，`--workers` 最多为 4，均为独立评测会话。它使用本机可用且已检查帮助的 Codex CLI，不声称适用于所有宿主。首次环境失败后停止后续批次，不把失败当作零缺陷或已完成审核。失败记录不覆盖；重试使用新的结果目录。命令不代替运行环境的审批或额度授权。

正式套件可分开计划：

```sh
python3 tests/statement/scripts/evaluate.py plan --suite a --split all --output tests/statement/results/a-plan.json
python3 tests/statement/scripts/evaluate.py plan --suite b --split all --output tests/statement/results/b-plan.json
python3 tests/statement/scripts/evaluate.py plan --suite c --split all --output tests/statement/results/c-plan.json
python3 tests/statement/scripts/evaluate.py plan --suite equivalence --split all --output tests/statement/results/equivalence-plan.json
```

A 为 56 版本 × 2 个 Skill，即 112 次。B 为 12 版本 × 5 次 × 2 个 Skill，即 120 次。C 对同样 20 个已确认根因配对比较两个 Skill，原始审核复用 A 的对应真实记录，40 份候选修订分别新开会话复审。D 按五类切片 A，不重复调用。等价版本复用同一条件下的基础版审核。

实际执行推荐先 `--split development`，调试完成后冻结脚本、提示和数据，再一次性运行 `--split holdout`。`--suite campaign` 合并 A、B 的重复第一轮与等价版本，全部为 216 次独立调用，不把同一真实调用计成五次。不要用留出结果反复修改 Skill，也不为提高指标剔除失败或修改题面。

### 其他宿主与导入

不能自动调用时，只将一个题面和对应版本 Skill 复制到干净工作目录，使用独立宿主会话，按 `request.txt` 审核。不要打开 Gold、此 README 或以往结论。保存原始输出后导入冻结计划中的一次运行：

可先用 `export --plan PLAN --run-id RUN_ID --output EMPTY_DIRECTORY` 导出完整中性载荷；导出目录不含计划、标签或 Gold。

```sh
python3 tests/statement/scripts/evaluate.py import --plan tests/statement/results/a-plan.json --run-id improved-st-001-base-r1 --raw /absolute/path/review.md --output tests/statement/results/imported --host your-host-version --model gpt-6.1-sol --run-date 2026-11-13T00:00:00Z
```

日期须替换为真实执行日期。导入声明由操作者保证输出真实，程序不能认证其来源，元数据会明确这一点。不能把本轮维护者的推演或单元测试样例导入为真实模型结果。

## 提取、匹配与 Evaluation A / D

被测报告正常输出 Markdown，另附不含 Gold 的结构化摘要。解析器提取问题、等级、原句、证据与实际修订建议。只有 Markdown 时生成待人工核对的候选，不直接判定命中。

```sh
python3 tests/statement/scripts/evaluate.py adjudication-template --run tests/statement/results/smoke/original-st-025-base-r1 --output tests/statement/results/smoke/original-st-025-base-r1/adjudication.json
```

裁定者阅读原始报告及对应 Gold 后填写模板：

- 需要语义判断时，`judge_kind` 为 `human`、`independent_model` 或 `maintainer_model`，注明身份与时间，不能把模型裁定称为人工确认。结构化空问题清单可由 `automatic_empty` 关闭，只确认模型没有列出扣分项，不宣称题面或 Gold 已由程序证明正确。
- 每个 finding 用 `matched`、`false_positive`、`new_confirmed`、`duplicate` 或 `pending`，按独立根因匹配，不要求措辞相同。
- `matched` 指向该 Gold 已确认的 `root_id`。同一根因取最高报告等级一次。
- `false_positive` 必须有 `novel_issue_review.status="rejected"` 和具体否定依据。未列入 Gold 的问题默认待核验，不能直接算误报。
- `new_confirmed` 须有独立证据及稳定的 `extra_root_id`，单列为 Gold 缺口。不得为了提高分数直接回写留出 Gold。
- `evidence_valid` 独立核对反例合法性、两种解释、输出或论证，不能从“命中了根因”推定证据有效。

模板绑定原始报告和提取结果哈希，修改后须重新裁定。未闭合裁定与 `needs_review` Gold 不进入已确认指标，报告保留缺口。Precision 分母为已裁定的 TP+FP；Recall 分母为已裁定运行覆盖的已确认 Gold 根因；完整样本覆盖另列，局部高比例不能代表全量能力。Important 指 Fatal+Major。FPR 为正确正式题面上出现至少一项误报的比例。严重度准确率以匹配根因为分母，证据有效率以已裁定证据为分母。

人工整理未能解析的报告时，可用 `normalize --run RUN_DIRECTORY --prediction NORMALIZED_JSON --identity OPERATOR`；必须忠实对应原始报告。该操作记录整理来源，不允许用整理过程补写模型未发现的问题。同一已确认根因的多个问题可全部映射到同一 `root_id`，取最高级别一次，并另核对去重计分。

报告逐题型给出 TP、FP、Gold 根因与 Fatal 命中，并保留漏检、误报、等级差异及其原始报告/裁定来源。发现新的正确问题时，原标注为正确的题面不再用于 FPR 分母，Gold 缺口另行披露。

## Evaluation B：稳定性

固定 12 个版本，每个 Skill 进行 5 次独立会话。比较根因集合众数次数/5、两两 Jaccard、每个根因的 Fatal/Major/Minor/未发现序列、分数极差与标准差、已否定误报和计分不一致。等价版本只增加节前空行，不改变文字、样例、规则或顺序。绝不只按总分一致判断稳定。

## Evaluation C：修复

仅使用真实原始审核的建议；不能从 Gold 生成一个理想修订后冒充模型建议。条件性方案需构造者明确选择，互斥建议用下标选择：

```sh
python3 tests/statement/scripts/evaluate.py apply-repair --run tests/statement/results/smoke/original-st-025-base-r1 --finding-id f1 --repair-indices 0 --author-choice 'synthetic author chooses directed roads' --output tests/statement/results/repair-example
python3 tests/statement/scripts/evaluate.py check-repair --bundle tests/statement/results/repair-example
python3 tests/statement/scripts/evaluate.py recheck-plan --source-plan tests/statement/results/smoke-plan.json --bundle tests/statement/results/repair-example --output tests/statement/results/repair-example/plan.json
python3 tests/statement/scripts/evaluate.py run --plan tests/statement/results/repair-example/plan.json --output tests/statement/results/repair-example/review
```

精确补丁必须只匹配一次；建议无法直接应用时保留待人工处理，不偷换为 Gold 修订。对缺陷变体，候选若逐字恢复为已核验的正确基础版，可得到 `reference_verified` 局部证书；它仍不是完整修复结论。其他修改须另写数学证明、有限枚举或人工语义复核，不能只听复审模型说“已修复”。

本轮选择政策固定在 [repair-policy.json](results/repair-policy.json)：按报告顺序采用第一套完整方案，同时应用该方案要求的配套改动，保留互斥方案的选择依据。不得看到复审结果后改选下一套。条件方案的作者选择由合成题作者（维护者模型）作出，不声称是人类确认。对同样 20 个根因分别保留旧、新两个候选，报告按 Skill 分组、固定以 20 为分母，未闭合者不算成功。

建议清楚但没有可直接应用的精确片段时，可按原始建议制作文本，再用 `import-repair` 保存，必须记录原审核、finding、操作者及应用依据。不得因为补丁提取失败就擅自换用 Gold 中的理想方案。

复审是新会话，只提供修订题面与同一 Skill。最终在修订目录保存 `repair-assessment.json`，字段由脚本 `repair_metrics` 的 required 集合定义：绑定原审与复审，记录 `resolved`（complete/partial/failed/needs_review）、是否改变原本明确的语义、新增规格错误、局部性、必要性及独立核验材料。`verification` 中的每项需给 `kind`、`artifact` 和 `result`；完整结论不能只引用模型自述。未能确认者不报成功。报告同时给原始目标数、闭合样本数和分子/分母。

使用 `repair-assessment-template --bundle BUNDLE --review-run REVIEW_RUN_DIRECTORY --root-id ROOT --output BUNDLE/repair-assessment.json` 生成待复核模板。每份独立证据还需给 `artifact_sha256`，报告检查文件及哈希；精确参考证书会重新计算，不只信任 JSON 中的成功声明。证明由模型撰写时保留 `maintainer_model`，不冒充人类确认。

`domain_changed` 单列输入域或协议资源变化；`changed_clear_semantics` 标记是否改变缺陷修补之外原已明确的规则。作者同意条件方案不能抹去这些变化。完整消除目标根因与“不改变明确任务且无新增错误的有效修复”分开统计。例如混合绝对/相对误差可能修复零除，却放宽原来明确的非零接受条件，即使恢复成正确基础版，也不能因此算作保持原任务的成功修订。复审计划中的仓库内候选路径相对本目录保存，支持换 checkout 复现。

## 报告与工程目标

```sh
python3 tests/statement/scripts/evaluate.py report --results tests/statement/results/smoke --output tests/statement/results/smoke/report.md
```

同时生成 `metrics.json`。初始目标为 Important Recall ≥85%、Precision ≥90%、正确题 FPR ≤10%、核心判断一致性 ≥80%、有效修复 ≥85%、确认新增实质错误为 0。这些是待检验目标，脚本不因若干样本通过而宣布达标。N/A 表示没有分母。尤其“尚无已复核修订”时的新增错误 0 不证明安全。

跨切分汇总使用 `merge --inputs DEVELOPMENT_DIRECTORY HOLDOUT_DIRECTORY --output NEW_DIRECTORY`；它保留两份计划全部 Gold 哈希，同一 run ID 的不同回答不能按分数挑选。`report` 可加 `--repair-results tests/statement/results/repairs`，从独立候选目录汇总 C。总表与开发/留出分表均保留原始分子、分母及裁定缺口。

本轮完整真实存档可用 `python3 tests/statement/scripts/audit_archive.py` 重新核验，结果写入 `results/archive-audit.json`。该审计要求原生会话证据及完整的 216+40 次结果；其他宿主的导入声明不冒充这种原生认证。它检查文件与哈希，也重新执行有限核验程序，不把通过结果当作人类专家审题结论。

有无 CPScore 的完整对照另用 `python3 tests/statement/scripts/compare_harness.py --audit` 核验，结果写入 `results/harness-vs-direct/archive-audit.json`，同时重建对照报告。两种对照共享部分真实调用，不能把两个审计的会话数相加当作独立样本数。

本轮真实运行状态、宿主错误及结果见 [results/](results/)。先前参数错误、沙箱初始化失败和审批阻止不算模型回答，均与成功的调用区分。每次结果的 `execution_status`、原始输出及裁定才是当前证据；不能从目录存在推定完成。
