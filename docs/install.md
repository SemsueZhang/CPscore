# 安装、调用、更新与卸载

CPScore遵循[Agent Skills规范](https://agentskills.io/specification)：每个技能目录内有一个带 `name` 和 `description` 的 `SKILL.md`。所有当前技能都可独立复制，不需要公共协议、其他技能或运行时。

## 选择安装位置

2026-11-11核对官方文档，以下为本地宿主的默认位置：

| 宿主 | 全局 | 项目级 | 调用 |
| --- | --- | --- | --- |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills/` | `.agents/skills/` | `$cp-editorial-review`，或从技能选择器选择 |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/` | `.claude/skills/` | `/cp-editorial-review` |
| [OpenCode](https://opencode.ai/docs/skills/) | `~/.config/opencode/skills/` | `.opencode/skills/` | 要求模型加载技能ID，新版本也可 `@cp-editorial-review` |

项目级目录在要审核的项目中，不一定是CPScore源码目录。全局会影响该宿主的其他本地项目。已有同名技能或全局、项目重复安装时，应核对实际加载路径，避免审到旧规则。宿主版本与当前文档不一致时，以实际版本的技能列表和加载路径为准。

OpenCode支持DeepSeek等提供商。按[OpenCode提供商说明](https://opencode.ai/docs/providers/)或[DeepSeek官方接入说明](https://api-docs.deepseek.com/quick_start/agent_integrations/opencode/)，用 `/connect` 连接已有账户，再用 `/models` 选择模型。技能安装在OpenCode中，裸DeepSeek API没有这里的目录发现和调用机制。

## macOS、Linux、Git Bash

先进入下载或克隆得到的CPScore目录。设定一次目标和需要的技能，下面以全局Codex为例：

```sh
cpscore_dest="$HOME/.agents/skills"
cpscore_skill=cp-editorial-review
```

其他目标可将第一行改为：

```sh
# Claude Code全局
cpscore_dest="$HOME/.claude/skills"
# OpenCode全局（如自行配置了其他配置根目录，使用实际路径）
cpscore_dest="$HOME/.config/opencode/skills"
# 项目级示例：请换成已有题目项目的实际绝对路径
cpscore_dest="/absolute/path/to/problem/.agents/skills"
# Claude Code和OpenCode项目级分别使用 .claude/skills、.opencode/skills
```

这些是备选赋值，选择其中一个即可。然后执行对应安装操作：

**单个技能，全局或项目级均适用：**

```sh
mkdir -p "$cpscore_dest"
cp -R "skills/$cpscore_skill" "$cpscore_dest/"
```

**全部技能，全局或项目级均适用：**

```sh
mkdir -p "$cpscore_dest"
for cpscore_skill_dir in skills/*/; do
  test -f "${cpscore_skill_dir}SKILL.md" || continue
  cp -R "${cpscore_skill_dir%/}" "$cpscore_dest/"
done
```

循环扫描实际目录，没有硬编码技能数量。不要只复制文件正文，保留 `<技能名>/SKILL.md` 目录结构。

**更新和卸载：**

先保存对已安装技能的自定义修改。更新源码可用 `git pull --ff-only`，再删除所选技能旧目录并重新复制，避免遗留旧版辅助脚本：

```sh
rm -r "$cpscore_dest/$cpscore_skill"
cp -R "skills/$cpscore_skill" "$cpscore_dest/"
```

只卸载时执行第一行即可。批量更新或卸载时，对实际安装过的技能逐个进行，不删除整个宿主技能目录。旧版安装留下的项目内 `.cpscore` 不再被任何技能使用，确认其中没有自己的材料后可移除；旧报告和实测证据按需保留。

## Windows PowerShell

不必安装Git Bash。下载仓库ZIP或使用Git克隆，进入CPScore目录后执行：

```powershell
$cpscoreDest = Join-Path $HOME '.agents/skills'
$cpscoreSkill = 'cp-editorial-review'
New-Item -ItemType Directory -Force -Path $cpscoreDest | Out-Null
Copy-Item -Recurse -Path "skills/$cpscoreSkill" -Destination $cpscoreDest
```

全局Claude Code换为 `Join-Path $HOME '.claude/skills'`，OpenCode换为 `Join-Path $HOME '.config/opencode/skills'`。项目级改为实际路径，例如 `C:/problems/demo/.agents/skills`，其他宿主替换相应目录。

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

只卸载时执行第一行即可。Windows上的宿主可用性以相应宿主支持的环境为准，在WSL中运行的宿主使用WSL文件系统中的安装目录，而非Windows用户目录。

## 确认安装

重启或新建宿主会话，用对应名称调用，确认实际加载了所复制目录的 `SKILL.md`，提供一份题面或题解。预期直接在对话收到报告，不需要预建文件或执行CPScore命令。看不到技能时检查路径层级、名称冲突、宿主版本及技能访问权限。

官方文档核对不等于本机调用成功。各宿主真实验证情况、命令与限制见[验收记录](review-notes.md)。
