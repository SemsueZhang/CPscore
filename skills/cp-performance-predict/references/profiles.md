# 画像填写与使用

一人一份，可自然语言或复制 [Markdown](profile-template.md)／[JSON](profile-template.json) 模板，字段可删，不需身份／学校／Rating；只在要求时保存，不主动收集经历。

## 格式与来源

当前 `schema_version` 为 `2`。顶层可含 `id`（可匿名）、`label`、`profile_type`（`individual` 或 `reference`）、`scope`、`self_assessment`、`evidence`、`assumptions`。字段可以省略，未知标量用 `unknown` 或 `null`。拼错字段会被辅助脚本拒绝，避免悄悄忽略能力信息。

`self_assessment` 包含：

- `abilities`：D/P/I/B，使用[行为量表](levels.md)。`notes` 用对应字母记录评分理由，不要求每项都有说明。
- `knowledge.categories`：`category` 是目录中的分类路径数组，`mastery` 为 0～5 或未知，`note` 写覆盖范围。只是领域自述，不代表所有子项。
- `knowledge.algorithms`：`algorithm_id` 引用唯一共享目录，`mastery` 记录具体掌握程度，可附 `note` 和 `evidence_ids`。无需填写完整目录。
- `strengths`、`limitations`：简短字符串数组。

`evidence` 用 `id/source/conditions/observation`，可附 `date/verification`。`reported` 默认表示自述，`linked` 仅有链接，`reproduced` 须有复现材料，不由脚本授予；独立限时、题解后复现和团队经历分开。无证据可提交，证据不自动覆盖自评／换算分数，冲突并列。

`assumptions` 保存预测所用但未经验证的条件。赛制、时长、语言、模板、反馈等本次环境放在题目分析的 `environment`，不新增赛制能力轴。

## 引用共享算法知识

唯一目录是 `CPSCORE_CATALOG` 指向的目录或 `catalog.json`，仓库内默认 `resources/algorithm-catalog/catalog.json`。例如：

```sh
python3 resources/algorithm-catalog/catalog.py search '树状数组'
python3 skills/cp-performance-predict/scripts/predict.py validate player.md
```

算法例 `{"algorithm_id":"oiwiki.ds.fenwick","mastery":3}`，名称、别名、说明不复制，分类路径查同一目录。缺目录则脚本失败；无 Python 可核同一 JSON，未核 ID 标未验证，不声称机器校验通过。

模板示例未知，不代表掌握，空列表不代表全不会。Markdown 仅唯一 `json` 块机器读取，块外只说明；自然语言／YAML 可由宿主整理并标注假设，脚本无 YAML 依赖。

## 知识难度参考

`python3 skills/cp-performance-predict/scripts/predict.py knowledge --profiles player.md` 查已填算法的同目录映射、参考和样本，省略参数则覆盖 16 锚点的 41 个显式 ID；不改画像或换算熟练度／D/P/I/B。知识索引 0～7、网站难度 ID 1～8、掌握度 0～5 分开。

`knowledge_level.confidence=reference` 表示有已核实题例和说明支撑的学习参考，仍含主观区间；`provisional`待专项校准，`unknown`不提供数值。`problem_difficulty`只表示缓存标签样本的分布，未必对应最优解所需方法，更不是选手评分。

## 16 个参考锚点

[reference-profiles.json](reference-profiles.json) 恰好 16 个假设锚点，字段同个人画像；`self_assessment` 是人为设定，不是实测、训练或统计样本，不是互斥等级，也不匹配真实选手。个人画像直接使用。

具体 ID、数值、知识与设定以该 JSON 为唯一来源。结构检查报告知识覆盖、轴范围、同分异知识／同知识异能力并拒绝重复记录；不证明统计代表性。保留 p05/p09、p07/p08、p10/p11、p14/p15 的对照用途，锚点组合须合理，不靠极端组合凑数；未填算法均未知。

旧 `schema_version: 1` 不静默迁移。先将文字放入 `notes`、经历放入 `evidence`，由选手或使用者重新确认各轴与算法掌握程度，不能从旧总体档位填满新画像。
