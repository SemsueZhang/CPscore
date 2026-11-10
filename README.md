# CPscore

CPscore 是算法竞赛题的打分智能体，提供四个可独立调用的技能：

| 技能 | 打分内容 |
| --- | --- |
| `cp-statement-review` | 题面定义、输入输出、约束、边界和样例 |
| `cp-solution-review` | 程序算法、正确性、复杂度和实现 |
| `cp-editorial-review` | 题解断言、推理、证明和复杂度 |
| `cp-novelty-review` | 检索相似题与论文，给出 A、B、C、C+、D、F 等级，以合适度和质量作为 C→C+、D→F 的重要判据 |

前三项采用 10 分制，由智能体填写核验记录，再由 Python 工具去重、算分并生成报告。每个已确认的 Fatal 根因扣 10 分，Minor 扣 1 分，最低 0 分。同根因只扣一次，总分按根因合并计算。新颖度单独评级。

## 审查流程与交付

按用户指定范围选择技能，先读取当前材料和版本，再核验并记录证据。多个正确性对象共同审查时使用同一份 `review.json`，各技能只更新自己负责的对象，最后统一生成结果。新颖度在独立报告中先判定先例关系，再对 C/D 核验合适度与质量，决定是否升为 C+/F。

| 审查部分 | 交付结果 |
| --- | --- |
| 题面、程序、题解 | `review.json` 核验记录、工具生成的 `scored.json` 和 `review.md`，包含分数、合格判定、覆盖完成度及问题证据 |
| 新颖度、合适度与质量 | `novelty.md` 和检索证据附件，包含等级、先例比较、合适度与质量结论、升级或不升级的依据 |

暂时没找到相似先例，按新颖，以 D 为基础评级。C+ 和 F 要求合适度、质量均有充分证据，不确定推导思维链是否足够好或支持证据不足，就按质量不足，保留 C/D。检索缺口与质量证据不足分别记录，不用“待定”替代这两项判断。该质量规则不改变正确性评分的证据要求，未确认错误不据此扣分。

最终回复给出已审查部分的结论、决定性理由和报告链接。完整问题、推导和检索记录留在报告及附件中。

## 安装与调用

需要 Python 3.10+。在完整源码目录中，为已有项目安装技能：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
```

`--harness` 支持 `codex`、`claude-code`、`opencode-deepseek`，省略时安装全部适配。各宿主的调用方式见[安装与调用](docs/harnesses.md)。

例如在 Codex 中调用：

```text
$cp-solution-review 为 statement.md 对应的 solution.cpp 打分，保存 review.json 并生成 review.md。
```

## 命令行

从源码运行，或先执行 `python3 -m pip install -e .`。核心工具仅依赖 Python 标准库。

```sh
python3 -m cpscore init-report --scope statement,solution,editorial --output review.json
```

按[打分规则与报告格式](docs/protocol.md)填写材料版本、核验项和问题证据，再校验并生成结果：

```sh
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --output review.md
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore validate scored.json --scored
```

新建报告的分数为 `null`。结果分别给出分数、覆盖完成度 `completion` 和合格判定 `qualification`。旧版报告使用 `python3 -m cpscore migrate old.json -o new.json` 迁移后重新核验。

## 使用文档

- [安装与调用](docs/harnesses.md)：宿主路径、安装、更新、卸载及调用脚本。
- [打分规则与报告格式](docs/protocol.md)：核验项、分级、证据和算分规则。
- [程序运行工具](docs/validation.md)：样例检查、差分验证、反例保存和性能测量。
- [新颖度工具](docs/novelty.md)：CPRet、arXiv、来源读取、缓存和用量汇总。

`cpscore/` 存放工具代码，`skills/` 存放技能，`tests/` 和 `fixtures/` 存放测试及数据。运行测试：`python3 -m unittest discover -s tests -v`。
