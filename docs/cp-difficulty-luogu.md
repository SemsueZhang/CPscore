# 洛谷八档难度预测

`cp-difficulty-luogu` 的唯一目标是提高前沿 LLM 对未见算法竞赛题目洛谷八档难度的预测准确性。输入是同题题面与完整正确解法，输出是原生 1～8 档和简洁依据。一个模型、一个简洁 Skill、经过审核的专家规则，通过独立 LuoguBench 与纯 LLM 配对验证。

当前版本 `cpscore-difficulty-luogu-v2.0.0` 已完成一次[未蒸馏版 87 题开发诊断](../data/difficulty/evaluations/20261114-v2-undistilled-sol-high/Report.md)。GPT-6.1 Sol high 的纯 LLM / Skill 命中为 68/87 / 65/87，本轮未观察到 Skill 增益，不作为独立测试成绩。原 `cp-difficulty-rate` 完整保留为历史版本，其 CF/AT 工具独立使用，不参与主评分。版本变化见[版本记录](difficulty-versions.md)。

## 直接使用

复制整个 `skills/cp-difficulty-luogu/` 到宿主技能目录，提供同一道题的材料：

```text
$cp-difficulty-luogu 根据 statement.md、editorial.md 和 std.cpp 预测洛谷八档难度，简述独立解题的主要障碍。
```

评分过程为理解完整可靠路线，考虑更容易的完整解法，识别独立发现、证明、必要知识和实现中的主要障碍，再结合适用的已确认专家经验预测等级。K/T/I 是分析视角，不输出三个必填数字，不加权合成，不强制逐个锚题比较。

原生档位依次为 1 入门、2 普及-、3 普及、4 普及+/提高-、5 提高、6 提高+/省选-、7 省选/NOI-、8 NOI/NOI+/CTS。0 为未知，不是入门，不进入 Benchmark 计分。正文默认返回简短 Markdown，机器工具返回 `id,level,label,reason` 四字段 JSON。

## 单题 CLI

可选工具只用 Python 3.8+ 标准库。输入沿用 LuoguBench 的无标签格式：

```json
{
  "id": "blind_item_001",
  "statement_md": "完整题面和约束",
  "solutions": [{
    "method_id": "method_1",
    "editorial_md": "完整正确解法与证明、复杂度",
    "std": {"language": "cpp17", "interface": "stdin_stdout", "code": "配套 C++17 程序"}
  }]
}
```

支持 1～3 条解法，`interface` 可为 `library`。材料本身必须先核对，不能混入其他题的解法。仓库合成接口样例为 `tests/difficulty/fixtures/item.json`，不属于准确率评测。

在 CPScore 根目录运行，下列模型 ID 需替换为实际可用的前沿模型：

```sh
cpscore_tools=skills/cp-difficulty-luogu/scripts
cpscore_model=YOUR_FRONTIER_MODEL_ID
python3 "$cpscore_tools/difficulty.py" prepare \
  --item /absolute/path/item.json --model "$cpscore_model" --reasoning high \
  --out /absolute/path/single-request
python3 "$cpscore_tools/difficulty.py" run \
  --prepared /absolute/path/single-request \
  --adapter "$cpscore_tools/codex_adapter.py" --out /absolute/path/single-run
```

内置 adapter 复用已登录的 Codex CLI，每题一个临时会话，只调用一次指定模型，禁止工具调用，不增加模型复核或语义重试。可用 `CPSCORE_CODEX_CLI` 指定可执行文件。已通过一次合成题传输检查及两组各 87 题的真实模型调用，原始记录位置见上述报告。其他宿主可用相同 adapter 协议：stdin 接收请求 JSON，stdout 返回四字段预测，或 `{"prediction": {...}, "usage": {...}}`。复用 LuoguBench 的 adapter 接口，不管理 API key。

`difficulty.py run` 默认串行，可加 `--workers 2` 并发独立单题请求。每题仍是同一模型的一次独立判断，不共享会话、不投票；运行记录保存并发数和会话 ID。

请求先冻结，运行保存原响应、指纹、失败与用量。运行目录必须为空，不覆盖历史结果，无自动重试。失败保留为 incomplete，修复后创建新运行目录并记录重跑原因，不根据等级或标签反复重试。自定义 adapter 也必须逐题新上下文、同一模型和参数，不读取标签。接口演示应返回 `demo:true`，正式计分会拒绝演示结果。

已收集的单题输出可独立检查：

```sh
python3 "$cpscore_tools/difficulty.py" validate-output \
  --item /absolute/path/item.json --prediction /absolute/path/prediction.json
```

单题未知输出另加 `--allow-unknown`。正式 Benchmark 始终拒绝 0、越界、浮点档位、档名不匹配、串题 ID 和字段错误。

## 专家反馈与蒸馏

正式规则在 Skill 内的 `references/expert-rules.json`，开发来源在 `data/difficulty/expert/`。本轮只搬入五条旧 K/T/I 单轴反馈，标为 `legacy_axis_only`，不参与正式评分或通用经验蒸馏。

```sh
cpscore_expert=data/difficulty/expert
python3 "$cpscore_tools/experts.py" new-case --id case_001 --out /absolute/path/feedback.json
# 填写反馈表。material_path 相对于 expert 数据目录，material_sha256 是完整无标签 JSON 的规范化 SHA256。
python3 "$cpscore_tools/experts.py" add-case --data "$cpscore_expert" --file /absolute/path/feedback.json
python3 "$cpscore_tools/experts.py" distill --data "$cpscore_expert" \
  --case-ids case_001 --out /absolute/path/distill-request.json
python3 "$cpscore_tools/experts.py" new-rule --id experience_001 --out /absolute/path/candidate.json
# 将蒸馏请求交给一个 LLM，依据模板整理候选，状态保持 candidate。
python3 "$cpscore_tools/experts.py" add-rule --data "$cpscore_expert" --file /absolute/path/candidate.json
python3 "$cpscore_tools/experts.py" check --data "$cpscore_expert"
```

