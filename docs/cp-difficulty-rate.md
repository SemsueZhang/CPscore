# 题目难度评定

`cp-difficulty-rate` 根据完整可通过路线评定知识、思维、实现与整题难度，并给出洛谷、Codeforces 和 AtCoder Problems 的尺度参照。

当前三维标准、八档锚题、完整平台换算表及验证范围见[难度评价现状总结](difficulty-assessment-summary.md)。

## 材料与调用

提供题面、约束、完整解法和必要实现，说明语言、模板、团队或工具条件。默认评估未见本题及直接先例、允许常用模板的个人选手。缺少全数据路线时只给已有部分的初评及具体缺口。

```text
$cp-difficulty-rate 评定 statement.md，结合 editorial.md 和 std.cpp，给出三维、总档及 CF、AT 参照。
```

## 三维与总档

| 维度 | 评价内容 | 刻度 |
| --- | --- | --- |
| K，知识门槛 | 独立解题前必须掌握的知识和理解深度 | 0～5 |
| T，思维难度 | 从题面发现并证明完整解法的困难 | 0～5 |
| I，实现难度 | 已知算法和不变量后，正确实现与调试的困难 | 0～5 |

三维对应完整的同一条路线，总档结合整条路线与锚题比较形成，不用最大值、均值或固定权重直接合成。多条可通过路线分别评定，以总难度最低的实际可行路线为主评，不跨路线拼接最低三维。

| 总档 | 洛谷参照 |
| --- | --- |
| 0 | 入门 |
| 1 | 普及- |
| 2 | 普及 |
| 3 | 普及+/提高- |
| 4 | 提高 |
| 5 | 提高+/省选- |
| 6 | 省选/NOI- |
| 7 | NOI/NOI+/CTS |

总档 0～7 与三维 0～5 是不同刻度。洛谷“暂无评定”保留为未知。CF 采用题目 rating，AtCoder Problems 采用社区模型的 difficulty，均与选手 rating、题目分值分别处理。平台换算是有版本的粗略参照，不是官方跨站标准或统计置信区间。

## 适配结果与边界

技能从 Auto-Insight 迁入，沿用三维定义，采用洛谷八档总刻度。原六档学习合成器未胜过基线，当前总档由规范、锚题与路线评定，未声称是经过验证的训练模型预测。

冻结同题快照用于原生难度标签到洛谷档次的转换。两站留出表现如下：

| 来源 | 留出题数 | 总档平均绝对误差 | 完全命中 | 相差至多一档 |
| --- | ---: | ---: | ---: | ---: |
| CF | 40 | 0.600 | 20/40 | 36/40 |
| AtCoder Problems | 40 | 0.350 | 27/40 | 39/40 |

该结果只验证标签转换，不验证题面到 K/T/I、三维到总档或整个 Skill 的评级准确率。分层选题与来源列表存在取样偏差，完整拆分、冻结数据和逐题结果见[平台适配](../skills/cp-difficulty-rate/references/platforms.md)。

## 数字工具与规范

已有 Python 3.8+ 时可使用标准库工具，例如在仓库根目录运行：

```sh
python3 skills/cp-difficulty-rate/scripts/platforms.py --level 4
python3 skills/cp-difficulty-rate/scripts/platforms.py --cf 2200
```

工具转换传入数字，不自行分析题目或查询原生标签。没有 Python 时可直接按表评定。

[技能入口](../skills/cp-difficulty-rate/SKILL.md) · [评分规范与锚题](../skills/cp-difficulty-rate/references/rubric.md) · [适配数据](../skills/cp-difficulty-rate/references/platform-anchors.json) · [适配参数](../skills/cp-difficulty-rate/references/platform-calibration.json)

[返回说明目录](README.md)
