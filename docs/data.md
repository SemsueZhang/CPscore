# 测试数据强度

`cp-data-review` 以真实错误机制和原数据实测为依据，评价一套测试数据能否筛掉应当失败的程序。共用正确性协议3.0的10分、根因去重、证据版本、完成度与修复规则，新增可选 `data` 对象，不改变旧三对象报告。新颖度仍独立评级。

## 分级规则

| 情况 | rule_id | 扣分 |
| --- | --- | ---: |
| 核心模型完全错误、没有依据的乱搞，或已证实不能满足全数据资源要求的算法，获得本不应获得的计分单元/分数 | `data_gross_escape` | 10 |
| 算法主干合理但有较小逻辑或实现错误，通过大部分本应检验该机制的计分单元 | `data_local_escape` | 3 |
| 极细边界遗漏、很高明且难以区分的乱搞在部分点/组漏网，影响有限 | `data_subtle_escape` | 1 |
| 已确认实际计分输入违反题面合法域 | `data_invalid_input` | 10 |
| 已确认计分答案错误，实际改变选手得分 | `data_bad_answer` | 10 |
| checker/interactor 已确认接受非法答案或拒绝合法答案，实际改变判定 | `data_bad_judge` | 10 |
| 计分权重/依赖实现与既定规则不符 | `data_bad_scoring` | 实质颠倒通过/得分为10，重要局部偏差为3，有限局部偏差为1 |

“不该过”按题目和子任务规则判断。小规模暴力通过给它保留的部分分、正确但较慢且明确允许的算法通过、应适用点之外的通过均不扣分。严重错解通过一个合法设计中本来不要求检出它的点，不自动构成Fatal。须说明该计分单元应排除什么，以及实际获得的额外收益。只有在题目本身明确规定的正确性/得分条件下判断，不由评审临时提高要求。

“大部分”默认指超过半数有针对性义务的计分单元，记录分子、分母和选择依据。普通逐点计分按点，捆绑按实际组及依赖，权重不同时同时列出获得分数与总分，优先按正式计分利益解释。不能事后只挑会通过的点做分母。轻微错误未达大部分时，若是有实际有限影响的漏网可记Minor；没有具体额外收益则不扣。不得因修复容易降级，也不因候选名字、代码长度或“用了随机”直接定级。

随机/启发式候选固定种子，多次测试保留全部尝试和成功次数。一次可复现的实际漏网可作具体观察，不能宣称稳定通过。复杂度错误须确认实际退化结构、操作量及题目资源要求，结合可信目标环境校准，且原集未将它排除。仅有渐进上界较差或本机一次耗时，不足以证明是假解；资源结论保留环境和限制。

## 证据与去重

每个漏网问题需要两类证据：候选确实错误的合法反例/有效反驳或经校准的资源违例，以及它在原冻结数据上实际取得不应获得成绩的记录。输入合法、答案可靠、判定器适用分别核对，不把参考程序AC当作正确性证明。既有真人错解可复用，但公开WA标签本身不能代替本轮适用性和具体错因确认。

同一缺失边界/结构/规模导致的多个候选与测试点，用同一 `root_cause_id`，以最高已确认级别扣一次。相互独立且需不同修复的数据缺口可分别扣分。同一数据的错误答案导致checker误判等连锁后果不重复扣。确认Major/Minor必须填 `impact`，写明范围、额外得分和轻重依据。

候选未证错、原集未跑完、编译失败、答案分歧、checker不匹配或环境不可用不构成漏网扣分。用 `suspected` 和具体 `evidence_gap` 保存疑点，相关覆盖为blocked/unchecked。重要候选未运行不能把 `execution` 标为checked。不因没有找到漏网给出数据完备保证，也不因暂未找到反例扣分。

五项覆盖为：`integrity` 原集版本/合法性/答案，`judging` 实际判定规则及必要校准，`mechanisms` 已分析的错误机制和允许路线，`execution` 原集实测及资源条件，`scoring` 点/组/依赖/允许分数与根因归并。完成指本轮约定范围完成，不要求穷举所有错误程序；报告明确候选来源和覆盖边界。

