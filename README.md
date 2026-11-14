# CPScore 1.0

CPScore 是一套供强推理 LLM 调用的算法竞赛审题 Skills，覆盖题面、题解、标程、数据、题目质量、难度及整场比赛。每个 Skill 自带执行流程和专业 Reference，可以独立安装。

## 八个 Skills

| Skill | 功能 |
| --- | --- |
| [cp-statement-review](docs/cp-statement-review.md) | 核验任务规格、样例、阅读体验与格式，给出材料评分。 |
| [cp-editorial-review](docs/cp-editorial-review.md) | 核验声明、推导、全题覆盖、教学表达与格式，静态对照代码。 |
| [cp-solution-review](docs/cp-solution-review.md) | 对照题解审核 std 的正确性、资源开销与实现表达。 |
| [cp-data-review](docs/cp-data-review.md) | 证实错解并核实原集漏检，评价实际计分影响。 |
| [cp-quality-review](docs/cp-quality-review.md) | 依据人类题解检索先例，评价考点原创性与设计质量。 |
| [cp-difficulty-luogu](docs/cp-difficulty-luogu.md) | 根据题面和完整正确解法，预测洛谷原生 1～8 档难度。 |
| [cp-contest-review](docs/cp-contest-review.md) | 赛前分析整套题的区分度、做题体验与组合质量。 |
| [cp-performance-predict](docs/cp-performance-predict.md) | 依据选手背景与赛制，预测解题路线、耗时和得分。 |

## 安装与调用

下载仓库 ZIP，或克隆后复制所需 Skill 的整个目录。以 Codex 全局安装为例：

```sh
git clone https://github.com/SemsueZhang/CPscore.git
cd CPscore
mkdir -p "$HOME/.agents/skills"
cp -R skills/cp-editorial-review "$HOME/.agents/skills/"
```

在宿主会话中提供材料并调用：

```text
$cp-editorial-review 结合 statement.md 审核 editorial.md，给出评分、证据和修改建议。
```

默认在对话中交付 Markdown 报告，要求保存时才写文件。各 Skill 使用宿主已有工具；随包 Python 脚本仅作可选辅助，要求 Python 3.8+ 标准库，无需额外依赖。没有 Python 时仍可由宿主 LLM 按 Reference 完成可核验的审核，并说明未完成范围。

[安装、更新与卸载](install.md)说明 Codex、Claude Code、OpenCode 和 DeepSeek Harness 的安装位置与调用方式。[使用文档](docs/README.md)说明各项材料、输出和边界；[示例](examples/README.md)演示语义判断与标程评分。

## 仓库结构

```text
CPscore/
├── README.md
├── LICENSE
├── install.md
├── skills/       # 八个独立 Skill，含 references/ 和必要的 scripts/
├── docs/         # 用户说明
└── examples/     # 少量自包含示例
```

本仓库仅发行正式 Skills，不包含 Benchmark、实验数据或研发测试工程。
