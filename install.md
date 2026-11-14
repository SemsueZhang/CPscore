# 安装、调用、更新与卸载

CPScore 遵循[Agent Skills 规范](https://agentskills.io/specification)。各技能独立使用，不强制依赖其他技能或额外运行时。安装时复制整个技能目录，包括 `SKILL.md`、引用文件与随包脚本。题目质量评分 `cp-quality-review` 以人类题解为依据，随包检索脚本会探测 Python 3.8+，不可用时使用宿主工具，无需安装额外依赖。

先下载仓库 ZIP，或执行 `git clone https://github.com/SemsueZhang/CPscore.git`，再进入 CPscore 目录。

## 选择安装位置

以下为本地宿主的默认位置：

| 宿主 | 全局 | 项目级 | 调用 |
| --- | --- | --- | --- |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills/` | `.agents/skills/` | `$cp-editorial-review`，或从技能选择器选择 |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/` | `.claude/skills/` | `/cp-editorial-review` |
| [OpenCode](https://opencode.ai/docs/skills/) | `~/.config/opencode/skills/` | `.opencode/skills/` | 要求模型加载技能ID，新版本也可 `@cp-editorial-review` |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md) | `~/.dsh/skills/` | `.dsh/skills/` | [`/cp-editorial-review`](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/tool-skill/README.md) |

项目级目录位于要审核的项目中，全局安装对该宿主的其他项目也可见。重复安装时核对实际加载路径，宿主版本不一致时以实际技能列表为准。已有同名技能先保存自定义修改，再按下文更新。

OpenCode 可按[提供商说明](https://opencode.ai/docs/providers/)或[DeepSeek 接入说明](https://api-docs.deepseek.com/quick_start/agent_integrations/opencode/)使用 `/connect` 与 `/models` 配置模型。技能安装在宿主中，裸 API 不具备目录发现和调用机制。

DeepSeek Harness 也默认扫描项目级与全局的 `.agents/skills/`，自定义 `DSH_HOME` 时使用其下的 `skills/`。该接入方式依据官方文档，尚未完成实际加载与审核验证。

## macOS、Linux、Git Bash

设定目标目录和技能，以下以全局 Codex 为例：

```sh
cpscore_dest="$HOME/.agents/skills"
cpscore_skill=cp-editorial-review
```

其他宿主按上表替换 `cpscore_dest`，自定义配置根目录时使用实际路径。项目级使用题目项目的绝对路径，例如 `/absolute/path/to/problem/.agents/skills`。

安装单个技能：

```sh
mkdir -p "$cpscore_dest"
cp -R "skills/$cpscore_skill" "$cpscore_dest/"
```

安装全部技能，用下面操作替换上述安装命令：

```sh
mkdir -p "$cpscore_dest"
for cpscore_skill_dir in skills/*/; do
  test -f "${cpscore_skill_dir}SKILL.md" || continue
  cp -R "${cpscore_skill_dir%/}" "$cpscore_dest/"
done
```

更新源码可用 `git pull --ff-only`。保存已安装技能的自定义修改后，删除旧目录再复制，避免遗留旧文件：

```sh
rm -r "$cpscore_dest/$cpscore_skill"
cp -R "skills/$cpscore_skill" "$cpscore_dest/"
```

卸载所选技能时，执行更新代码块中的 `rm -r "$cpscore_dest/$cpscore_skill"`。批量更新或卸载时逐个处理所选技能，不删除整个宿主技能目录。

## Windows PowerShell

在 CPscore 目录执行，无需 Git Bash：

```powershell
$cpscoreDest = Join-Path $HOME '.agents/skills'
$cpscoreSkill = 'cp-editorial-review'
New-Item -ItemType Directory -Force -Path $cpscoreDest | Out-Null
Copy-Item -Recurse -Path "skills/$cpscoreSkill" -Destination $cpscoreDest
```

其他宿主按上表替换 `Join-Path` 的相对部分，项目级改为实际路径，例如 `C:/problems/demo/.agents/skills`。自定义 `DSH_HOME` 时使用其下的 `skills`。

安装全部技能时，用以下操作替换最后一行：

```powershell
Get-ChildItem -Directory 'skills' | Where-Object {
    Test-Path (Join-Path $_.FullName 'SKILL.md')
} | ForEach-Object {
    Copy-Item -Recurse -Path $_.FullName -Destination $cpscoreDest
}
```

更新前保存自定义修改，再执行：

```powershell
Remove-Item -Recurse -Path (Join-Path $cpscoreDest $cpscoreSkill)
Copy-Item -Recurse -Path "skills/$cpscoreSkill" -Destination $cpscoreDest
```

卸载所选技能时，执行更新代码块中的 `Remove-Item` 命令。宿主可用性以其支持的环境为准，WSL 中运行的宿主使用 WSL 内的安装目录。

## 确认安装

新建或重启宿主会话，提供一份题面或题解并按上表调用，例如 Codex 中输入 `$cp-editorial-review 审核 editorial.md，结合 statement.md。`。确认实际加载的路径，预期在对话收到报告，无需预建文件或执行 CPScore 命令。

看不到技能时检查目录层级、名称冲突、宿主版本和访问权限。DeepSeek Harness 另检查本地技能发现与加载插件，以及会话是否位于题目项目。
