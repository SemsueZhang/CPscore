# 使用说明

按审核对象选择 Skill，提供同一版本的完整材料。各 Skill 独立安装，默认在对话中输出 Markdown；要求保存时才写文件。安装操作见[安装说明](../install.md)。

| 任务 | 说明 |
| --- | --- |
| 题面规格、样例、阅读与格式 | [cp-statement-review](cp-statement-review.md) |
| 题解推导、覆盖、教学与格式 | [cp-editorial-review](cp-editorial-review.md) |
| std 实现、资源与表达 | [cp-solution-review](cp-solution-review.md) |
| 原测试集、判定器与错解漏检 | [cp-data-review](cp-data-review.md) |
| 考点原创性与设计质量 | [cp-quality-review](cp-quality-review.md) |
| 洛谷八档难度 | [cp-difficulty-luogu](cp-difficulty-luogu.md) |
| 整套赛题组合与体验 | [cp-contest-review](cp-contest-review.md) |
| 指定选手的路线、耗时与得分 | [cp-performance-predict](cp-performance-predict.md) |

材料分、质量等级、题目难度和选手水平回答不同问题，不能直接互换。具体标准以各 Skill 自带 Reference 为准；实测、静态核验、预测和未完成范围分别说明。

题面与题解分别随包提供相同的格式协议和 Linter，均可独立运行。没有 Python 时，宿主 LLM 仍按同一协议核验可取得的材料，不把工具故障当成稿件错误。

[示例目录](../examples/README.md) · [返回首页](../README.md)
