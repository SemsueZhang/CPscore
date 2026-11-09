# 隔离运行与验证证据

`check-candidate` 和 `bench` 提供可选的运行证据，不会修改评分。有限次样例或随机测试通过不构成正确性证明。差分不一致依赖输入校验器与可信 oracle 的正确性，仍需人工复核。

## 准备隔离环境

需要 Linux 容器的 Docker 或 Podman。macOS 可使用已启动的 Docker Desktop 或 Podman VM。原生 Windows 当前返回 `unavailable`，可在 Linux/WSL2 中使用。本工具不启动守护进程、不安装运行环境、不自动拉取镜像，不会降级为宿主机裸跑，也不使用未经验证的 `sandbox-exec`。

在仓库根目录显式构建只含 Python 3 与 C++17 工具链的镜像。

```sh
docker build -f Dockerfile.runner -t cpscore-runner:local .
# 或：podman build -f Dockerfile.runner -t cpscore-runner:local .
```

构建依赖 Debian 软件源，需要网络。运行检查本身使用已存在的本地镜像，解析并固定镜像 ID，容器创建加 `--pull=never`。自定义 `--image` 应是可信、无凭据的运行镜像，必须含 `python3`、`g++` 与 `/bin/sh`。记录镜像 ID 以辨识具体环境，不把可变 tag 当可复现依据。

每个编译或运行阶段都创建独立的临时容器，并施加以下限制。

- 网络为 `none`，只读根文件系统，UID/GID 为 `65534:65534`
- 丢弃所有 Linux capabilities，开启 `no-new-privileges`，保留引擎默认系统调用过滤
- 有限的 CPU 配额、内存与 swap、进程数、单文件大小、文件描述符数、临时文件空间
- 源码与已编译程序只读挂载，不向不可信程序提供任何可写宿主机挂载
- stdin、stdout、stderr 经过有界管道，stdout/stderr 合计超限或墙钟超时会停止附着客户端并强制移除容器

C++ 编译也在容器中进行。可执行文件从容器的有界 stdout 返回，随后以只读文件用于新容器。Python 的语法编译也在隔离容器中完成。工具只支持单个 `.cpp`/`.cc`/`.cxx` 或 `.py` 源文件，不自动挂载项目目录、头文件、账号目录或 Docker socket。

`/work` 的 tmpfs 显式允许 `exec`，供可信编译器探针执行刚编译的程序，避免依赖引擎对 tmpfs 的默认挂载选项。`/tmp` 保持 `noexec`，两个 tmpfs 均限制空间并设置 `nosuid,nodev`。

开始执行候选程序前，真实探针检查容器的 UID、capabilities、`NoNewPrivs`、根挂载只读、仅有回环网络接口，并读取 cgroup v1/v2 的实际内存、swap、pids 与 CPU 配额。探针还编译并运行一个固定的可信 C++ 程序。限制不可核实、镜像缺失、工具链失效或引擎不可用都会返回 `unavailable`。不会接受“引擎忽略了限制，但仍继续执行”的情况。需要读 cgroup 状态的严格探针可能拒绝某些无法暴露这些信息的引擎配置。

这是依赖 Linux 内核与容器引擎的进程隔离，不提供虚拟机级安全保证。处理高风险样本宜使用专用 VM 和 rootless 引擎。容器异常清理失败会变为基础设施错误，并输出待移除容器名，不能当成功或算法错误。创建容器请求超时存在守护进程稍后才完成创建的竞态，此时不会启动程序，会明确输出状态不确定的容器名。可用 `docker ps -a --filter label=org.cpscore.managed=true` 检查本工具创建的容器，并按报告中的名称移除残留。

## 样例检查

仓库附带人工编写的求和题，范围、正确程序、错误程序、校验器与 oracle 见 [fixtures/validation](../fixtures/validation/README.md)。只检查样例文件可使用以下命令。

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --expected fixtures/validation/sample.out
```

多组样例重复传入 `--input` 与 `--expected`，按各自出现的顺序一一配对。默认按字节精确比较，包括空格、换行和末尾内容。`.py` 自动识别为 Python，C++ 扩展名自动识别为 C++17，也可显式设置 `--language cpp|python`。输入与预期文件各限 16 MiB。

只使用预期输出时，不一致标为 `sample_mismatch`，不会声称已经运行 oracle。需要确立合法输入与成功 oracle 运行的差分证据时使用以下命令。

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/wrong.py \
  --input fixtures/validation/sample.in \
  --validator fixtures/validation/validator.py \
  --oracle fixtures/validation/oracle.py \
  --save-dir .cpscore/counterexamples \
  --output .cpscore/wrong-report.json
```

