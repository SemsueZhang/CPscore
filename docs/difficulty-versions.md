# Difficulty 版本记录

| 版本 | 入口 | 变化 | 验证状态 |
| --- | --- | --- | --- |
| `cpscore-difficulty-v1`（2026-11-13） | `cp-difficulty-rate` | K/T/I 0～5、总档 0～7、路线锚题、CF/AT 适配 | 保持原文件与历史实验，成绩不代表新版 |
| `cpscore-difficulty-luogu-v2.0.0`（2026-11-14） | `cp-difficulty-luogu` | 洛谷原生 1～8 直接预测，K/T/I 仅分析，人工经验门槛，逐题隔离的基线/Skill 配对协议 | 31 项基础测试通过，正式专家规则 0 条。[87 题开发诊断](../data/difficulty/evaluations/20261114-v2-undistilled-sol-high/Report.md)：GPT-6.1 Sol high 基线 / Skill 命中 68/87 / 65/87，未见增益，非独立测试 |

本次模型测试增加了可选的 `--workers` 单题并发参数，默认仍为 1，不改变评分提示、独立会话或一次评级的协议。并发绑定测试通过，实际每组使用 2 个独立进程。Skill 评分文本及正式专家库在测试中保持冻结。

新版不训练分类器或 Ranker，不引入评审 Agent、多模型投票、三维合成器、标签调参或自动 Skill 修改。CF/AtCoder 工具留在原版中，既有数据和参数未改动。

新增专家规则时记录规则 ID、来源案例、确认人、适用条件和局限，更新 Skill、规范、`common.VERSION` 与正式经验文件的版本。将完整已确认记录手动纳入正式文件，再运行 `experts.py check-release` 和基础测试。冻结版本、提示与材料后运行独立配对实验，另记指标和限制。人工审核通过与评测发现增益是两个状态。
