# 我的能力自评

不需要姓名、学校或 Rating。按 [行为量表](levels.md) 填 0～5，不确定保留 `unknown`，也可删掉未填字段。以下代码块是唯一机器读取的内容，块外文字用于说明。

- D/P/I/B 分别为发现、证明、实现、调试，可以同时很强或较弱。
- `notes` 可写评分理由，例如 `"D": "能从小例子提炼性质，但陌生建模常需提示"`。
- 分类示例为 `{"category":["图论","最短路问题"],"mastery":3,"note":"主要练过非负权路径"}`，只代表领域概述。
- 算法示例为 `{"algorithm_id":"oiwiki.ds.fenwick","mastery":3}`，用共享目录查询 ID，只填熟悉或明确不会的部分，其他算法未知。
- `strengths`、`limitations` 各填几句即可。
- 可选经历放入 `evidence`，例如 `{"id":"e1","source":"自己的训练记录","conditions":"独立，45 分钟，无题解","observation":"完成一题区间维护，边界调试耗时较长","verification":"reported"}`。自述不是客观测量，实际核验情况单独说明。

```json
{
  "schema_version": 2,
  "profile_type": "individual",
  "self_assessment": {
    "abilities": {
      "D": "unknown",
      "P": "unknown",
      "I": "unknown",
      "B": "unknown"
    },
    "notes": {},
    "knowledge": {
      "categories": [],
      "algorithms": []
    },
    "strengths": [],
    "limitations": []
  },
  "evidence": [],
  "assumptions": []
}
```
