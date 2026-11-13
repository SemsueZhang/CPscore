# CPScore：算法竞赛题目评价 Skills

CPScore 为算法竞赛出题、验题和组卷提供 9 个独立技能，覆盖材料审核、新颖度、难度评定、单题与整套设计、选手表现预测。把题面、题解、标程或数据交给本地智能体，即可收到包含依据与修改建议的 Markdown 报告。默认在对话中返回，要求保存时才写文件。

## 技能清单

| Skill | 用途 | 结果 |
| --- | --- | --- |
| [cp-statement-review](skills/cp-statement-review/SKILL.md) | 规格、边界、样例、格式与易读性 | 10分制评分及修改建议 |
| [cp-solution-review](skills/cp-solution-review/SKILL.md) | std 正确性、复杂度、表达及与给定题解的对应 | 10分制评分及修改建议 |
| [cp-editorial-review](skills/cp-editorial-review/SKILL.md) | 关键思想、证明、复杂度、讲解与格式 | 10分制评分及修改建议 |
| [cp-data-review](skills/cp-data-review/SKILL.md) | 数据合法性、错解漏网、子任务得分 | 10分制评分及补点建议 |
| [cp-novelty-review](skills/cp-novelty-review/SKILL.md) | 相似题、论文、独立考点和推导质量 | A/B/C/C+/D/F |
| [cp-difficulty-rate](skills/cp-difficulty-rate/SKILL.md) | 知识、思维、实现与整题难度，适配洛谷、CF、AT | 三维各 0～5，总档 0～7 及平台参照 |
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

难度评定示例：`$cp-difficulty-rate 评定 statement.md，结合 editorial.md 和 std.cpp，给出 CF、AT 参照。`

需要文件时追加“将审核保存为 review.md”。其他用途替换技能名和材料即可，题目总评可直接审核原始材料或复用已有评审。

Codex、Claude Code、OpenCode、DeepSeek Harness 的安装位置与调用方式，以及批量安装、Windows、更新和卸载，见[安装说明](install.md)。已有同名技能时先保存自定义修改，再按更新步骤替换。

## 结果说明

- **材料评分**：从10分起，Fatal −10、Major −2、Minor −1，允许负分。同一根因只扣一次，疑点不扣分。9～10分为优秀，6～8分为尚可，5分及以下为不合格。关键核验未完成时注明缺口，暂定6～10分的档次待定。
- **新颖度**：独立使用A/B/C/C+/D/F，C+与F质量标准相同，区别在先例关系。
- **题目总评**：推荐、合格、不合格，按单题协议汇总材料和设计判断。
- **比赛总评**：默认依据赛前材料预测区分度、做题体验与整体质量，按逐题占比及整体否决条件判定。仅明确要求复盘时使用本场实际成绩，详见[比赛总评协议](skills/cp-contest-review/references/assessment.md)。
- **难度评定**：K/T/I 各用 0～5 六档，总难度 0～7 依次对应洛谷的入门、普及-、普及、普及+/提高-、提高、提高+/省选-、省选/NOI-、NOI/NOI+/CTS。总档按完整路线与锚题判断，CF 和 AtCoder Problems 分别提供有版本的粗略参照，不是材料的 10 分制评分或选手水平。
- **表现预测**：给出路线、时间和得分区间，不作质量评级或实测成绩。

题面审核先独立重建规格，再主动核验疑点，最后交叉核对材料并提出最小修订。[规格核验](skills/cp-statement-review/references/specification.md)直接规定任务定义、输入输出、范围、部分分、多语言及时空裕量要求，[阅读和修订](skills/cp-statement-review/references/readability.md)直接规定标点、间距、公式及展示要求。分级、去重及未完成状态统一见[评分协议](skills/cp-statement-review/references/scoring.md)。

题解审核在[论证与表达核验](skills/cp-editorial-review/references/verification.md)中直接规定正文完整性、证明、复杂度、Markdown、数学记号、代码、图片和来源要求。[评分协议](skills/cp-editorial-review/references/scoring.md)列出格式与内容问题的扣分规则。明确格式违规至少为 Major −2，严重的可为 Fatal −10，证明缺漏与算法错误分别判断，建议项及合理例外不直接扣分。

