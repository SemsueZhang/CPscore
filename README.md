# CPscore

CPscore 用于算法竞赛题的证据式审查，提供四个可独立使用的 Agent Skills：

| 技能 | 职责 |
| --- | --- |
| `cp-statement-review` | 题面定义、输入输出、约束、边界和样例 |
| `cp-solution-review` | 程序算法、正确性、复杂度和实现 |
| `cp-editorial-review` | 题解断言、推理、证明和复杂度 |
| `cp-novelty-review` | 检索相似题与论文，对照方法，独立给出 A–E（含 C+）新颖度初判 |

前三项使用协议 v2 的证据式 10 分制。模型核验材料并记录覆盖与问题，共享 Python 代码校验结构、按根因去重、算分和生成报告。数学分析优先，有限测试只作辅助。文风、主观难度与原创性不扣分，新颖度不混入正确性分数，最终由用户裁决。

## 开始审查

Python 3.10+，核心与安装器仅依赖标准库。在完整源码目录中执行：

```sh
python3 -m cpscore init-report --scope statement,solution,editorial --output review.json
```

按[审查协议](docs/protocol.md)填写当前材料版本、固定覆盖项与问题证据，再运行：

```sh
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --output review.md
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore validate scored.json --scored
```

初始化骨架没有审查活动，分数为 `null`。每个已确认 Fatal 根因扣 10 分，Minor 扣 1 分，最低 0 分，同根因在对象内及跨对象总评分别只扣一次，总评不取平均。已确认扣分使分数低于 6 时，`qualification` 立即为 `fail`。只有覆盖完成、无未决严重疑点且分数至少 6 时才为 `pass`，其余为 `undetermined`。`completion` 独立报告覆盖是否完成，不能用“已不合格”冒充“已审查完”。

旧版报告需迁移并重新审查：

```sh
python3 -m cpscore migrate old.json -o new.json
```

迁移保留旧源及迁移记录，拒绝覆盖已有文件，不自动沿用旧分数、发现或完成结论。版本与复审要求见[协议](docs/protocol.md)。

## 部署技能

从完整源码为已有项目安装，安装与检查不调用模型 API：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
```

支持 `codex`、`claude-code`、`opencode-deepseek` 三种文件适配，省略 `--harness` 时选择 all。裸 DeepSeek API 不是 Harness，不支持 `--harness deepseek`。安装后的四个技能共用项目内一份 `.cpscore` 运行时，入口不依赖原仓库路径。manifest 和哈希保护拒绝覆盖同名他人技能或用户改动，也保护重装与卸载操作。

例如在 Codex 中调用：

```text
$cp-solution-review 审查 statement.md 与 solution.cpp，保存 review.json 并生成 review.md。
```

安装路径、各宿主调用、重装卸载和保护规则见[Harness 手册](docs/harnesses.md)。文件安装、CLI 在 PATH、真实模型加载是三层独立验证。真实调用脚本为 `python3 scripts/harness_smoke.py --help`，结果以实际留存记录为准。2026-11-10 本机验收：Codex 三个正确性技能均完成真实调用，Claude Code、OpenCode 因 CLI 缺失未验证。Docker 守护进程不可用，容器集成未执行。

## 工具与验证边界

- [审查协议](docs/protocol.md)：v2 覆盖记录、分级、证据、算分和迁移。
- [Harness 手册](docs/harnesses.md)：安装、移除、宿主路径及官方来源。
- [隔离验证手册](docs/validation.md)：可选 `check-candidate`、`bench` 和容器集成。没有可验证隔离时不在宿主执行待审程序。
- [新颖度手册](docs/novelty.md)：CPRet、arXiv、来源读取、缓存和实际用量记录。

本地回归入口为 `python3 -m unittest discover -s tests -v`。可选安装 `jsonschema` 后同时执行独立 Draft 2020-12 对照检查，未安装时该项明确跳过，运行时不依赖它。[真实题衍生判例](fixtures/review_cases/README.md)与[历史审计证据](tests/history/README.md)分别保留人工裁定和真实调用结果。结构验证能检查字段、版本与派生分数一致性，不能认证自然语言证明的真实性或保证模型找全错误。有限回归、模拟外部响应、真实隔离测试与真实 Harness 调用也分别报告，AI 审核准确率尚未建立。

源码位于 `cpscore/`，技能在 `skills/`，测试与人工夹具在 `tests/`、`fixtures/`。支持源码运行与 `pip install -e .`，普通 wheel 缺少源码资源时只支持核心评分与报告，技能部署会明确报错。审核报告、检索附件、缓存和模型试跑记录留在使用者的工作目录。