专家案例需有原生标签及来源、完整正确材料、解释、家族和人工确认才能进入蒸馏。候选经验必须包含内容、来源案例、适用条件、局限、反例及反例检查。人类查证后手动改为 confirmed，记录确认人、日期和引入版本。然后手动挑选完整规则记录写入正式库、更新版本并执行：

```sh
python3 "$cpscore_tools/experts.py" check-release --data "$cpscore_expert"
```

工具只录入、导出开发请求和校验，不调用蒸馏模型，不自动审核或修改 Skill。未确认经验不能通过正式库检查。详细边界见[维护协议](../skills/cp-difficulty-luogu/references/maintenance.md)。

计算反馈材料指纹：

```sh
python3 -c 'import sys; sys.path.insert(0,"skills/cp-difficulty-luogu/scripts"); from common import digest,read_json; print(digest(read_json(sys.argv[1])))' /absolute/path/item.json
```

## Benchmark 协议与命令

复用独立 LuoguBench 工程的材料格式、输入/标签校验和全部既有指标。本模块使用 `cpscore-luogu-paired-isolated-v2`，是专用配对实验协议，不能冒充禁止额外 Skill 的 LuoguBench 官方 `isolated-text-v1` 成绩。

新集先由维护者制作无标签 `inputs.jsonl` 与私有 `labels.jsonl`。先生成 split 模板，人工填写每题实际身份、别名、题族、每个 method 对应的实际题号，并确认材料及家族检查。不要把标签填入 split。

```sh
cpscore_bench=/absolute/path/LuoguBench
python3 "$cpscore_tools/benchmark.py" manifest \
  --inputs /absolute/path/new-inputs.jsonl --dataset-id luogu-independent-001 \
  --purpose independent --registry data/difficulty/development-registry.json \
  --out /absolute/path/new-split.json
# 人工填写并确认 new-split.json，再准备两组冻结请求，不调用模型。
python3 "$cpscore_tools/benchmark.py" prepare \
  --inputs /absolute/path/new-inputs.jsonl --split /absolute/path/new-split.json \
  --registry data/difficulty/development-registry.json --luogubench-root "$cpscore_bench" \
  --model "$cpscore_model" --reasoning high --out /absolute/path/paired-requests
for cpscore_mode in baseline skill; do
  python3 "$cpscore_tools/difficulty.py" run \
    --prepared "/absolute/path/paired-requests/$cpscore_mode" \
    --adapter "$cpscore_tools/codex_adapter.py" --out "/absolute/path/runs/$cpscore_mode"
done
# 两组全题输出冻结后，才由维护者读取标签计分。
for cpscore_mode in baseline skill; do
  python3 "$cpscore_tools/benchmark.py" score \
    --prepared "/absolute/path/paired-requests/$cpscore_mode" \
    --run "/absolute/path/runs/$cpscore_mode" --labels /private/path/labels.jsonl \
    --luogubench-root "$cpscore_bench" --out "/absolute/path/scores/$cpscore_mode"
done
python3 "$cpscore_tools/benchmark.py" compare \
  --baseline /absolute/path/scores/baseline/metrics.json \
  --skill /absolute/path/scores/skill/metrics.json
```

标签兼容既有 LuoguBench：`id,problem_id,bucket,level,label`，可含来源等字段。`bucket` 是维护者的分类记录，不进入请求。0 是待补标签，正式计分直接报错，先补齐或在冻结评测集之前排除，不能按预测结果筛题。

基线只有任务、八档名称和同题完整材料，不加载 Skill、经验或锚题。两组使用完全相同的模型、推理参数、输入和逐题上下文隔离方式，唯一实验差异是冻结 Skill。报告 Accuracy、MAE、Within-one-level、Spearman（并列平均秩）与平均有符号误差 `prediction - truth`，正数表示高估。常数序列的 Spearman 为 null。保留覆盖率、逐题输出和所有失败，不发布筛选子集的独立成绩。

旧 87 题只能诊断。准备时将 inputs 指向 `$cpscore_bench/data/inputs.jsonl`，split 使用 `data/difficulty/luogubench87-development.json`，其余步骤相同。输出始终标记 `development_diagnostic`。不能将已查看答案并改过 Skill 的题重新命名为独立集。按家族隔离、盲化与人工材料复核的限制见[数据说明](../data/difficulty/README.md)。

## 基础验证与未完成项

```sh
python3 -m unittest discover -s tests/difficulty -p 'test_*.py' -v
LUOGUBENCH_ROOT=/absolute/path/LuoguBench \
  python3 -m unittest discover -s tests/difficulty -p 'test_*.py' -v
python3 .github/scripts/test-difficulty.py  # 原版平台工具回归，本地已有脚本
```

前一条不需要 LuoguBench，会跳过四项外部集成检查。后一条额外验证现有输入契约、无标签配对准备、五项指标及计分拒绝条件。测试均为合成接口材料，不是预测准确率实验。

尚待完成：人类整理题族并留出新独立集，提供完整专家案例并确认候选规则，再冻结进行独立配对 Benchmark。已完成的旧 87 题实验保持开发诊断身份，没有据其标签修改评分规则或自动蒸馏经验。

[技能入口](../skills/cp-difficulty-luogu/SKILL.md) · [原版说明](cp-difficulty-rate.md) · [历史与现状](difficulty-assessment-summary.md) · [返回说明目录](README.md)
