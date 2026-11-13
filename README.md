# CPScore：算法竞赛题目评价 Skills

CPScore 为算法竞赛出题、验题和组卷提供 8 个独立技能，覆盖材料审核、新颖度、单题与整套设计、选手表现预测。把题面、题解、标程或数据交给本地智能体，即可收到包含依据与修改建议的 Markdown 报告。默认在对话中返回，要求保存时才写文件。

## 技能清单

| Skill | 用途 | 结果 |
| --- | --- | --- |
| [cp-statement-review](skills/cp-statement-review/SKILL.md) | 规格、边界、样例、洛谷规范与易读性 | 10分制评分及修改建议 |
| [cp-solution-review](skills/cp-solution-review/SKILL.md) | std 正确性、复杂度、表达及与给定题解的对应 | 10分制评分及修改建议 |
| [cp-editorial-review](skills/cp-editorial-review/SKILL.md) | 关键思想、证明、复杂度、讲解与洛谷题解规范 | 10分制评分及修改建议 |
| [cp-data-review](skills/cp-data-review/SKILL.md) | 数据合法性、错解漏网、子任务得分 | 10分制评分及补点建议 |
| [cp-novelty-review](skills/cp-novelty-review/SKILL.md) | 相似题、论文、独立考点和推导质量 | A/B/C/C+/D/F |
| [cp-problem-review](skills/cp-problem-review/SKILL.md) | 单题材料、解法空间与整体设计 | 推荐 / 合格 / 不合格 |
| [cp-contest-review](skills/cp-contest-review/SKILL.md) | 赛前预测整套区分度、做题体验和整体质量 | 推荐 / 合格 / 不合格 |
| [cp-performance-predict](skills/cp-performance-predict/SKILL.md) | 预测选手路线、障碍、时间和得分 | 预测分析，不作质量评级 |

## 安装与调用

下载或克隆仓库后，复制所需技能的完整目录。例如在 macOS、Linux 或 Git Bash 中全局安装 Codex 技能：

```sh
mkdir -p "$HOME/.agents/skills"
cp -R skills/cp-editorial-review "$HOME/.agents/skills/"
```

安装后新建宿主会话，在题目项目中调用：

```text
$cp-editorial-review 审核 editorial.md，结合 statement.md。
```

需要文件时追加“将审核保存为 review.md”。其他用途替换技能名和材料即可，题目总评可直接审核原始材料或复用已有评审。

Codex、Claude Code、OpenCode、DeepSeek Harness 的安装位置与调用方式，以及批量安装、Windows、更新和卸载，见[安装说明](install.md)。已有同名技能时先保存自定义修改，再按更新步骤替换。

## 结果说明

- **材料评分**：从10分起，Fatal −10、Major −2、Minor −1，允许负分。同一根因只扣一次，疑点不扣分。9～10分为优秀，6～8分为尚可，5分及以下为不合格。关键核验未完成时注明缺口，暂定6～10分的档次待定。
- **新颖度**：独立使用A/B/C/C+/D/F，C+与F质量标准相同，区别在先例关系。
- **题目总评**：推荐、合格、不合格，按单题协议汇总材料和设计判断。
- **比赛总评**：默认依据赛前材料预测区分度、做题体验与整体质量，按逐题占比及整体否决条件判定。仅明确要求复盘时使用本场实际成绩，详见[比赛总评协议](skills/cp-contest-review/references/assessment.md)。
- **表现预测**：给出路线、时间和得分区间，不作质量评级或实测成绩。

题面审核先独立重建规格，再主动核验疑点，最后交叉核对材料并提出最小修订。方法分别维护在[规格核验](skills/cp-statement-review/references/specification.md)与[阅读和修订](skills/cp-statement-review/references/readability.md)，包括适用的洛谷规范；分级、去重及未完成状态统一见[评分协议](skills/cp-statement-review/references/scoring.md)。

题解审核参照[洛谷主题库题解规范](https://help.luogu.com.cn/rules/academic/solution-standard)，兼顾正确性、讲解、Markdown、公式、代码及引用，按投稿场景核对图片托管和 GenAI 等来源要求。明确格式违规至少为 Major −2，严重的可为 Fatal −10，详见[题解规范核对表](skills/cp-editorial-review/references/luogu-standard.md)和[评分协议](skills/cp-editorial-review/references/scoring.md)。证明缺漏与算法错误分别判断，建议项及合理例外不直接扣分。

std 审核兼顾实现与题解对应。具体分级见各技能的 `references/`。读取、检索和执行使用宿主已有能力，实测结论须有真实结果，有限测试不替代证明。

各技能独立安装，入口只负责范围、流程、Reference 加载和交付。核验方法与评分或汇总规则分开维护，不依赖跨技能共享文件；表现预测足够简短，保留单文件。题面小案例、推演结果与验证边界见[方法验收材料](examples/statement-review-cases/README.md)。

新颖度检索附带可选的 Python 3.8+ 标准库辅助脚本，用于候选索引、原文缓存和分段读取。技能先检测已有解释器，不可用时回退到宿主工具，无需安装依赖，详见[检索说明](skills/cp-novelty-review/references/retrieval.md)。

## 项目目录

```text
CPscore/
├── .github/               # CI、安装复制与检索辅助检查
├── examples/              # 审核案例、解法与核验代码
├── install.md             # 多宿主安装说明
└── skills/<skill>/
    ├── SKILL.md           # 技能说明、核心流程与交付要求
    ├── references/        # 详细协议，按入口指引读取
    └── retrieve.py        # 仅新颖度技能附带的可选检索工具
```

## 示例

| 项目 | 链接 | 摘要 |
| --- | --- | --- |
| 题解审核 | [货币系统](examples/editorial-review.md) | 数学证明缺漏的编写示例，演示评分8/10，未演示新版洛谷规范全项核验。 |
| 题解审核实例 | [CCPC 2026 长春 L：故事](examples/editorial-review-story.md) | 缺少达到最少剩余 1 时保留端点的判定，旧版数学审核评分8/10，未按新版规范复审。 |
| std 审核示例 | [CSP-S 2026 迁徙](examples/solution-review.md) | 人工变体含 Fatal、Major、Minor 各一项，评分−3/10，附题解与实际反例。 |
| 比赛评价实例 | [ICPC 2026 西安区域赛](examples/contest-review-xian-2026.md) | 整套合格，中段区分度有风险，附[解法推导](examples/contest-review-xian-2026-solutions.md)与[核验方法](examples/contest-review-xian-2026/README.md)。这是已暴露赛后结果的材料回放。 |
| 新颖度与质量评审实例 | [CSP-S 2026 全卷](examples/novelty-review-csps2026.md) | 四题评级 A / B / F / C+，附先例比较、整套设计与检索范围。 |
| 数据审核实例 | [CSP-S 2026 地铁](examples/data-review-subway.md) | 原集25点实测，评分−10/10，含8项独立缺陷及复现方法。 |

## 许可证

本项目采用 [MIT License](LICENSE)。
