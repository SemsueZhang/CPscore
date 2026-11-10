# 安装与调用

CPscore 将四个打分技能安装到目标项目，并在项目内共享一份 `.cpscore` 运行时。安装需要完整源码目录，调用技能需要已配置的宿主。

| `--harness` | 技能目录 | 调用方式 |
| --- | --- | --- |
| `codex` | `.agents/skills/<name>/SKILL.md` | `$cp-statement-review`，或从 `/skills` 选择 |
| `claude-code` | `.claude/skills/<name>/SKILL.md` | `/cp-statement-review` |
| `opencode-deepseek` | `.opencode/skills/<name>/SKILL.md` | 按技能 ID 加载，调用语法以宿主版本为准 |

表中的技能名可替换为其他三个技能。使用 OpenCode 时，先通过 `/connect` 连接 DeepSeek，再用 `/models` 选择模型。裸 DeepSeek API 不支持技能安装。

## 安装、更新与卸载

在源码目录运行，目标须为已有项目：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
python3 -m cpscore reinstall --project /absolute/path/to/problem --harness codex
python3 -m cpscore uninstall --project /absolute/path/to/problem --harness codex
```

`--harness` 可重复，设为 `all` 或省略时选择全部宿主。`reinstall` 更新受管安装并补回丢失文件。遇到同名外部技能、用户修改或内部符号链接时，先保存改动并处理冲突，再重新执行。

共享代码、打分规则、新颖度手册和安装清单分别位于 `.cpscore/runtime/cpscore/`、`.cpscore/protocol.md`、`.cpscore/novelty.md`、`.cpscore/manifest.json`。卸载一个宿主会保留其他宿主及共享文件，卸载最后一个宿主时移除共享文件。安装和卸载应串行执行。

技能入口按自身路径定位运行时，项目整体移动后仍可运行，请勿单独移动技能目录。安装支持源码运行和 `pip install -e .`，普通 wheel 缺少技能资源时只能使用核心算分与报告工具。

## 调用技能

例如在 Codex 中输入：

```text
$cp-statement-review 为 statement.md 打分，保存 review.json 并生成 review.md。
$cp-novelty-review 为 statement.md 和 editorial.md 评定新颖度，保存 novelty.md 和检索附件。
```

新技能未出现时检查宿主技能列表，并重启会话。出现同名技能时核对实际加载路径。宿主配置参考 [Codex](https://learn.chatgpt.com/docs/build-skills)、[Claude Code](https://code.claude.com/docs/en/skills) 和 [OpenCode](https://opencode.ai/docs/skills/) 的技能文档。

安装后的命令行入口为 `python3 <实际技能目录>/scripts/cpscore.py`，参数与 `python3 -m cpscore` 相同。路径含空格时使用引号。

`check` 的 `file_installation` 表示文件及哈希状态，`cli.on_path` 表示是否找到 CLI，`invocation` 保持 `not_verified`。实际模型调用使用下面的脚本。

## 脚本调用

```sh
python3 scripts/harness_smoke.py --harness codex --skill statement \
  --material /absolute/path/to/statement.md --model YOUR_MODEL \
  --output-dir /absolute/path/to/new-run
```

脚本会调用所选模型。`--skill` 支持 `statement`、`solution`、`editorial`，`--context` 可重复，`--timeout` 默认 600 秒。输出目录须不存在，OpenCode 模型名使用 `provider/model`。

输出包括输入材料、prompt、事件、stderr、原始 `review.json`、独立重算的 `verified-scored.json` 和 `run.json`。CLI 缺失返回 `unavailable`，执行及结构校验通过返回 `invoked_and_validated`，其他状态及原因写入 `run.json`。
