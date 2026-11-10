# 题目总评、比赛总评与选手表现预测

题目和比赛总评交付 Markdown 三档结论及修改意见。材料未齐时标记评定未完成，不另设质量档。选手表现预测只交付报告，不要求盲测。

## 共用入口

```sh
python3 -m cpscore assess init problem -o problem.json
# 读取材料、完成分析并填写输入记录后：
python3 -m cpscore assess report problem.json -o problem.md
```

比赛与预测分别将 `problem` 换为 `contest`、`performance`。安装后改用 `python3 <实际技能目录>/scripts/cpscore.py`。引用路径相对输入文件所在目录；标准输入使用当前目录，也可用 `--base-dir` 指定。`--format json` 查看重算结果，默认交付 Markdown。

智能体负责分析，工具负责校验、重算和渲染，不自动调用模型。预测也可直接写 Markdown。

## 题目总评

`problem.json` 的 `schema_version` 为 `1.0`，`kind` 为 `problem`。填写 `title`、`reviews`、`novelty`、`design_reviews`。

- `reviews`：题面、程序、题解、数据的当前原始 `review.json` 或带原始 review 的 `scored.json` 路径数组。可按对象分文件，也可在一份报告中联合审查。多次智能体审查全部保留。工具从原始记录重算每个对象的分数，不采用存储的总分，也不将各项扣分合并代替取最低档。同一对象的多份报告须指向相同 `artifact_version`。
- `novelty`：每份报告对应 `{grade, report, reason, edits}`，report 为非空 Markdown 报告路径。grade 是从该报告提取的当前等级，A/B 不合格、C/D 合格、C+/F 推荐。A/B 必须给出修改意见。工具不从自由文本猜等级，智能体必须核对等级与原文一致。无法消除先例关系时应明确建议换题或改变核心任务，不承诺修改后能升级。
- `design_reviews`：每次设计审查填写独立的 `{id, dimensions, original_method}`，不删除较低结果来提高总评。dimensions 固定为 `solution_space`、`subtasks`、`full_score`、`coherence`，分别审查解法空间、部分分、满分做法与限制、条件和观察价值。

每个维度使用以下记录，合格或不合格时 edits 至少一项，推荐时可以为空。未完成的 verdict 为 null。

```json
{
  "verdict": "合格",
  "reason": "两个子任务的条件相同，但分值不同，不能反映进阶。",
  "evidence": ["statement.md 子任务表第2、3行"],
  "edits": ["合并重复子任务，或增加能对应独立做法的条件。"]
}
```

`original_method` 为 `{suitable, reason, simpler_alternative}`。suitable 为 true 时表示已核验原做法适合竞赛，false 表示不适合，null 为未完成。原做法不适合时，只有已核验的更简单竞赛做法允许这一项判为合格，并强制给出更新意见。替代记录示例：

```json
{
  "verified": true,
  "description": "具体的更简单算法及其与原做法的比较。",
  "correctness": "覆盖全部合法输入的正确性论证，不能只引用有限测试。",
  "complexity": "全范围时间、空间复杂度及与限制的对应。",
  "suitability": "发现线索、必要知识和实现负担为何适合竞赛。",
  "evidence": ["alternative.md 第2至4节"]
}
```

无替代做法用 null。只有想法时用 `verified: false`，不能触发合格例外。该项被判为合格，不会提升其他不合格项，也不会更改原程序、题解或新颖度报告。修改建议不表示材料已经修好。

**汇总取所有结果的最低档。** 题面、程序、题解和数据各项 9～10 推荐、6～8 合格、0～5 不合格，沿用其完成度与未决 Fatal 门槛。全部完成才能给合格或推荐，任意已确认不合格都可确定总评不合格，同时保留未完成标记。原做法适合度与设计维度同样参与取最低档。不能把各项分数平均、按多数票通过或只保留最高的一轮审查。

## 比赛总评

`kind` 为 `contest`。必须围绕本场实际要求填写 requirements：

```json
{
  "audience": "具备基础图论、DP能力的省选选手",
  "format": "个人OI，独立子任务计分",
  "duration_minutes": 300,
  "problem_count": 3,
  "scoring": "每题100分，各子任务取组内最低得分，无提交罚时",
  "goals": ["区分省选中上水平选手，保留基础得分入口"],
  "constraints": ["使用C++17，离线批处理，无交互题"]
}
```

这是格式示例，不是默认比赛要求。缺少关键要求时先分析已有材料，报告说明缺口，不给合格或推荐。

`problems` 每题为 `{id, points, review}`，review 指向可重算的 `problem.json`，不能引用手写档次或已经渲染的 Markdown。`assessments` 固定包含 `requirements_fit`、`difficulty_progression`、`topic_balance`、`time_budget`、`score_distribution`、`differentiation`、`fairness`。每项按上述维度格式填写，并增加 `requirement_refs`，例如 `["audience", "duration_minutes", "goals"]`，说明该判断依赖哪些实际要求。reason 必须解释具体题目组合与这些要求的关系，evidence 引用题目和推导。

工具重算全部单题总评，题数与要求不一致判不合格，再与比赛组合各项取最低档。单题全部推荐并不自动意味着整场推荐。Markdown 包含比赛要求、分项理由、修改意见和依据。

## 选手表现预测

`kind` 为 `performance`，不产生质量等级。直接写 Markdown 时说明目标选手、赛制、时长和假设，再按选手层次和题目分析思考路线、障碍、投入时间、得分、策略和预测依据。不要求盲测，不编造实测成绩。

如使用工具，`context` 包含 `audience`、`format`、`duration_minutes`；`problems` 是 `{id, title, max_score}` 数组；`assumptions` 为非空假设数组。每类选手记录如下：

```json
{
  "name": "基础组",
  "profile": "熟悉基础算法，尚不熟悉该题关键转化。",
  "strategy": "优先取得第一题部分分，再尝试第二题。",
  "predictions": [{
    "problem_id": "T1",
    "score_range": [20, 40],
    "time_range_minutes": [30, 60],
    "route": "先枚举，再利用特殊条件简化。",
    "bottlenecks": "难以发现满分所需的不变量。",
    "basis": "20分子任务只需直接模拟，40分子任务要求一次非平凡转化。",
    "confidence": "medium"
  }]
}
```

每类选手覆盖所有题目，可用零投入、零得分表示放弃。得分区间不能超过满分，时间区间不能超过比赛总时长，各题时间下界之和不能超过总时长。confidence 为 low/medium/high，表达分析把握，不是统计置信水平。各题上界不一定能同时达到，报告中的逐题区间合计不作为有保证的实际总分。