数据审核按[数据评分协议](skills/cp-data-review/references/scoring.md)先确认候选错误与原集实际漏检，再以额外成绩、正式计分权重及对区分度、判定可靠性的影响为主，结合错误机制定级。具有评审意义的满分漏检是 Fatal 的强信号，理论上很错误的算法仅获有限额外收益时不直接判 Fatal。正常部分分不扣分，外加反例不并入原集成绩。

题目总评的[材料分项协议](skills/cp-problem-review/references/materials.md)也直接规定题面、题解和排版要求，独立安装即可审核。这些要求已纳入 CPScore 自身协议，制定时参考洛谷题目及题解规范。

std 审核兼顾实现与题解对应。具体分级见各技能的 `references/`。读取、检索和执行使用宿主已有能力，实测结论须有真实结果，有限测试不替代证明。

各技能独立安装，入口只负责范围、流程、Reference 加载和交付。核验方法与评分或汇总规则分开维护，不依赖跨技能共享文件；表现预测的[1～7 档水平参考](skills/cp-performance-predict/references/levels.md)随技能提供，用户画像 RAG 预留于本地项目的 `contestant_profiles/`，当前尚未填充。题面小案例、推演结果与验证边界见[方法验收材料](examples/statement-review-cases/README.md)。

难度评定从 Auto-Insight 迁入为独立技能，沿用三维定义并按用户要求采用洛谷八档总刻度。[评分规范](skills/cp-difficulty-rate/references/rubric.md)给出路线、逐维标准与锚题，[平台适配](skills/cp-difficulty-rate/references/platforms.md)提供原生字段、换算表、冻结数据和留出表现。原六档合成器未胜过基线，当前总档没有冒称训练模型预测；新换算表只验证原生标签之间的对应。总评可复用与材料版本匹配的难度报告。

新颖度检索附带可选的 Python 3.8+ 标准库辅助脚本，用于候选索引、原文缓存和分段读取。技能先检测已有解释器，不可用时回退到宿主工具，无需安装依赖，详见[检索说明](skills/cp-novelty-review/references/retrieval.md)。

题面审核的[真实调用评测](tests/statement/README.md)分别保存新旧 Skill 对照与[CPScore 对比直接审题](tests/statement/results/harness-vs-direct/README.md)。后者在同一 Codex 宿主及模型上观察到少量稳定性和修复保持性收益，已确认非格式根因检出率相同，输入 token 约为直接组的 1.54 倍。这是合成题面上的有限结果，未经人类专家确认，不代表其他技能或最新工作区版本的效果。

## 项目目录

```text
CPscore/
├── .github/               # CI、安装复制与检索辅助检查
├── examples/              # 审核案例、解法与核验代码
├── install.md             # 多宿主安装说明
├── tests/statement/       # 题面评测、真实调用存档与离线审计
└── skills/<skill>/
    ├── SKILL.md           # 技能说明、核心流程与交付要求
    ├── references/        # 详细协议，按入口指引读取
    ├── retrieve.py        # 新颖度技能的可选检索工具
    └── scripts/           # 难度技能的可选换算与离线拟合工具
```

## 示例

| 项目 | 链接 | 摘要 |
| --- | --- | --- |
| 题解审核 | [货币系统](examples/editorial-review.md) | 数学证明缺漏的编写示例，演示评分8/10，未演示新版协议全项核验。 |
| 题解审核实例 | [CCPC 2026 长春 L：故事](examples/editorial-review-story.md) | 缺少达到最少剩余 1 时保留端点的判定，旧版数学审核评分8/10，未按新版规范复审。 |
| std 审核示例 | [CSP-S 2026 迁徙](examples/solution-review.md) | 人工变体含 Fatal、Major、Minor 各一项，评分−3/10，附题解与实际反例。 |
| 比赛评价实例 | [ICPC 2026 西安区域赛](examples/contest-review-xian-2026.md) | 整套合格，中段区分度有风险，附[解法推导](examples/contest-review-xian-2026-solutions.md)与[核验方法](examples/contest-review-xian-2026/README.md)。这是已暴露赛后结果的材料回放。 |
| 新颖度与质量评审实例 | [CSP-S 2026 全卷](examples/novelty-review-csps2026.md) | 四题评级 A / B / F / C+，附先例比较、整套设计与检索范围。 |
| 数据审核实例 | [CSP-S 2026 地铁](examples/data-review-subway.md) | 原集25点实测，按漏检影响复评为−20/10（2 Fatal、4 Major、2 Minor），保留8项独立缺陷的实测与复现方法。 |

## 许可证

本项目采用 [MIT License](LICENSE)。
