# CPscore

CPscore 用于算法竞赛题的证据式审查。项目提供四个 Agent Skills：

| 技能 | 职责与输出 |
| --- | --- |
| `cp-statement-review` | 题面正确性审查，参与证据式10分制 |
| `cp-solution-review` | 程序正确性审查，参与证据式10分制 |
| `cp-editorial-review` | 题解正确性审查，参与证据式10分制 |
| `cp-novelty-review` | 相似题与论文检索、方法对照，独立给出A–E（含C+）新颖度初判 |

各技能可以独立工作。前三项也可读取题面、程序与题解交叉核验；新颖度最终判断由用户裁决。

正确性审查中，模型填写结构化证据，共享 Python 代码校验、按根因去重、计算分数并生成报告。数学推导优先，极小反例和有限测试辅助；不按文风、主观难度或原创性扣分，也不把测试通过当作正确性证明。新颖度由独立技能依据实际检索及原文比较判断，不混入正确性分数。

## 快速开始

运行环境为 Python 3.10+，核心与安装器只使用标准库。从本仓库直接运行，不要求全局 pip 安装：

```sh
python3 -m cpscore --help
python3 -m cpscore init-report --scope statement --output review.json
```

读取 [审查协议](docs/protocol.md)，填写题面实际版本、问题证据与完成状态。初始化骨架始终为未审查，不能直接当作无错误结论。完成后运行：

```sh
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --output review.md
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore validate scored.json --scored
```

需要在任意目录使用命令时，可在虚拟环境执行 `python3 -m pip install -e .`，随后使用 `cpscore` 或 `python3 -m cpscore`。技能部署请保留完整源码，普通 wheel 未携带源码资源时只支持核心评分与报告，安装技能会明确报错。

## 安装四个技能

