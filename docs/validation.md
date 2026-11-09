# 隔离运行与验证证据

`check-candidate` 和 `bench` 只产生可选运行证据，不自动完成 coverage 或扣分。证据绑定、确认门槛和有限测试的证明边界统一见[协议](protocol.md)。

## 准备隔离环境

需要 Linux 容器的 Docker 或 Podman；macOS 使用已启动的 Docker Desktop/Podman VM，原生 Windows 返回 unavailable，可改用 Linux/WSL2。工具不启动守护进程、不安装环境或自动拉镜像，不退回宿主裸跑或未经验证的 sandbox-exec。

在仓库根目录显式构建只含 Python 3 与 C++17 工具链的镜像。

```sh
docker build -f Dockerfile.runner -t cpscore-runner:local .
# 或：podman build -f Dockerfile.runner -t cpscore-runner:local .
```

构建需要 Debian 软件源网络。运行使用本地镜像，固定镜像 ID 并加 `--pull=never`，不用可变 tag 作为复现依据。自定义 `--image` 须可信、无凭据，含 `python3`、`g++` 和 `/bin/sh`。

每个编译或运行阶段都创建独立的临时容器，并施加以下限制。

- 网络为 `none`，只读根文件系统，UID/GID 为 `65534:65534`
- 丢弃所有 Linux capabilities，开启 `no-new-privileges`，保留引擎默认系统调用过滤
- 有限的 CPU 配额、内存与 swap、进程数、单文件大小、文件描述符数、临时文件空间
- 源码与已编译程序只读挂载，不向不可信程序提供任何可写宿主机挂载
- stdin、stdout、stderr 经过有界管道，stdout/stderr 合计超限或墙钟超时会停止附着客户端并强制移除容器

C++ 编译与 Python 语法编译同样隔离。编译产物经有界 stdout 返回，再只读挂载到新容器。仅支持单个 `.cpp`/`.cc`/`.cxx` 或 `.py`，不挂载项目、头文件、账号目录或 Docker socket。两个 tmpfs 均限空间并设 nosuid,nodev，`/work` 允许 exec，`/tmp` 为 noexec。

执行前探针核验 UID、capabilities、NoNewPrivs、根只读、仅回环网络，以及 cgroup v1/v2 的实际内存、swap、pids 和 CPU 限制，并编译运行固定可信 C++ 程序。限制不可核实（包括无法暴露 cgroup）、镜像缺失、工具链或引擎不可用均返回 unavailable，不继续执行。

隔离依赖 Linux 内核与容器引擎，不提供虚拟机级保证。清理失败按基础设施错误报告残留容器名。创建请求超时后守护进程仍可能完成创建，此时不启动程序并报告状态不确定的名称。可用 `docker ps -a --filter label=org.cpscore.managed=true` 检查并按名称移除残留。

## 样例检查

人工求和题与程序见[验证夹具](../fixtures/validation/README.md)。样例文件检查：

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --expected fixtures/validation/sample.out
```

多组 `--input` 与 `--expected` 按出现顺序配对，文件各限 16 MiB。按扩展名识别 Python/C++17，或设 `--language cpp|python`。使用 oracle 与校验器的差分检查：

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/wrong.py \
  --input fixtures/validation/sample.in \
  --validator fixtures/validation/validator.py \
  --oracle fixtures/validation/oracle.py \
  --save-dir .cpscore/counterexamples \
  --output .cpscore/wrong-report.json
```

校验器从 stdin 读输入，退出 0 接受、1 或 2 拒绝，其余失败或超限是工具故障。oracle 读取同一输入，以 stdout 给预期答案，须成功退出。两者同样隔离，可设 `--validator-language`、`--oracle-language`。`--oracle` 与 `--expected` 互斥。

## 固定种子随机差分

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/correct.cpp \
  --generator fixtures/validation/generator.py \
  --validator fixtures/validation/validator.py \
  --oracle fixtures/validation/oracle.py \
  --seed 20261109 --cases 20
