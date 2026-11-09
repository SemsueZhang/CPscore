# Harness 适配与验证边界

核对日期：2026-11-09。以下目录和调用方式依据实际打开的官方文档。安装器不安装 Harness、不修改用户全局配置、不登录服务、不读取或保存 API key，也不发起模型调用。模型/API 与负责技能发现、文件读写及工具执行的 Harness 是两层。

| 安装目标 | 实际 Harness | 项目技能位置 | 显式调用 |
| --- | --- | --- | --- |
| `codex` | Codex 本地 CLI / 支持本地 skills 的环境 | `.agents/skills/<name>/SKILL.md` | `$cp-statement-review`，或 `/skills` 选取 |
| `claude-code` | Claude Code 本地终端 | `.claude/skills/<name>/SKILL.md` | `/cp-statement-review` |
| `opencode-deepseek` | OpenCode，模型由用户选择 DeepSeek | `.opencode/skills/<name>/SKILL.md` | `@cp-statement-review`，或要求 agent 按 ID 加载 |
| `deepseek` | 未指定 Harness，仅模型/API | **不支持** | 返回 unsupported，不创建 `.deepseek` 目录 |

表中的技能名均可换为 `cp-solution-review`、`cp-editorial-review`。共三个原始技能，适配器只将它们部署到各宿主目录，共享协议与评分运行时在每个项目中仅一份。不要把另外一个 Harness 的模型提供商名称当作新的技能目录标准。

## 安装与移除

