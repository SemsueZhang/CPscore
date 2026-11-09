# Harness 适配

路径与调用方式按 2026-11-09 打开的官方文档核对。安装器不安装或登录 Harness、不修改全局配置、不读取保存 API key，也不调用模型。技能执行仍受宿主的沙箱、工具权限和账户配置约束。

| `--harness` | 宿主与项目发现路径 | 显式调用 |
| --- | --- | --- |
| `codex` | Codex，`.agents/skills/<name>/SKILL.md` | `$cp-statement-review`，或 `/skills` 选取 |
| `claude-code` | Claude Code 本地终端，`.claude/skills/<name>/SKILL.md` | `/cp-statement-review` |
| `opencode-deepseek` | OpenCode + 用户选择的 DeepSeek，`.opencode/skills/<name>/SKILL.md` | `@cp-statement-review`，或按 ID 加载 |
| `deepseek` | 裸模型/API，没有统一的本地技能发现路径 | unsupported，不创建 `.deepseek` |

技能名可替换为另外三个技能。四个技能共用项目内一份运行时，分别按需读取[正确性协议](protocol.md)或[新颖度手册](novelty.md)。

## 安装、检查与移除

从完整源码目录运行，目标须为已有项目：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness all
python3 -m cpscore reinstall --project /absolute/path/to/problem --harness codex
python3 -m cpscore uninstall --project /absolute/path/to/problem --harness codex
```

`--harness` 可重复或设为 all，省略为 all。reinstall 补回丢失文件、更新未修改的受管安装。共享包、协议、检索手册和所有权记录分别位于 `.cpscore/runtime/cpscore/`、`.cpscore/protocol.md`、`.cpscore/novelty.md`、`.cpscore/manifest.json`。技能的 `scripts/cpscore.py` 按自身路径定位共享包，不产生字节码缓存，项目整体移动后仍可运行，不能单独移动技能目录。

manifest 格式2记录四技能安装，旧格式1可检查、卸载或重装升级。全部目标先预检，遇到他人同名技能、无受管 manifest 的 `.cpscore`、用户改动、内部符号链接或非法 manifest 路径均拒绝操作，不提供强制覆盖。需先保存个人改动、核对并恢复原安装文件，再重装或卸载。

卸载仅删除未修改的受管文件，不删除外部用户文件。卸载一个目标保留其他目标和共享包，最后一个目标才移除共享文件。项目根路径可规范化系统别名（如 macOS `/tmp`），内部受管路径不跟随符号链接。manifest 记录所有权，不认证恶意篡改。安装与移除应串行执行。

安装需要源码中的 `skills/`、`docs/protocol.md`、`scripts/skill_entry.py`。支持源码与 `pip install -e .`，普通 wheel 缺少资源时明确报错，核心评分与报告仍可用。

## 宿主发现与调用限制

Codex 先发现 SKILL.md 的 name/description，再加载选中技能及按需引用。项目 `.agents/skills` 从当前目录向仓库根扫描，同名技能不自动合并，用户可禁用。新技能未出现时检查 `/skills` 并重启会话。

Claude Code 可按描述自动选择或用 `/技能名` 调用。项目发现受设置与运行模式影响，个人或企业同名技能可能优先。本项目仅用标准 YAML frontmatter 与 Markdown，不使用动态 shell 注入、自动工具授权或子智能体 frontmatter。未允许 Bash 不等于安装失败。本适配针对本地终端，不声称覆盖 Cowork、所有云会话或账户同步。

OpenCode 按路径 ID 发现并由 skill 工具加载正文，调用参数以已安装版本为准。先由用户在宿主 `/connect` 连接 DeepSeek、`/models` 选择可用模型，CPscore 不介入凭据。OpenCode 也可能读取 `.agents/skills` 和 `.claude/skills`，项目原生路径通常优先，显式配置源仍可覆盖。只安装正在使用的目标可减少同名副本，来源有疑问时检查实际加载路径。DeepSeek Tool Calls 由外部客户端执行，不使任意 DeepSeek 客户端自动兼容。

官方来源：

- Codex：[Build skills](https://learn.chatgpt.com/docs/build-skills)、[CLI 技能路径](https://developers.openai.com/api/reference/cli)。
- Claude Code：[Extend Claude with skills](https://code.claude.com/docs/en/skills)。
- OpenCode：[Skills](https://opencode.ai/docs/skills/)、[Providers](https://opencode.ai/docs/providers/)、[DeepSeek 接入](https://docs.opencode.ai/docs/providers/#deepseek)。
- DeepSeek：[Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)。

## 验证层次与真实调用

`check` 分别报告以下结果：

| 字段 | 能建立的事实 |
| --- | --- |
| `file_installation` | 文件与哈希符合 manifest |
| `cli.on_path` | 在 PATH 找到命令，execution 仍为 not_tested |
| `invocation` | 始终 not_verified，未发起模型调用 |

文件通过即可使 check 成功，即使 CLI 缺失；文件缺失则失败，即使 CLI 存在。临时项目的 Python 入口测试也只验证评分链路。上述结果不能证明 CLI 已登录、模型可用或技能已被加载。

显式真实调用使用 `scripts/harness_smoke.py`，会调用所选模型，应在用户授权范围内执行：

```sh
python3 scripts/harness_smoke.py --help
python3 scripts/harness_smoke.py --harness codex --skill statement \
  --material /absolute/path/to/statement.md --model YOUR_MODEL \
  --output-dir /absolute/path/to/new-run
```

输出目录须不存在。`--context` 可重复，`--timeout` 默认 600 秒；另外两个宿主使用表中的 harness ID，OpenCode 模型写为 provider/model。脚本保留 prompt、事件、stderr、原始 review、独立重算的 verified-scored 和含 CLI 版本的 run 元数据。CLI 缺失返回 unavailable，零退出码仍须通过安装、协议、材料和 prompt 未改动及输出 scope/结构检查才为 invoked_and_validated。控制器结果文件拒绝覆盖，超时终止进程组。这仅验证一次实际调用与结构合规，准确率需独立裁定。结果及限制以留存记录为准，旧结论不能通过协议迁移自动生效。