```

生成器接受十进制位置参数 `SEED CASE_INDEX`，成功退出后使用 stdout。索引默认 0，可设 `--start-case`。输入先过校验器，再运行 oracle 和候选程序。自定义生成器须实际使用种子和索引，工具不保证外部实现确定性；附带生成器的相同参数输入哈希由集成测试检查。

## 比较策略

| 策略 | 显式参数 | 规则 |
| --- | --- | --- |
| 精确 | 默认或 `--compare exact` | stdout 字节完全一致，含空白与末尾内容 |
| token | `--compare tokens` | 按 ASCII 空白分词，逐 token 按字节一致 |
| 浮点 | `--compare float --abs-tol A --rel-tol R` | token 数相同，全部是有限的十进制/科学计数法数值，满足下述误差公式 |

浮点策略要求 `A`、`R` 均显式给出，有限且非负。每个候选值 `a` 与参考值 `b` 以 Python 的二进制双精度解析，使用

```text
abs(a - b) <= max(A, R * max(abs(a), abs(b)))
```

该公式为 math.isclose 的对称规则，不能默认等价于题目的其他误差公式。NaN、无穷、下划线、十六进制与混合文字 token 均拒绝。参考输出不合策略为 tool_error，候选不合策略为输出不一致。目前不支持任意外部比较器。

## 证据文件与结果解释

不匹配、非法输入及运行故障会尽可能保存证据目录，含以下内容。

- 实际使用的输入、参考输出、各程序的 stdout/stderr
- 编译时使用的源码快照和 SHA-256，而非结束时重新读取可能变化的原路径
- 各阶段退出码、超时/输出截断/内存状态、资源限制与环境
- 生成种子与索引、比较参数、每个文件哈希、`manifest.json` 内的 `replay_argv` 和正确转义的 `replay_shell`

生成器失败没有可称为反例的输入。manifest 的 `validated_differential_mismatch` 仅记录差分前提，`oracle_correctness: assumed_requires_review` 明示 oracle 仍需复核。重放使用保存的源码、输入和固定镜像 ID，要求同版本 CPscore 与镜像可用。

`replay.py` 按 runtime_root 导入包，无需 pip 安装，支持其他工作目录与 `python3 -I`。证据目录移动后直接运行 `python3 replay.py`，输入、源码和输出按脚本位置定位。运行时移动后加 `--runtime /新的运行时根目录`，其下须有 `cpscore/`。manifest 的绝对 replay_argv/replay_shell 仅对应原保存位置。

| 状态 | 含义 |
| --- | --- |
| `match` | 这一次输出匹配 |
| `candidate_mismatch` | 仅在校验器接受、oracle 与候选均成功而输出不同时产生，工具故障不产生此状态 |
| `sample_mismatch` | 与给定样例输出不同，没有成功 oracle 执行证据 |
| `unverified_mismatch` | 与 oracle 不同，但未用校验器确立输入合法性 |
| `candidate_compile_error` | 候选程序在已通过工具链探针的隔离环境中编译失败或超限 |
| `candidate_execution_failure` | 候选程序在记录的限制下退出失败、超时、内存或输出超限 |
| `invalid_input` | 输入被校验器拒绝，不运行 oracle 与候选程序 |
| `tool_error` / `config_error` | 工具或参数问题，不能判为算法错误 |
| `unavailable` | 没有可验证的隔离能力，不执行候选代码 |

顶层 completed 只表示流程完成，结论读 counts、cases 和 all_cases_matched。退出码：0 全部匹配或测量完成，1 候选观察或未确立前提的差异，2 参数/输入/工具/证据保存错误，3 隔离不可用。故障与候选观察并存时优先报工具错误。

## 性能观察

```sh
python3 -m cpscore bench \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --validator fixtures/validation/validator.py \
  --warmups 1 --repetitions 3 \
  --output .cpscore/bench.json
```

报告保存各次预热和测量、最小/中位/最大墙钟时间，以及宿主平台、CPU 数/负载、容器 kernel/CPU、编译器/Python、引擎/镜像 ID 和限额。计时从容器附着启动至退出，包含启动与管道收集开销，不是算法独占 CPU 用时，不能直接判 TLE、渐进复杂度或跨机性能。bench 不验答案，可先独立 check-candidate。

主要资源选项为 `--timeout`（默认 2 秒墙钟）、`--memory-mib`（默认 256）、`--cpus`（默认 1）、`--pids`（默认 64）、`--output-limit-kib`（默认 1024，stdout/stderr 合计）及 `--scratch-mib`（每个 tmpfs 默认 128）。也可用互斥的 `--output-limit-bytes` 精确设置输出限额。生成器、校验器、oracle 与候选程序使用相同运行限制。C++/Python 编译默认 30 秒，内存至少 1024 MiB，临时空间至少 256 MiB，产物最多 64 MiB，诊断与产物管道同样有界。可用 `--compile-timeout` 设置编译墙钟上限。

## 测试

```sh
python3 -m unittest tests.test_validation -v
```

默认运行比较策略、模拟故障、证据保存、命令限制和有界管道单元测试，跳过真实隔离测试，不代表真实编译或隔离通过。

已启动容器引擎并显式构建镜像后，运行真实集成测试。

```sh
CPSCORE_RUN_SANDBOX_TESTS=1 \
  python3 -m unittest tests.test_validation.SandboxIntegrationTests -v
```

可用 `CPSCORE_SANDBOX_ENGINE=docker|podman` 与 `CPSCORE_SANDBOX_IMAGE=...` 选择引擎/镜像。显式启用后隔离不可用将测试失败，不会静默跳过。它实际检查 C++ 和 Python 正确/错误程序、合法与非法输入、固定种子生成、oracle 故障、编译失败、超时、输出上限、容器清理、manifest 重放及性能测量。