从 CPscore 源码目录执行，目标必须是已存在的项目目录。无需 pip 安装即可部署：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore install --project /absolute/path/to/problem --harness claude-code
python3 -m cpscore install --project /absolute/path/to/problem --harness opencode-deepseek
python3 -m cpscore check --project /absolute/path/to/problem --harness all
python3 -m cpscore reinstall --project /absolute/path/to/problem --harness codex
python3 -m cpscore uninstall --project /absolute/path/to/problem --harness codex
```

`--harness` 可重复，省略时选择 all。重装使用同一安装逻辑，补回丢失的受管文件并更新未被修改的安装。安装时会复制完整共享包到 `.cpscore/runtime/cpscore/`，协议到 `.cpscore/protocol.md`，所有权与 SHA256 到 `.cpscore/manifest.json`。每个技能仅有本体与指向项目共享包的薄入口 `scripts/cpscore.py`，入口按自身路径定位，因此项目整体移动后仍可运行。入口不产生字节码缓存，正常运行后可卸载并重装。

安装前预检全部目标。已有他人同名技能目录、无受管 manifest 的 `.cpscore`、受管文件已修改、内部符号链接、非法 manifest 路径均拒绝操作，不提供强制覆盖。若受管文件被修改，请先保存个人改动，再与原安装版本核对和恢复，随后重装或卸载。外部用户文件不会被删除。多个目标共存时，只卸载一个会保留其他目标及共享包，最后一个目标卸载后才删除未修改的共享受管文件。

项目路径本身会规范化，因此 macOS `/tmp` 等系统别名可用。项目内部受管路径不跟随符号链接。manifest 是文件所有权记录，不是对恶意用户篡改 manifest 的密码学认证。安装与卸载应串行执行，避免另一个进程同时修改安装文件。

安装器依赖源码中的 `skills/`、`docs/protocol.md`、`scripts/skill_entry.py`。支持源码运行与 `pip install -e .`。普通 wheel 保留评分/报告功能，但没有这些源码资源时，技能安装会明确报资源不可用，请从完整源码部署技能。不要单独移动一个技能目录，它依赖同项目 `.cpscore`。

## Codex

OpenAI Docs 说明，技能以 `SKILL.md` 的 name/description 发现，选中后再加载正文及按需读取辅助文件。当前项目路径是 `.agents/skills`，Codex 会从当前目录向仓库根目录扫描。同名技能不会自动合并，用户配置也可禁用技能。

在目标项目启动 Codex，输入例如：

```text
$cp-solution-review 审查 statement.md 与 solution.cpp，写入 review.json，并用共享入口生成 review.md。
```

新技能未出现时用 `/skills` 检查并重启会话。宿主的沙箱与工具权限依然有效，skill 没有提升权限的能力。

官方来源：[Build skills](https://learn.chatgpt.com/docs/build-skills)（原 Codex skills 地址会跳转至此），[官方 CLI 技能安装路径表](https://developers.openai.com/api/reference/cli)。

## Claude Code

本项目采用标准 YAML frontmatter 的 name/description 和 Markdown 正文，不使用 Claude 专有的动态 shell 注入、自动工具授权或子智能体 frontmatter。Claude Code 可按描述自动选择，也可用 `/技能名` 显式调用。项目 `.claude/skills` 的发现受设置与运行模式影响，个人或企业同名技能可能优先。

在本地目标项目启动 `claude`：

```text
/cp-editorial-review 审查 editorial.md，并用 statement.md 与 solution.cpp 交叉核验，生成 review.json 和 review.md。
```

首次执行 Python 命令仍遵循用户工具授权。未预先允许 Bash 不等于安装失败。Claude Code 的本地终端、Cowork 与云会话的加载范围不同，本适配不声称覆盖所有云会话或账户同步技能。

官方来源：[Extend Claude with skills](https://code.claude.com/docs/en/skills)。

## OpenCode + DeepSeek

OpenCode 官方将项目 `.opencode/skills` 作为技能源，同时兼容部分其他宿主路径。技能通过路径 ID 识别，描述先被提供给模型，再由 skill 工具加载正文，权限规则可能允许、询问或拒绝。当前文档支持 `@skill-id` 显式提及。不同版本的工具参数可能变化，使用已安装版本的技能工具定义，不把文档示例参数写死到模型 API 请求。

由用户在 OpenCode 中先运行 `/connect` 连接 DeepSeek，再运行 `/models` 选择当前账户可用的 DeepSeek 模型。此过程由 Harness 处理，CPscore 不介入凭据。在目标项目启动 OpenCode 后示例：

```text
@cp-statement-review 审查 statement.md 的定义、约束与样例，保存 review.json 并生成 review.md。
```

若安装了 all，OpenCode 也可能发现 `.agents/skills` 和 `.claude/skills` 的同名副本。官方文档说明来源存在覆盖顺序，项目原生 `.opencode/skills` 通常优先于这两个兼容目录，显式配置源仍可覆盖。若内容或来源有疑问，检查实际加载路径。最简单的部署是只安装当前要用的目标。

DeepSeek 官方说明，函数调用由外部客户端实际执行，模型本身不执行函数。这不构成统一的本地 Skill 搜索路径。裸 DeepSeek API、网页聊天或任意其他 DeepSeek 客户端均不能据此声称兼容。第三目标准确名称是 **OpenCode + DeepSeek**，只确认文件格式适配，模型是否按预期遵循技能仍须真实调用验证。

官方来源：[OpenCode Skills](https://opencode.ai/docs/skills/)、[OpenCode Providers](https://opencode.ai/docs/providers/)、[OpenCode 的 DeepSeek 接入说明](https://docs.opencode.ai/docs/providers/#deepseek)、[DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)。

## 三种验证分别报告

`check` 的 JSON 把以下层次分开，不能互相推断：

1. `file_installation`：受管技能、共享包与协议的存在和哈希是否符合 manifest。
2. `cli.on_path`：能否在当前 PATH 找到命令，仅表示找到路径。`cli.execution` 为 not_tested，不等于 CLI 启动、登录或模型可用。
3. `invocation`：check 始终为 not_verified。安装器不会花费模型额度或伪造真实 Harness 调用，另行烟测应记录宿主版本、实际调用、输出与限制。

在没有 CLI 的环境中，只要文件验证通过，check 可返回成功，同时准确报告 CLI 缺失和真实调用未验证。CLI 存在却文件缺失时，check 仍失败。使用临时项目的入口烟测只能证明 Python 评分链路可运行，不能证明 Codex、Claude Code 或 DeepSeek 模型已实际加载并遵循技能。

## 本次真实调用记录

2026-11-09 已在临时项目真实调用 Codex CLI 0.167.0-alpha.3.2，使用 GPT-6.1 Sol、xhigh，完成 `cp-statement-review` 的一次加载与工具烟测。会话实际读取安装技能和共享协议，用安装入口生成并校验 review.json、生成 review.md，得到一项样例算术问题、9 分/pass，程序与题解保持 not_reviewed，未运行候选程序。归档包含原提示、人工题面、原报告、资源哈希与脱敏事件摘录，见 [Codex 集成证据](../tests/integration_evidence/codex-statement/README.md)。

该次人工题面只说明一个技能的真实发现、加载和工具链连接成功，不衡量审核准确率，也未覆盖其余两技能的真实调用。Claude Code 与 OpenCode + DeepSeek 本次未真实调用。`check` 仍仅报告本地文件与命令路径，不会把历史烟测当作当前项目的真实调用验证。