输入校验器从 stdin 读取输入，退出 0 表示接受。退出 1 或 2 表示拒绝，其他失败或资源超限按工具故障处理。oracle 从 stdin 读取相同输入，stdout 为预期答案，必须成功退出。校验器和 oracle 同样执行于隔离容器，分别可设置 `--validator-language`、`--oracle-language`。`--oracle` 与 `--expected` 互斥。

## 固定种子随机差分

```sh
python3 -m cpscore check-candidate \
  --candidate fixtures/validation/correct.cpp \
  --generator fixtures/validation/generator.py \
  --validator fixtures/validation/validator.py \
  --oracle fixtures/validation/oracle.py \
  --seed 20261109 --cases 20
```

生成器收到两个十进制位置参数 `SEED CASE_INDEX`，stdout 为输入，成功退出后才使用它。索引默认从 0 开始，可用 `--start-case` 指定。生成的输入必须先通过校验器，再运行 oracle 和候选程序。自定义生成器应真正使用给定种子与索引，工具不能保证任意外部生成器的确定性。附带的生成器使用独立的确定性随机实例，集成测试会检查相同参数产生相同输入哈希。

生成器、校验器、oracle 或比较策略的故障都不会产生 `candidate_mismatch`。该状态只有在输入被校验器接受、oracle 成功、候选程序成功且输出不同的情况下返回。即使如此，manifest 也明确记录 `oracle_correctness: assumed_requires_review`，以免把机械差分当作已完成的数学反驳。

## 比较策略

| 策略 | 显式参数 | 规则 |
| --- | --- | --- |
| 精确 | 默认或 `--compare exact` | stdout 字节完全一致 |
| token | `--compare tokens` | 按 ASCII 空白分词，逐 token 按字节一致 |
| 浮点 | `--compare float --abs-tol A --rel-tol R` | token 数相同，全部是有限的十进制/科学计数法数值，满足下述误差公式 |

浮点策略要求 `A`、`R` 均显式给出，有限且非负。每个候选值 `a` 与参考值 `b` 以 Python 的二进制双精度解析，使用

```text
abs(a - b) <= max(A, R * max(abs(a), abs(b)))
```

它是 `math.isclose` 的对称相对误差规则。题目若采用其他公式，应使用适配的验证机制，不能默认等价。`NaN`、无穷大、下划线、十六进制与混合文字 token 均不接受。参考输出不符合浮点策略属于 `tool_error`，候选输出不符合策略属于输出不一致。当前没有执行任意外部比较器的接口。

## 证据文件与结果解释

不匹配、非法输入及运行故障会尽可能保存证据目录，含以下内容。

- 实际使用的输入、参考输出、各程序的 stdout/stderr
- 编译时使用的源码快照和 SHA-256，而非结束时重新读取可能变化的原路径
- 各阶段退出码、超时/输出截断/内存状态、资源限制与环境
- 生成种子与索引、比较参数、每个文件哈希、`manifest.json` 内的 `replay_argv` 和正确转义的 `replay_shell`

生成器未成功产生输入时没有可声称为反例的输入文件，直接报告工具故障。`manifest.json` 的 `validated_differential_mismatch` 只说明满足输入校验和成功 oracle 执行的差分前提，不证明 oracle 自身正确。重放命令使用保存的源码和输入、固定镜像 ID。需要同一代码版本的 CPScore 及同一镜像仍在本地可用。

目录内的 `replay.py` 会主动导入记录的 `runtime_root`，因此通过已安装 skill 的临时 bootstrap 调用、没有 `pip install`、在其他工作目录或用 `python3 -I` 运行时也能找到原来的运行时。移动证据目录后，在新目录运行 `python3 replay.py`，源码、输入和重放输出目录会按脚本位置重新定位。移动 CPScore 运行时后，使用 `python3 replay.py --runtime /新的运行时根目录`，该目录下应有 `cpscore/`。manifest 原有绝对路径的 `replay_argv`/`replay_shell` 仅对应保存时的位置。

