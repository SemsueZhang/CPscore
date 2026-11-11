# CPScore : 面向算法竞赛的题目评价系统

CPScore 是一个面向算法竞赛的独立评分 Skill。安装需要的技能，在本地智能体中提供材料，即可直接收到有依据的 Markdown 评审报告。现已支持 codex、claude code、opencode、deepseek harness 等多平台。

目前总共有 8 个子 Skills，每个 Skill 可单独安装和调用。默认直接输出报告，只有你要求保存时才创建文件。

## 技能清单

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

## 安装与调用

下载仓库，或执行 `git clone https://github.com/SemsueZhang/CPscore.git`。进入仓库目录后，将所需 Skill 复制到宿主技能目录。例如在 macOS、Linux 或 Git Bash 中全局安装一个 Codex Skill：

```sh
mkdir -p "$HOME/.agents/skills"
cp -R skills/cp-editorial-review "$HOME/.agents/skills/"
```

其他宿主、项目级或批量安装、Windows PowerShell、更新与卸载统一见[安装说明](install.md)。已有同名技能时先保存自己的修改。

安装后启动宿主的新会话，在题目项目中提供文件或粘贴材料。例如：

| 宿主 | 输入示例 |
| --- | --- |
| Codex | `$cp-editorial-review 审核 editorial.md，结合 statement.md。` |
| Claude Code | `/cp-editorial-review 审核 editorial.md，结合 statement.md。` |
| OpenCode | `请加载 cp-editorial-review 技能，审核 editorial.md，结合 statement.md。` |

其他用途只需替换技能名和材料。例如让 `cp-data-review` 结合原数据、答案、判定器和子任务检查是否有漏网错解，或让 `cp-problem-review` 直接审核全部题目材料。已有评审可直接复用，不必先运行其他技能。

**重要**：需要文件时直接说“将审核保存为 review.md”，否则报告在对话中返回。简短报告示例：

> **评分：7/10 — 尚可，值得打磨**
>
> **[Major −3] 缺少最优性论证**
>
> 当前只证明删去冗余面额后系统等价，还需证明任意等价系统都必须包含每个不可约面额。
>
> **修改建议**：补充不可约面额必选的替换反证，建立种数下界。

## 结果说明

10分制从10分起，Fatal −10、Major −3、Minor −1，最低0分。同一根因只扣一次，未确认疑点不扣分。9～10分为优秀、具备推荐资格，6～8分为尚可、值得打磨，0～5分为不合格。关键核验未完成时标明暂定和具体缺口，暂定高分的档次待定。算法错误与证明缺漏分别判断，简洁正确的题解、公认结论和个人文风偏好不扣分。

新颖度独立使用A/B/C/C+/D/F。C+和F的质量标准相同，区别在先例关系。题目及比赛总评取各适用项的最低档，不取平均。选手表现预测是基于材料的分析，不是实测成绩。

检索、读取和代码执行使用宿主已有能力。数据实际通过率和运行时间需要真实执行，缺少工具时会说明具体未完成部分。审核流程见各技能的 `SKILL.md`，详细协议放在相应技能的 `references/` 中，由入口说明何时读取。安装和更新时复制整个技能目录。

## 项目目录

```text
CPscore/
├── .github/    # CI 配置与检查脚本
├── examples/
│   └── editorial-review.md     # 题解审核示例
└── skills/
    ├── cp-statement-review/    # 题面审核
    ├── cp-solution-review/     # 程序审核
    ├── cp-editorial-review/    # 题解审核
    ├── cp-data-review/         # 数据审核
    ├── cp-novelty-review/      # 新颖度审核
    ├── cp-problem-review/      # 题目总评
    ├── cp-contest-review/      # 比赛总评
    └── cp-performance-predict/ # 选手表现预测
```

## 示例

| 项目 | 链接 | 摘要 |
| --- | --- | --- |
| 题解审核 | [货币系统](examples/editorial-review.md) | 算法正确但缺少最优性下界，评分7/10。此为编写的使用示例。 |

更多实际评审案例待补充。

## 许可证

本项目采用 [MIT License](LICENSE)。
