# 程序运行工具

`check-candidate` 在隔离环境中检查样例或进行差分验证，`bench` 测量运行时间。两者输出运行记录，供打分智能体核实后填写报告。

## 准备环境

需要 Linux 容器的 Docker 或 Podman。macOS 先启动 Docker Desktop 或 Podman VM，Windows 使用 Linux/WSL2。在仓库根目录构建镜像：

```sh
docker build -f Dockerfile.runner -t cpscore-runner:local .
```

使用 Podman 时将 `docker` 替换为 `podman`。工具使用本地镜像，不自动拉取。自定义镜像通过 `--image` 指定，须包含 `python3`、`g++` 和 `/bin/sh`。

支持单个 Python 或 C++17 源文件。编译和运行均在禁用网络、只读根文件系统、有资源限额的临时容器中执行。执行前探针核实隔离和工具链，不可用时返回 `unavailable`。残留容器可用 `docker ps -a --filter label=org.cpscore.managed=true` 查看，再按名称移除。

## 检查样例

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --expected fixtures/validation/sample.out
```

多组 `--input` 和 `--expected` 按顺序配对，每个文件最多 16 MiB。按扩展名识别语言，也可设 `--language cpp|python`。`--expected` 可替换为 `--oracle`，两者互斥。

## 差分验证

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/wrong.py \
  --generator fixtures/validation/generator.py \
  --validator fixtures/validation/validator.py \
  --oracle fixtures/validation/oracle.py \
  --seed 20261109 --cases 20 \
  --save-dir .cpscore/counterexamples \
  --output .cpscore/wrong-report.json
```

也可用 `--input` 替代生成器。生成器接受十进制参数 `SEED CASE_INDEX`，以 stdout 输出输入，索引默认从 0 开始，可用 `--start-case` 调整。输入先经校验器，再运行 oracle 和候选程序。

校验器从 stdin 读取输入，退出 0 接受，1 或 2 拒绝。oracle 从 stdin 读取同一输入，以 stdout 输出预期答案。其他退出码、超限或 oracle 失败记为工具故障。各工具按扩展名识别语言，也可使用对应的 `--generator-language`、`--validator-language`、`--oracle-language`。

## 输出比较

| 参数 | 比较方式 |
| --- | --- |
| `--compare exact`（默认） | stdout 字节完全一致 |
| `--compare tokens` | 按 ASCII 空白分词，逐 token 比较字节 |
| `--compare float --abs-tol A --rel-tol R` | token 数相同，全部为有限数值，逐项按以下公式比较 |

```text
abs(a - b) <= max(A, R * max(abs(a), abs(b)))
```

浮点比较的 A、R 必须显式给出且有限、非负。参考输出格式不符记为工具故障，候选输出格式不符记为不匹配。

## 结果与重放

| 状态 | 含义 |
| --- | --- |
| `match` | 本次输出匹配 |
| `candidate_mismatch` | 校验器接受，oracle 与候选均成功，输出不同 |
| `sample_mismatch` | 与给定样例输出不同 |
| `unverified_mismatch` | 与 oracle 不同，尚未经校验器确认输入合法 |
| `candidate_compile_error` | 候选编译失败或超限 |
| `candidate_execution_failure` | 候选退出失败、超时、内存或输出超限 |
| `invalid_input` | 校验器拒绝输入 |
| `tool_error` / `config_error` | 工具或参数错误 |
| `unavailable` | 隔离环境不可用，未执行候选程序 |

读取 `counts`、`cases` 和 `all_cases_matched` 查看结果。退出码 0 表示全部匹配或测量完成，1 表示候选观察或待核实差异，2 表示参数、输入、工具或保存错误，3 表示隔离不可用。

不匹配和故障会尽可能保存输入、输出、源码快照、哈希、退出码、限额及环境，生成数据还保存种子和索引。确认反例前独立核实输入与 oracle 答案。证据目录内 `manifest.json` 提供重放命令，也可运行：

```sh
python3 /absolute/path/to/evidence/replay.py
```

重放需要同版本 CPscore 和记录的镜像 ID。证据目录可移动，运行时移动后用 `--runtime /新的运行时根目录` 指定包含 `cpscore/` 的目录。

## 性能测量与资源参数

```sh
python3 -m cpscore bench \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --validator fixtures/validation/validator.py \
  --warmups 1 --repetitions 3 --output .cpscore/bench.json
```

报告保存预热、各次测量、最小/中位/最大墙钟时间及运行环境。计时包含容器启动和管道开销。`bench` 不检查答案，请先用 `check-candidate` 验证输出。

| 参数 | 默认值 |
| --- | --- |
| `--timeout` | 2 秒墙钟 |
| `--compile-timeout` | 30 秒 |
| `--memory-mib` | 256 |
| `--cpus` | 1 |
| `--pids` | 64 |
| `--output-limit-kib` | stdout/stderr 合计 1024 KiB，可用互斥的 `--output-limit-bytes` 精确指定 |
| `--scratch-mib` | 每个 tmpfs 128 MiB |

生成器、校验器、oracle 和候选程序使用相同运行限制。编译内存至少 1024 MiB，临时空间至少 256 MiB，产物最多 64 MiB。

容器引擎已启动、镜像已构建后，运行集成测试：

```sh
CPSCORE_RUN_SANDBOX_TESTS=1 python3 -m unittest tests.test_validation.SandboxIntegrationTests -v
```

可用 `CPSCORE_SANDBOX_ENGINE=docker|podman` 和 `CPSCORE_SANDBOX_IMAGE=...` 选择引擎与镜像。
