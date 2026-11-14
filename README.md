# CPScore：算法竞赛题目评价 Skills

> 给算法竞赛题做一次有依据的评审，把问题、理由和修改建议说清楚。

CPScore 为算法竞赛出题、验题和组卷提供 8 个独立技能，覆盖材料审核、题目质量评分、难度评定、比赛设计和选手表现预测。把题面、题解、标程或数据交给本地智能体，即可收到包含依据与修改建议的 Markdown 报告。默认在对话中返回，要求保存时才写文件。

各技能可按需安装到 Codex、Claude Code、OpenCode 或 DeepSeek Harness，使用宿主已有的文件读取、检索和代码执行能力。

## 能做什么

| Skill 与使用说明 | 用途 | 交付 |
| --- | --- | --- |
| [cp-statement-review](docs/cp-statement-review.md) | 检查题面规则、样例、格式与阅读障碍 | 评分、依据与局部修订 |
| [cp-editorial-review](docs/cp-editorial-review.md) | 检查声明、全题覆盖、复杂度与讲解 | 评分、缺口定位与修改方向 |
| [cp-solution-review](docs/cp-solution-review.md) | 对照题解审核 std 的正确性与实现表达 | 评分、反例与修正建议 |
| [cp-data-review](docs/cp-data-review.md) | 核验数据、判定与错解的实际漏网收益 | 评分与补点建议 |
| [cp-quality-review](docs/cp-quality-review.md) | 依据人类题解，评价考点原创性与算法设计质量 | A+ / A / B+ / B / C / D / F / S 及用途建议 |
| [cp-difficulty-luogu](docs/cp-difficulty-luogu.md) | 根据完整解法预测洛谷八档难度 | 原生 1～8 档及主要依据 |
| [cp-contest-review](docs/cp-contest-review.md) | 分析整套区分度、做题体验与质量 | 推荐 / 合格 / 不合格 |
| [cp-performance-predict](docs/cp-performance-predict.md) | 按选手背景预测解题过程 | 路线、时间与得分区间 |

## 快速开始

以 Codex 为例，在 macOS、Linux 或 Git Bash 中安装题解审核技能：

```sh
git clone https://github.com/SemsueZhang/CPscore.git
cd CPscore
mkdir -p "$HOME/.agents/skills"
cp -R skills/cp-editorial-review "$HOME/.agents/skills/"
```

安装后新建宿主会话，在题目项目中调用：

```text
$cp-editorial-review 审核 editorial.md，结合 statement.md。
```

需要文件时追加“将审核保存为 review.md”。其他用途替换技能名和材料即可。

Codex、Claude Code、OpenCode、DeepSeek Harness 的安装位置与调用方式，以及批量安装、Windows、更新和卸载，见[安装说明](install.md)。已有同名技能时先保存自定义修改，再按更新步骤替换。

## 示例

| 方向 | 示例 | 内容 |
| --- | --- | --- |
| 题面审核 | [方法小案例](examples/statement-review-cases/README.md) | 通过合成题面展示规则歧义、样例核验、阅读障碍与局部修订。 |
| 题解审核 | [《货币系统》](examples/editorial-review.md)、[长春 L《故事》](examples/editorial-review-story.md) | 关键证明缺漏、补证与修改建议，保留原版审核评分。 |
| 标程审核 | [CSP-S 2026《迁徙》](examples/solution-review.md) | 人工变体中的正确性与说明缺陷，附实际反例。 |
| 数据审核 | [CSP-S 2026《地铁》](examples/data-review-subway.md) | 原集漏检、错解额外得分、分级与补点建议，附复现代码。 |
| 比赛总评 | [ICPC 2026 西安区域赛](examples/contest-review-xian-2026.md) | 已暴露赛后结果的材料回放，分析解题路线、梯度与做题体验。 |
| 历史新颖度审核 | [CSP-S 2026 全卷](examples/novelty-review-csps2026.md) | 旧协议下的先例与设计比较，尚未按现行八档质量标准复评。 |

## 文档与项目结构

每个技能的用途、材料要求、结果解读、案例和已有验证见 [Skill 使用说明](docs/README.md)。详细判据由各技能自带的 `references/` 维护，安装时复制完整技能目录即可。

难度模块当前为 `cpscore-difficulty-luogu-v2.0.0`：一个前沿 LLM、简洁 Skill、人工确认的专家经验和独立评测。原 `cp-difficulty-rate` 保留为历史版本及 CF/AT 数字工具，不参与新评分流程。专家资料与历史评测见 [Difficulty 数据说明](data/difficulty/README.md)。[未蒸馏版 87 题开发诊断](data/difficulty/evaluations/20261114-v2-undistilled-sol-high/Report.md)中，GPT-6.1 Sol high 的纯 LLM / Skill 命中为 68/87 / 65/87，本轮未观察到 Skill 增益，不作为独立测试成绩。

```text
CPscore/
├── skills/                # 8 个当前技能及 1 个保留的历史难度技能
├── docs/                  # 每个技能的使用说明与结果分析
├── data/difficulty/       # 专家反馈、开发隔离登记及历史结果
├── examples/              # 审核案例、解法与核验代码
└── install.md             # 多宿主安装、更新与卸载
```

数据协议和历史结果摘要随仓库保存。`test/`、`tests/` 及依赖它们的测试工作流仅在本地保留，不随仓库提交。历史题目正文和完整模型轨迹仍在原 LuoguBench 工程中。

## 许可证

本项目采用 [MIT License](LICENSE)。
