# 安装与调用

八个技能安装到目标项目，共享一份 `.cpscore` 运行时。需要完整源码和已配置的宿主，技能名称与用途见[README](../README.md)。

| `--harness` | 技能目录 | 调用方式 |
| --- | --- | --- |
| `codex` | `.agents/skills/<name>/` | `$cp-statement-review` 或 `/skills` |
| `claude-code` | `.claude/skills/<name>/` | `/cp-statement-review` |
| `opencode-deepseek` | `.opencode/skills/<name>/` | 按技能ID加载，语法以宿主版本为准 |

OpenCode先用 `/connect` 连接DeepSeek，再用 `/models` 选模型。裸DeepSeek API不支持技能安装。

## 安装、更新与卸载

目标须为已有目录，在源码目录运行：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
python3 -m cpscore reinstall --project /absolute/path/to/problem --harness codex
python3 -m cpscore uninstall --project /absolute/path/to/problem --harness codex
```

`--harness` 可重复，省略或设为 `all` 时选择全部宿主。安装和卸载串行执行。`reinstall` 更新受管文件并补回缺失文件，同名外部技能、用户改动或内部符号链接会阻止写入，须先保存和处理冲突。

`.cpscore/runtime/cpscore/` 保存代码，`.cpscore/` 下另有 `protocol.md`、`novelty.md`、`data.md`、`assessment.md` 和 `manifest.json`。清单格式4兼容旧格式1/2/3。卸载部分宿主保留共享文件，卸载最后一个时移除。项目可整体移动，不单独移动技能目录。普通wheel缺少技能资源时只能使用核心算分与报告工具。

## 调用与验证

宿主按技能名调用，示例见README。新技能未出现时检查列表并重启会话；同名冲突时核对加载路径。宿主说明：[Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills)、[OpenCode](https://opencode.ai/docs/skills/)。

安装后的工具入口为 `python3 <实际技能目录>/scripts/cpscore.py`，参数与 `python3 -m cpscore` 相同，含空格路径须加引号。10分制记录按[评分协议](protocol.md)处理，总评和预测用[assess入口](assessment.md)。

`check` 只验证文件与哈希：`file_installation` 为安装状态，`cli.on_path` 为CLI是否存在，`invocation` 保持 `not_verified`。实际10分制模型调用可用：

```sh
python3 scripts/harness_smoke.py --harness codex --skill statement \
  --material /absolute/path/to/statement.md --model YOUR_MODEL \
  --output-dir /absolute/path/to/new-run
```

脚本支持 `statement`、`solution`、`editorial`、`data`，`--context` 可重复，默认超时600秒，输出目录须不存在。OpenCode模型名用 `provider/model`。三个总评与预测技能直接在宿主中调用。

输出保留输入、prompt、事件、stderr、原始记录、独立重算结果和 `run.json`。CLI缺失返回 `unavailable`，执行及结构校验通过返回 `invoked_and_validated`，不代表审查结论准确。

脚本只复制显式文件，不递归搬运数据套件依赖。数据技能宜在已有题目项目调用，或先准备完整独立目录；缺依赖时报告未执行。
