# 专家反馈蒸馏

仅处理用户的评级、理由、纠正或比较反馈；独立评分只读规范和已确认经验，不读本页模板、原始案例或候选。

## 对话中的处理

1. 固定材料、完整路线和标签；独立预测先于专家结论，已知结论标反馈分析。
2. 保留档位、原话、比较与不确定性，区分模型判断。用户明确给出的结论、经验与规则按已确认专家输入处理；已声明验证的内容不降格为待验证或重复要求确认。只给档位不代写理由；追问聚焦发现障碍、发现后的推导负担、模板条件或相邻档差异，不要求填全表。
3. 在对话展示用户原意、模型候选经验、条件及例外；个案不足以泛化时明确说明。
4. 以改约束、线索、实现或已核实另解检查边界；推测反例标待核，单例可支持窄经验，不能推广整类算法等级。
5. 用户直接给出的通用经验按原意标记 `confirmed`；模型额外归纳的内容、条件或适用范围经用户明确认可才确认。单题评级不等于确认模型另行提出的通用经验。纠正／撤回保留依据，不改写旧原话。

## 最小记录格式

开发记录可用每行一对象的 `cases.jsonl` 与 `candidate-rules.jsonl`。仅在用户指定或已授权的仓库外研发目录持久化，否则在对话展示；原始题、真实标签、候选不进发行 Skill。以下仅字段示意。

案例反馈：

```json
{
  "case_id": null,
  "feedback_id": null,
  "family_id": null,
  "material_refs": [],
  "route_summary": null,
  "provided_tags": [],
  "algorithm_ids": [],
  "model_prediction": {
    "skill_version": null,
    "level": null,
    "reason": null
  },
  "expert_feedback": {
    "level": null,
    "quote": null,
    "comparison": null,
    "source": null
  }
}
```

`case_id` 绑定材料，`feedback_id` 绑定反馈；`material_refs` 持久化时记来源／路径及摘要。`provided_tags` 保留收到内容，`algorithm_ids` 核对实际路线，不复制目录。等级为 1～8，`null/0` 为未知；只有区间不擅填主档。`quote` 原样保留不确定措辞，`comparison` 记比较题及理由，`source` 记实际反馈来源，模型推测不能替换原话。

候选经验：

```json
{
  "id": null,
  "experience": null,
  "algorithm_ids": [],
  "category_scopes": [],
  "sources": [],
  "applies_when": [],
  "limitations": [],
  "counterexamples": [],
  "confirmation": {
    "status": "candidate",
    "reviewer": null,
    "reviewed_on": null
  }
}
```

`sources` 关联 `case_id/feedback_id`；分类用目录层级数组。`experience` 写内容，`applies_when` 写条件，`limitations` 写局限／未查范围，`counterexamples` 仅记实证及来源，未发现不等于不存在。算法 ID／分类只定位，空列表不表示无条件成立。

状态为 `candidate/confirmed/rejected`；确认记实际确认者和 `YYYY-MM-DD`。用户直接给出的经验或明确认可的归纳可成为正式经验，保留来源与适用范围，不按数量或合理感自动确认。

## 更新正式经验

把已明确确认的规则整理入 [expert-rules.json](expert-rules.json)，仅保留通用经验及来源案例标识；题目真实标签、原话和模型错误明细留开发记录，不发行答案表或评分回查。

合并重复经验保留 ID／来源，检查算法 ID、条件、局限和确认状态，必要时缩小范围；用户直接纠正或更新按新反馈记录，模型另作实质扩展须经用户认可。同步 Skill、规范和库的版本号并说明变更依据，不自动写回或生成规则。

`confirmed` 仅表示专家确认，不证明准确率提高；反馈题、比较题及近变体为开发材料，与独立评测隔离。