从本仓库运行，为已有目标项目部署：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
python3 -m cpscore reinstall --project /absolute/path/to/problem --harness codex
python3 -m cpscore uninstall --project /absolute/path/to/problem --harness codex
```

三个实际适配目标：

| `--harness` | 发现目录 | 示例调用 |
| --- | --- | --- |
| `codex` | `.agents/skills` | `$cp-solution-review 审查 statement.md 和 solution.cpp` |
| `claude-code` | `.claude/skills` | `/cp-editorial-review 审查 editorial.md` |
| `opencode-deepseek` | `.opencode/skills` | `@cp-statement-review 审查 statement.md` |

`--harness` 可重复或设为 all，省略也为 all。第三目标由 OpenCode 加载技能，由用户选择 DeepSeek 模型。裸 DeepSeek 模型/API 不是 Harness，`--harness deepseek` 明确 unsupported，不创建虚构目录。真实路径与调用限制见 [Harness 适配](docs/harnesses.md)，其中列出实际核对的官方来源。

安装后只有一份 `.cpscore` 共享运行时与协议，各技能用自身目录的 `scripts/cpscore.py` 调用。不依赖原仓库绝对路径，整个目标项目移动后仍可运行。安装器用 manifest 与 SHA256 记录自己管理的文件，拒绝覆盖他人同名技能、拒绝安装内部符号链接，遇到用户改动会报错并保留文件。卸载一个目标不影响其他目标，最后一个才移除共享受管文件。

新安装使用manifest格式2，重装可把旧格式1的三技能安装升级为四技能；已有受管文件被修改时仍拒绝覆盖。`check`会列出各宿主实际安装的技能。新颖度手册以`.cpscore/novelty.md`共享，只在需要参数或排错时读取。

`check` 分别报告文件是否安装完整、CLI 是否出现在 PATH、真实 Harness 调用是否验证。文件检查成功不代表模型已经加载技能，也不代表 CLI 已登录。安装与 check 都不会调用模型 API 或花费额度。

## 新颖度审查

在已安装技能的项目中调用，例如：

```text
$cp-novelty-review 评审 statement.md 与 editorial.md 的新颖度，按当前题来源和评审时点检索先例，保存 novelty.md 及证据附件。
```

常规只加载技能正文。CPRet、arXiv和来源缓存由随包工具或宿主等价工具提供，普通网页补搜由宿主提供；未完成的覆盖如实记录。A为原题，B为做法可套用，C为想法类似且仍需新思考，C+表示虽属C但各项推导十分自然，推荐用于正式比赛，D为本轮未发现实质先例的新题，E还需有具体的正面质量依据。检索未完成时可待定，不宣称全球原创。

源码工具入口示例：

```sh
python3 -m cpscore novelty --help
python3 -m cpscore novelty search cpret --query-file model-query.txt --output searches/cpret.json
python3 -m cpscore novelty search arxiv --query-file paper-query.txt --output searches/arxiv.json
python3 -m cpscore novelty inspect --record searches/cpret.json --ids <索引中的ID>
```

安装后将`python3 -m cpscore`替换为该技能目录的`python3 <技能目录>/scripts/cpscore.py`。工具保存全量候选，先返回索引，再按需展开链接、摘要和正文片段，支持缓存与实际usage汇总；工具本身不调用模型或自动生成A–E（含C+）。详见[新颖度手册](docs/novelty.md)及[本次迁移验证](docs/novelty-migration.md)。

## 评分和报告

每个已审查对象从 10 分开始。每个**已确认**致命根因扣 10 分，轻微根因扣 1 分，最低 0 分，6 分及以上通过。同根因在对象内和跨对象总评中分别只扣一次，总评不取平均。共用根因需要相同机制、同一修复及各对象证据，不能仅依文本相似判断。

未审查对象分数为 null，scope 内未完成或存在未决疑似致命问题时，审核状态优先为 pending，即使当前已确认扣分使分数低于 6 也如此。疑似问题不扣分，排除严重疑点且完成范围后才按分数判定通过或不通过。已解决问题只有重新核验当前版本后才不再扣分。

输入 JSON 记录版本、发现、证据、复现、修复和核验。每条证据绑定 snapshot 与材料版本，旧证据不能用于新轮评分。材料版本推荐文件 SHA256，使用人工标签时由审查者负责对应关系。Markdown 报告和结构化 JSON 包含分项、整体结论、根因清单、每条扣分证据、未决事项、修复建议以及已执行和未执行的验证。

结构定义位于 `cpscore/schemas/`。工具可以验证字段、状态、版本与算分一致性，不能自动判定自然语言数学证明是否正确，也不能保证模型找全错误。完整规则见 [协议](docs/protocol.md)。

可直接运行带证据的例子：

```sh
python3 -m cpscore score examples/cross-object-review.json
python3 -m cpscore score examples/resolved-review.json
```

前者演示三个对象各 9 分、跨对象根因去重后整体 8 分，后者演示保留旧轮并以当前版本证据复审至 10 分。可对照 [首轮报告](examples/cross-object-report.md) 与 [修复复审报告](examples/resolved-report.md)，材料定位在 examples 中对应的版本文件。

## 验证与限制

2026-11-09 的实际执行环境、通过与跳过项目、容器不可用结果及尚未验证的范围见 [本地验收记录](docs/acceptance.md)。

```sh
python3 -m unittest discover -s tests -v
```

测试覆盖评分与协议、报告生成、技能安装检查卸载重装、移动项目后的独立入口、同名冲突、修改保护、符号链接与 manifest 路径逃逸，以及可选验证工具的边界。有限回归验证当前实现的这些行为，不能证明任意竞赛题的正确性，也不能替代真实 Harness 调用验证。

已真实调用 Codex CLI，以 GPT-6.1 Sol xhigh 对一个人工题面完成 `cp-statement-review` 加载与工具烟测，生成有效报告并计算为 9 分/pass。原提示、材料、报告与脱敏事件见 [集成证据](tests/integration_evidence/codex-statement/README.md)。这只验证一次加载和工具接线，不是准确率实验，其余两技能、Claude Code 与 OpenCode + DeepSeek 未在该次调用中验证。

可选验证使用本地 Docker 或 Podman 隔离运行，先自行构建本地镜像：

```sh
docker build -f Dockerfile.runner -t cpscore-runner:local .
python3 -m cpscore check-candidate --candidate fixtures/validation/correct.cpp --input fixtures/validation/sample.in --expected fixtures/validation/sample.out
python3 -m cpscore check-candidate --candidate fixtures/validation/wrong.cpp --oracle fixtures/validation/oracle.py --validator fixtures/validation/validator.py --generator fixtures/validation/generator.py --seed 20261109 --cases 20
python3 -m cpscore bench --candidate fixtures/validation/correct.cpp --input fixtures/validation/sample.in --validator fixtures/validation/validator.py --warmups 1 --repetitions 3
```

第二条验证命令故意使用错解，演示固定 seed 对拍与反例保存。反例证据默认保存在 `.cpscore/counterexamples/<序号>-<输入哈希>-<唯一标识>/`，包括输入、预期与实际输出、源文件快照、环境与限额、manifest 和复现命令。预期答案仍须独立核验，工具不会自动把对拍不一致转换成确认错误或扣分。

运行器在隔离容器内编译与执行 C++17 / Python，只读挂载源文件，禁网、非 root、限制时间、内存、进程数、CPU 和输出。镜像构建可能联网下载依赖，与禁网运行是不同阶段。未安装引擎、daemon 不可用、镜像缺失或隔离能力不足时明确返回 unavailable，不退回宿主直接执行。性能记录包含环境和计时范围，不能仅凭容器计时断言目标评测机超时。详细参数与验证边界见 [可选验证工具](docs/validation.md) 和 [验证夹具](fixtures/validation/README.md)。

这些工具由用户选择触发，不是核心评分的强制依赖。没有运行的项目应保留原因，不会记为通过。模型与模型 API 也不是本地评分所必需。
