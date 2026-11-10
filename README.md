# CPscore

算法竞赛题审查与打分工具，由智能体分析材料并记录证据，Python 校验、算分和生成报告。需要 Python 3.10+，核心仅依赖标准库。

| 技能 | 内容 | 交付 |
| --- | --- | --- |
| `cp-statement-review` | 定义、输入输出、约束、边界、样例 | 10分制报告 |
| `cp-solution-review` | 算法、正确性、复杂度、实现 | 10分制报告 |
| `cp-editorial-review` | 断言、推理、证明、复杂度 | 10分制报告 |
| `cp-data-review` | 错解漏网、子任务得分、数据强度 | 10分制报告 |
| `cp-novelty-review` | 检索并核对相似题与论文 | `novelty.md`，A/B/C/C+/D/F |
| `cp-problem-review` | 汇总已有审查，评价解法空间和整体设计 | `problem.md`，三档结论及修改意见 |
| `cp-contest-review` | 结合具体比赛要求评价题目组合 | `contest.md`，三档结论及修改意见 |
| `cp-performance-predict` | 预测路线、障碍、耗时和得分 | `performance.md`，无须盲测 |

10分制按独立根因扣分：Fatal −10、Major −3、Minor −1，最低0分。9～10分推荐、6～8分合格、0～5分不合格，未完成或有未决Fatal时不能按高分推荐。证明缺漏与算法错误分别核验，疑点不扣分。联合正确性审查按根因合并扣分。

题目和比赛总评按所有审查结果取最低档。新颖度A/B对应不合格、C/D合格、C+/F推荐。原做法不适合竞赛时，已核验的更简单竞赛做法只允许该项判为合格，并提出修改意见，其他不合格项仍保留。

## 安装与调用

从完整源码目录安装到已有题目项目：

```sh
python3 -m cpscore install --project /absolute/path/to/problem --harness codex
python3 -m cpscore check --project /absolute/path/to/problem --harness codex
```

`--harness` 支持 `codex`、`claude-code`、`opencode-deepseek`，省略则全部安装。宿主中按技能名调用，例如：

```text
$cp-data-review 结合题面、题解、std和suite.json评估数据，保存review.json并生成review.md。
$cp-problem-review 综合当前题目材料和全部审查，生成problem.md。
$cp-contest-review 按具体比赛要求和逐题总评生成contest.md。
$cp-performance-predict 按目标选手和比赛条件生成performance.md。
```

## 工具入口

从源码运行，或先执行 `python3 -m pip install -e .`。智能体填写记录后生成报告：

```sh
python3 -m cpscore init-report --scope statement,solution,editorial,data -o review.json
python3 -m cpscore validate review.json
python3 -m cpscore score review.json -o review.md
python3 -m cpscore score review.json --format json -o scored.json
python3 -m cpscore validate scored.json --scored
python3 -m cpscore assess init problem -o problem.json
python3 -m cpscore assess report problem.json -o problem.md
```

新记录不会自动通过。正确性协议为3.0，旧1.0/2.0报告需用 `migrate old.json -o new.json` 原样归档并重新核验。总评与预测使用独立输入格式。

## 文档与验证

- [安装与宿主调用](docs/harnesses.md)：更新、卸载、可移动安装和模型调用脚本。
- [评分协议](docs/protocol.md)：根因、证据、完成度和迁移。
- [程序运行](docs/validation.md)：隔离、反例保存、输出比较和性能测量。
- [数据强度](docs/data.md)：错解分析、冻结实测和计分规则。
- [新颖度](docs/novelty.md)：先例关系、合适度与质量、检索和证据工具。
- [总评与预测](docs/assessment.md)：三档汇总、比赛要求和预测报告格式。

`cpscore/` 存放工具，`skills/` 存放技能，`tests/` 与 `fixtures/` 存放回归测试及夹具。运行 `python3 -m unittest discover -s tests -v`。
