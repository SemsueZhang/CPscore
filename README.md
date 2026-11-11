# CPScore

面向算法竞赛出题人的八个独立审核 Skill。安装需要的技能，在 Codex、Claude Code 或 OpenCode 中提供材料，即可直接收到有依据的 Markdown 评审。

每个 Skill 自带规则，可单独安装和调用，无需额外运行时。默认不创建报告文件，只有你要求保存时才写文件。

## 有哪些技能

| Skill | 用途 | 结果 |
| --- | --- | --- |
| [cp-statement-review](skills/cp-statement-review/SKILL.md) | 定义、输入输出、约束、边界、样例 | 10分制评分及修改建议 |
| [cp-solution-review](skills/cp-solution-review/SKILL.md) | 算法、正确性、复杂度、实现 | 10分制评分及修改建议 |
| [cp-editorial-review](skills/cp-editorial-review/SKILL.md) | 关键思想、证明、复杂度 | 10分制评分及修改建议 |
| [cp-data-review](skills/cp-data-review/SKILL.md) | 数据合法性、错解漏网、子任务得分 | 10分制评分及补点建议 |
| [cp-novelty-review](skills/cp-novelty-review/SKILL.md) | 相似题、论文、独立考点和推导质量 | A/B/C/C+/D/F |
| [cp-problem-review](skills/cp-problem-review/SKILL.md) | 单题材料、解法空间与整体设计 | 推荐 / 合格 / 不合格 |
| [cp-contest-review](skills/cp-contest-review/SKILL.md) | 按实际比赛要求审核题目组合 | 推荐 / 合格 / 不合格 |
| [cp-performance-predict](skills/cp-performance-predict/SKILL.md) | 预测选手路线、障碍、时间和得分 | 预测分析，不作质量评级 |

## 安装

下载仓库，或执行：

```sh
git clone https://github.com/SemsueZhang/CPscore.git
cd CPscore
```

选择宿主和安装范围，将 Skill 目录复制到对应位置即可。以下是宿主默认目录，`<项目>` 指要审核的题目项目。

| 宿主 | 全局安装 | 项目级安装 |
| --- | --- | --- |
| Codex | `~/.agents/skills/` | `<项目>/.agents/skills/` |
| Claude Code | `~/.claude/skills/` | `<项目>/.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `<项目>/.opencode/skills/` |

例如在 macOS、Linux 或 Git Bash 中，从本仓库目录全局安装一个 Codex Skill：

```sh
mkdir -p "$HOME/.agents/skills"
cp -R skills/cp-editorial-review "$HOME/.agents/skills/"
```

安装全部技能：

```sh
mkdir -p "$HOME/.agents/skills"
for cpscore_skill_dir in skills/*/; do
  test -f "${cpscore_skill_dir}SKILL.md" || continue
  cp -R "${cpscore_skill_dir%/}" "$HOME/.agents/skills/"
done
```

用于其他宿主或项目时，将目标换为表中的目录，保持 `<技能名>/SKILL.md` 层级。Windows PowerShell、四种安装组合、更新、卸载和官方来源见[安装说明](docs/install.md)。已有同名技能时先保存自己的修改。

## 调用

安装后启动宿主的新会话，在题目项目中提供文件或粘贴材料。例如：

| 宿主 | 输入示例 |
| --- | --- |
| Codex | `$cp-editorial-review 审核 editorial.md，结合 statement.md。` |
| Claude Code | `/cp-editorial-review 审核 editorial.md，结合 statement.md。` |
| OpenCode | `请加载 cp-editorial-review 技能，审核 editorial.md，结合 statement.md。` |

OpenCode 的新版本也支持 `@cp-editorial-review` 显式提及。连接 DeepSeek 时先在 OpenCode 中 `/connect` 选择提供商，再用 `/models` 选择模型。Skill 安装在宿主中，不是安装到裸模型 API。

其他用途只需替换技能名和材料。例如让 `cp-data-review` 结合原数据、答案、判定器和子任务检查漏网，或让 `cp-problem-review` 直接审核全部题目材料。已有评审可直接复用，不必先运行其他技能。

需要文件时直接说“将审核保存为 review.md”，否则报告在对话中返回。简短报告示例：

> **评分：7/10 — 尚可，值得打磨**
>
> **[Major −3] 缺少最优性论证**
>
> 当前只证明删去冗余面额后系统等价，还需证明任意等价系统都必须包含每个不可约面额。
>
> **修改建议**：补充不可约面额必选的替换反证，建立种数下界。

## 如何理解结果

10分制从10分起，Fatal −10、Major −3、Minor −1，最低0分。同一根因只扣一次，未确认疑点不扣分。9～10分为优秀、具备推荐资格，6～8分为尚可、值得打磨，0～5分为不合格。关键核验未完成时标明暂定和具体缺口，暂定高分的档次待定。算法错误与证明缺漏分别判断，简洁正确的题解、公认结论和个人文风偏好不扣分。

新颖度独立使用A/B/C/C+/D/F。C+和F的质量标准相同，区别在先例关系。题目及比赛总评取各适用项的最低档，不取平均。选手表现预测是基于材料的分析，不是实测成绩。

检索、读取和代码执行使用宿主已有能力。数据实际通过率和运行时间需要真实执行，缺少工具时会说明具体未完成部分。完整的任务标准直接写在各自 `SKILL.md` 中。

[示例](examples/editorial-review.md) · [人工验收材料](tests/README.md) · [本次重构与验证记录](docs/review-notes.md)
