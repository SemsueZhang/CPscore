# 选手能力画像与表现预测

先对题目与完整正确解法作一次系统分析，再判断不同知识、发现、推导与证明、实现和调试能力会怎样影响解题过程，最终提炼少量有依据的差异。题目自身的难度仍由 `cp-difficulty-luogu` 独立评价。

```text
$cp-performance-predict 根据 statement.md 与 editorial.md 分析完整路线，用16份参考画像识别真正影响表现的能力条件，合并相近结论。
```

## 参考画像与个人自评

随包提供[恰好16个假设性参考锚点](../skills/cp-performance-predict/references/reference-profiles.json)，覆盖基础到顶端，以及同能力异知识、同知识异实现或调试、推导强于工程等组合。具体设定与适用范围以该 JSON 为准，[画像说明](../skills/cp-performance-predict/references/profiles.md)解释使用规则。它们不是16个互斥类别，也没有真实选手统计依据。

真实选手可复制[Markdown 自评模板](../skills/cp-performance-predict/references/profile-template.md)或 [JSON 模板](../skills/cp-performance-predict/references/profile-template.json)，只填了解的部分。通用能力 D/P/I/B 使用[0～5行为量表](../skills/cp-performance-predict/references/levels.md)，允许未知。K 通过唯一共享 [Algorithm Catalog](algorithm-catalog.md) 的分类和具体算法 ID 表达，不压缩成总分。

共享目录同时提供洛谷标签映射、算法知识门槛和有限题目样本。可用 `predict.py knowledge --profiles player.md` 按画像已填ID查询，省略画像时汇总16锚点的41个ID。难度参考索引0～7与熟练度0～5不同，不会自动修改K/D/P/I/B，样本也不代表算法必须使用或全站分布。

无需姓名、学校或平台 Rating，不要求填写全部算法，不归类到参考锚点。分类自述不自动覆盖其全部子算法，未填内容仍未知。自评与经历证据分开保存，未核实自述不是客观测量。自然语言同样可用，整理成结构化画像时需保留未知与假设。

```text
$cp-performance-predict 用 player.md 的个人画像，结合 statement.md 和 editorial.md，预测在90分钟、C++17、无现成模板下的路线、卡点与可达进展。
```

旧版 `schema_version: 1` 的总体档位、合并的实现与调试文字不能自动换算新分数，需要重新确认。新格式为版本2。

## 预测与合并

[预测协议](../skills/cp-performance-predict/references/prediction.md)保留每条完整路线的前提、关键发现、推导依赖、证明、实现与调试要求，不拼接不同解法的最低门槛，不使用 K/D/P/I/B 加权总分。推导任务按具体障碍分析 D/P，画像字段与既有分值不因题目难度增加 R 轴而改变。陌生知识可以有具体的独立重建可能，熟悉知识也不能代替题目转化的发现。

内部可比较全部参考锚点，但最终按结果、主要瓶颈与路线提炼。相同结论可合并，同结果的重要异因仍保留。数量由题目决定，没有差异就只给一条。报告同时列明环境、依据、未知条件和最可能改变判断的能力要求。部分分只依据真实子任务和评分方式。

辅助脚本只需 Python 3.8+ 标准库，不调用模型 API。由人或宿主 LLM 先提供分析 JSON，再运行：

```sh
python3 skills/cp-performance-predict/scripts/predict.py audit
python3 skills/cp-performance-predict/scripts/predict.py validate player.md
python3 skills/cp-performance-predict/scripts/predict.py predict analysis.json --profiles player.md
```

省略 `--profiles` 时使用16个锚点，默认输出保守合并初稿，再按协议做语义提炼。`--details` 才输出内部逐画像记录及单维敏感性诊断。后者检查分数变化是否触及具体任务，不是因果实验。独立安装时用 `CPSCORE_CATALOG` 指向同一公共目录，或把 `--catalog /path/to/catalog.json` 放在子命令前。依赖缺失明确报错，不另建目录。

没有 Python 时，宿主仍可按同一协议人工核对和预测，不能声称机器校验通过。没有完整解法时应先说明分析不足，不强行判定画像能否完成。

## 验证边界

结构校验覆盖画像格式、算法 ID 与参考锚点，预测结果依赖分析者给出的完整路线与门槛。画像推断不得冒充实际解题、编码或测试记录，没有校准不输出成功率百分比。需要耗时或整场排程时按具体负担给粗略范围，未知则不填数字。赛前不使用本场结果反推，结果已暴露的分析标为材料回放。

[技能入口](../skills/cp-performance-predict/SKILL.md) · [返回目录](README.md)
