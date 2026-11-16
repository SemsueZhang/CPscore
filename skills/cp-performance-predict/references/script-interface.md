# 离线脚本接口

使用 `scripts/predict.py` 校验或批量比较时读取；语义预测见[共享分析](prediction.md)。

`scripts/predict.py` 是离线一致性辅助，不从题面自动产生路线，不替代 LLM 的语义判断。只使用 Python 标准库。分析 JSON 顶层：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | `1`，独立于画像版本 |
| `problem_id`、`summary`、`sources` | 题目标识、目标与约束摘要、实际查过的来源或本地材料路径 |
| `environment` | 本次时长、语言、模板与反馈等条件的文字说明 |
| `scoring` | `mode` 为 `binary`／`subtasks`／`unknown`；`subtasks` 每项用 `id/conditions/credit/source` 记录真实评分依据 |
| `routes` | 完整路线列表，至少一条满分路线 |
| `uncertainties` | 题目分析、门槛、环境或知识覆盖的不确定性，不能省略 |

每条路线用 `id/name/target/method/correctness/complexity/initial_attempts/gates/progress`。`target` 为 `full` 或 `partial`，部分分路线必须用 `subtask_ids` 指向有来源的实际子任务。`correctness` 须含足以核查的理由，不能只写“标准算法”。

`gates` 是按依赖顺序排列的门槛，含 `id/dimension/minimum/task`，`dimension` 是 K/D/P/I/B，`task` 描述这道题的具体工作。`minimum` 对照行为量表，是分析者的可审查假设，不是训练出的阈值。每条完整路线都要检查 D/P/I/B，可用 0 表示无额外要求。K 门槛额外提供 `algorithm_id`，`role` 可为 `required`（默认）或 `helpful`。有帮助的知识不阻断路线、不制造输出分组。

K 门槛可附 `derive: {"D":4,"P":3,"task":"具体可重建的步骤与额外负担"}`。仅当 D/P 均支持该重建时，将原知识障碍放宽为“有困难的重建可能”，绝不直接当作已掌握或已发现。不能重建的既有模板不应随意配置此字段，可能重建但未建模的部分列入不确定性。

`progress` 每项用 `after_gate/description` 指定有意义的进展，脚本只在此前必要门槛全部支持时保留它。部分路线得分只引用子任务，不自动相加或估计百分比。

脚本按路线逐项给 `supported/strain/gap/unknown`：达到假设门槛为支持，差一档为明显困难，差更多为较大障碍，缺失为未知。画像明确填0表示不具备该行为，在正门槛下按较大障碍处理，不因只差一档就视为接近完成。0 门槛本身不依赖画像是否填写。它不是普遍适用的心理模型，档位附近不应被解读为突然必会或必不会。整体结论取至少一条完整可行路线的支持情况，保留同样适合的路线和真实部分分选项，不把维度加权。未知完整路线会限制最终判断，即便已有确定的部分进展。

辅助脚本的五种整体状态只用于记录和归并，不限制最终结论的用语、数量或区别方式。最终仍应围绕本题具体路线和能力条件表达，不能只返回五档标签。

在本 Skill 目录运行：

```sh
python3 scripts/predict.py audit
python3 scripts/predict.py validate player.md
python3 scripts/predict.py predict analysis.json --profiles player.md
python3 scripts/predict.py predict analysis.json --details
```

默认使用参考锚点，输出合并结论。`--profiles` 可提供个人画像或画像数组，不限于参考锚点。`--details` 才附内部逐画像路线记录与敏感性诊断，通常不作为最终报告。独立安装时须通过 `CPSCORE_CATALOG` 或全局参数 `--catalog` 提供同一共享目录，依赖缺失明确报错。