## 冻结数据实测入口

普通批处理使用 `test-data`。保留用户原数据和答案，工具先保存逐文件哈希及独立快照，运行validator与参考程序核对原答案，再运行候选。工具不替换原答案，不添加新测试点，不自动判定错解或扣分。原集很大时沿用原平台/已有rbx配置评测并引用原生报告，无需改造成此格式。

套件路径相对JSON所在目录，示例如下：

```json
{
  "version": "1.0",
  "reference": "std.cpp",
  "validator": "validator.cpp",
  "comparison": {"mode": "tokens"},
  "cases": [
    {"id": "small", "input": "data/01.in", "answer": "data/01.ans"},
    {"id": "large", "input": "data/02.in", "answer": "data/02.ans"}
  ],
  "groups": [
    {"id": "partial", "points": 20, "cases": ["small"]},
    {"id": "full", "points": 80, "cases": ["large"], "depends_on": ["partial"]}
  ],
  "candidates": [
    {"id": "quadratic", "source": "wrong/quadratic.cpp", "mechanism": "实际二重循环的规模退化", "allowed_groups": ["partial"]}
  ]
}
```

`groups`省略时每点独立计1分，组ID取点ID。显式组采用组内全过及依赖全过才得分。每个候选必须明确填写允许取得的组，`[]`表示按已核实规则不应得任何组；它是审查者输入，工具不认证该判断。`unexpected_points`只表示超出这个声明的观察分，不等于自动确认数据漏洞。复杂计分、优化和交互规则请用原正式计分器。

```sh
python3 -m cpscore test-data suite.json --output-dir evidence/original --timeout 2 --memory-mib 256
python3 -m cpscore init-report --scope data --output review.json
python3 -m cpscore validate review.json
python3 -m cpscore score review.json --format json --output scored.json
python3 -m cpscore score review.json --output review.md
```

执行继承CPscore现有Docker/Podman隔离，镜像与准备见[运行工具](validation.md)。单文件C++17/Python，比较模式仅exact/tokens/float，float必须给定 `abs_tolerance`、`rel_tolerance`。多解、特殊checker、交互及部分输出计分不得用单答案比较替代。默认限制含启动开销，不能直接当作官方CPU限时。

输出目录必须不存在。`suite.json`、`files.json`及 `frozen/` 保存可迁移的配置与原始字节，`reference.json`、`candidate-*.json` 保留逐点执行和环境，`summary.json` 给出完成状态、逐点通过数/率、组状态、允许组、额外通过组与分数。CE/未完成保持分数和通过率为null，不能当作零分检出或存活。资源失败记录为本环境的失败观察，不自动升格官方TLE/MLE。返回0代表执行证据完整，即使候选全部漏网；返回3表示不完整。错误配置返回2。

另行验证候选错误时可用 `check-candidate` 和已有定向generator/oracle/validator；按固定参数与种子重现，生成结果放独立反例目录。构造小实例时可独立暴力核对参考。修订生成器、checker或数据集后建立新快照，原分数及证据保留，修复成绩另算。交付候选与反例生成源码、复现命令、必要许可及轻量报告，大型输入/答案/二进制留证据目录。运行工具无模型调用，模型用量如需统计只记录实际usage。

## 接入原因与验证范围

2026-11-10从Auto-Insight的`problem-data`迁入错解分析、合法反例确认和执行反馈，复用现有隔离执行与10/3/1扣分器。已有rbx项目沿用原生报告，无须重复安装rbx或testlib。旧三对象格式兼容，数据仅在scope包含data时初始化。当前安装清单格式4兼容旧格式1/2/3，见[安装手册](harnesses.md)。

回归覆盖算分、冻结字节、部分分、依赖、故障分类和三宿主升级。模拟运行器只验证工具逻辑，不构成真实漏网证据。本机此前缺少Docker服务及Podman，实际调用正确返回未完成，尚未验证真实容器候选执行或模型审查效果。环境就绪后运行：

```sh
CPSCORE_RUN_CONTAINER_TESTS=1 python3 -m unittest tests.test_data.DataContainerTests -v
```