| 状态 | 含义 |
| --- | --- |
| `match` | 这一次输出匹配 |
| `candidate_mismatch` | 合法输入上与成功运行的 oracle 不一致，需审查 oracle |
| `sample_mismatch` | 与给定样例输出不同，没有成功 oracle 执行证据 |
| `unverified_mismatch` | 与 oracle 不同，但未用校验器确立输入合法性 |
| `candidate_compile_error` | 候选程序在已通过工具链探针的隔离环境中编译失败或超限 |
| `candidate_execution_failure` | 候选程序在记录的限制下退出失败、超时、内存或输出超限 |
| `invalid_input` | 输入被校验器拒绝，不运行 oracle 与候选程序 |
| `tool_error` / `config_error` | 工具或参数问题，不能判为算法错误 |
| `unavailable` | 没有可验证的隔离能力，不执行候选代码 |

多例报告的顶层 `completed` 只表示检查流程完成，具体结论需读取 `counts`、`cases` 与 `all_cases_matched`。CLI 退出码 0 表示全部样例匹配或性能测量完成，1 表示候选相关观察或未确立前提的差异，2 表示参数、输入、工具或证据保存错误，3 表示隔离不可用。没有任何状态自动扣分。基础设施或工具故障与候选观察同时存在时，退出码优先报工具错误。

## 性能观察

```sh
python3 -m cpscore bench \
  --candidate fixtures/validation/correct.cpp \
  --input fixtures/validation/sample.in \
  --validator fixtures/validation/validator.py \
  --warmups 1 --repetitions 3 \
  --output .cpscore/bench.json
```

报告保存每次预热和测量结果、最小/中位/最大墙钟时间，并记录宿主平台、CPU 数与负载、容器 kernel/CPU 型号、编译器/Python 版本、引擎/镜像 ID 和资源限制。测量从容器附着启动至退出，包含容器启动和管道收集开销，不是算法独占的 CPU 用时。不能直接用它判 TLE、推出渐进复杂度或跨机器性能结论。`bench` 不验证答案正确性，可先独立运行 `check-candidate`。

主要资源选项为 `--timeout`（默认 2 秒墙钟）、`--memory-mib`（默认 256）、`--cpus`（默认 1）、`--pids`（默认 64）、`--output-limit-kib`（默认 1024，stdout/stderr 合计）及 `--scratch-mib`（每个 tmpfs 默认 128）。也可用互斥的 `--output-limit-bytes` 精确设置输出限额。生成器、校验器、oracle 与候选程序使用相同运行限制。C++/Python 编译默认 30 秒，内存至少 1024 MiB，临时空间至少 256 MiB，产物最多 64 MiB，诊断与产物管道同样有界。可用 `--compile-timeout` 设置编译墙钟上限。

## 测试与本次环境记录

普通测试明确区分单元测试和真实隔离集成。

```sh
python3 -m unittest tests.test_validation -v
```

默认执行比较策略、模拟工具故障、证据保存、命令限制与有界可信管道的单元测试，真实隔离测试显示为跳过。模拟测试不代表真实 C++/Python 编译或隔离验证通过。

已启动容器引擎并显式构建镜像后，运行真实集成测试。

```sh
CPSCORE_RUN_SANDBOX_TESTS=1 \
  python3 -m unittest tests.test_validation.SandboxIntegrationTests -v
```

可用 `CPSCORE_SANDBOX_ENGINE=docker|podman` 与 `CPSCORE_SANDBOX_IMAGE=...` 选择引擎/镜像。显式启用后隔离不可用将测试失败，不会静默跳过。它实际检查 C++ 和 Python 正确/错误程序、合法与非法输入、固定种子生成、oracle 故障、编译失败、超时、输出上限、容器清理、manifest 重放及性能测量。

2026-11-09 在本次 macOS 宿主上，Docker CLI 存在但 Docker daemon socket 不存在，Podman 未安装。真实 `check-candidate` 返回 `unavailable`、退出码 3，候选代码没有编译或运行。显式启用集成测试也在初始化阶段因该原因失败，真实集成尚未完成。普通测试中的模拟用例通过不能替代这项缺失的集成证据。
