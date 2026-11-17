# 使用说明

按审核对象选择 Skill，提供同一版本的完整材料。各 Skill 独立安装，默认在对话中输出 Markdown；要求保存时才写文件。安装操作见[安装说明](../install.md)。

| 任务 | 说明 |
| --- | --- |
| 题面规格、样例、阅读与按需格式 | [cp-statement-review](cp-statement-review.md) |
| 题解推导、覆盖、教学与按需格式 | [cp-editorial-review](cp-editorial-review.md) |
| std 实现、资源与表达 | [cp-solution-review](cp-solution-review.md) |
| 原测试集、判定器与错解漏检 | [cp-data-review](cp-data-review.md) |
| 考点原创性与设计质量 | [cp-quality-review](cp-quality-review.md) |
| 洛谷八档难度 | [cp-difficulty-luogu](cp-difficulty-luogu.md) |
| 整套赛题组合与体验 | [cp-contest-review](cp-contest-review.md) |
| 多维选手画像、路线与表现差异 | [cp-performance-predict](cp-performance-predict.md) |

材料分、质量等级、题目难度和选手水平回答不同问题，不能直接互换。具体标准以各 Skill 自带 Reference 为准；实测、静态核验、预测和未完成范围分别说明。

需要统一算法知识名称、别名与 ID 时，八个 Skill 按需查询同一份[共享算法知识目录](algorithm-catalog.md)，无需整份加载。共享目录还统一洛谷标签、算法知识参考区间和有限标签样本，区分参考索引与网站ID，不提供题解或选手能力测量，不能由标签直接推出整题难度。

题面与题解默认分任务审核正确性与阅读质量，通过对象级记录检查覆盖、定向补查。用户明确要求时启用格式审核。两套技能各自随包提供覆盖检查工具、相同的文风与格式协议及格式 Linter，均可独立安装。无 Python 时按协议核验可取得的材料，执行失败标明未完成范围。

[示例目录](../examples/README.md) · [返回首页](../README.md)
