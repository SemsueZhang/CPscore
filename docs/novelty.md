# 新颖度工具

`cp-novelty-review` 是新颖度打分技能，检索 CPRet、arXiv 和网页，核对相似题与方法后给出 A、B、C、C+、D、F 等级，以合适度和质量判断 C→C+、D→F，保存 `novelty.md` 和证据附件。随包命令负责检索、来源读取和用量汇总，普通网页搜索使用宿主工具。

## 调用技能

提供题面或 idea、解法、约束和比较时点：

```text
$cp-novelty-review 为 statement.md 和 editorial.md 评定新颖度，保存 novelty.md 和检索附件。
```

新题查重与已公开题目比较，回顾原场题时比较此前独立工作。每题独立给出结论、先例比较、质量分析和判据来源。记录材料文件或链接、版本日期即可，默认不计算或反复校验哈希。

## 先例关系

A表示核心任务、关键约束和所需思考实质等价，B表示已有方法经常规调整覆盖整解。判C要指明先例替代了本题哪个非平凡关键步骤、条件如何对应，以及仍需独立发现什么重要内容。只共享图类、贪心路径、双指针、DP或数据结构不构成C，目标不同也不妨碍核实关键复用。

没有核实到实质先例时，以D为基础关系，写“本轮检索按新颖评定”。有价值的新算法另行说明，整题已有A/B覆盖时按最直接关系评级。

## C→C+、D→F：合适度与质量

C+保留C的先例关系，F保留D的新颖性关系。合适度与质量均通过时，C→C+、D→F，否则保留C/D。A/B的等级保持不变，具体问题另行说明。C+与F采用同一套质量标准，只因先例关系不同而区分，不能用质量高低解释二者差别。

合适度考察独立考点、发现线索、必要知识和可实现性。质量考察条件自然性、观察价值、推导连贯性，以及证明与实现负担。重建“初始尝试—障碍—关键观察—转化与证明—可实现算法”，围绕影响判断的具体步骤展开分析。完整判据见 `cp-novelty-review` 的 `SKILL.md`。

发现错误时，明确错误断言和影响范围，检查上下文并实际尝试局部修复。修复后核心结论、算法和复杂度仍成立的，按修复后的方法评价。修复若需要新引理、改变算法或新增条件，应说明新增推导。结论被反驳时给出具体推导或反例。

区分证明文字、数学结论、算法和题目质量。局部证明错误不自动推出算法错误或拒绝升级。核对已知替代路线，评价能够解决本题的实际方法。拿不准的关键步骤先补推导或针对性阅读，不以自身未完成的工作替代题目判断，也不把未建立的断言写成已被反驳。

分别给出合适度和质量的明确结论，用具体观察、推导和实现成本解释评级。保留C/D时说明哪一步发现缺少线索、哪项条件不协调或负担与收益失衡。难度高、代码长、未指定比赛、缺少盲测或实测本身不判差。

## 交付结果

每题独立成篇。默认在 `novelty.md` 中逐题重复完整结构，多题也各有自己的结论、分析与来源。用户指定分文件时沿用同一结构。每题固定先写“结论”，再写“题目分析”，其下分“先例比较”和“质量分析”，最后写“判据来源”。模板以 `SKILL.md` 为准。

结论先给等级和决定性理由。题目分析简述模型与解法，展开影响评级的先例关系、关键推导、独立考点和实现成本，常规步骤概述即可。判据来源按编号给出材料和相关段落，正文就近引用，末尾只列出处，不重述分析。

不要防御性写作。直接作出判断并解释原因，不用“证据不足”等泛化措辞或免责段落代替分析，不强制凑缺点、列风险清单或逐项填表。正向判断是明确陈述评价，确认的问题照实写明。

依据就地说明，同一内容只写一次。推导、必要的小检验和评价融入对应分析，不分别建账或增加章节。已有论证直接引用，只有影响评级的具体疑点才补证或检验，结果一句话说明对象、覆盖和发现。报告直接链接工具已有文件，不手工复述响应、重建日志或为常规步骤另做附件。

最终回复按题给出等级、决定性理由和报告链接。新颖度报告与正确性10分制独立保存，具体比赛安排、难度与做题预测由对应任务处理。

## 搜索与展开候选

在源码目录运行以下命令。安装后将 `python3 -m cpscore` 替换为 `python3 <实际技能目录>/scripts/cpscore.py`。查询写入 UTF-8 文件：

```sh
python3 -m cpscore novelty search cpret --query-file model-query.txt --output searches/cpret.json
python3 -m cpscore novelty search arxiv --query-file paper-query.txt --output searches/arxiv.json
python3 -m cpscore novelty index --record searches/cpret.json
python3 -m cpscore novelty inspect --record searches/cpret.json --ids CANDIDATE_ID
```

CPRet 默认保留 60 条主候选及全部组内成员。`--limit`、`--page`、`--dedup` 调整数量、起始页和服务分组，`--cpret-url` 切换服务地址。先读完整索引，再用 `inspect --ids` 批量展开相关候选。后续页失败时，已取得结果保留为 `partial`。

arXiv 默认使用网页检索并保留 10 条，`--arxiv-interface api` 切换至官方字段查询。查询围绕模型、关键观察和核心转化，接口失败时切换接口或使用宿主网页搜索。

## 读取来源与缓存

```sh
python3 -m cpscore novelty read --url https://example.org/paper --output sources/paper.json
python3 -m cpscore novelty read --source-file sources/paper.json --find 'Lemma 10' --output sources/lemma.json
python3 -m cpscore novelty read --source-file sources/paper.json --start-line 80 --output sources/next.json
```

读取器保存完整 HTML、提取文本和链接，默认展示 40 行、最多 6000 字符，长行按 240 字符拆分。用 `next_line` 或 `--find` 继续阅读，`--max-lines`、`--max-chars`、`--context` 调整片段，`--include-links` 展示前 20 个链接。PDF 另存后交由宿主 PDF 工具读取。评级时核对相关正文、方法和适用条件，未展示内容按未读处理。

成功完整记录默认在输出目录的 `.cache` 缓存 24 小时。`--cache-dir` 指定共享目录，`--cache-ttl` 调整期限，`--refresh` 强制刷新。错误和 partial 记录不作为成功缓存。

## 汇总用量

搜索、索引、展开和读取会向同目录 `calls.jsonl` 写入状态、耗时、缓存命中、返回字节及证据位置，`--ledger` 可指定共享日志。

```sh
python3 -m cpscore novelty usage --events run/events.jsonl --ledger searches/calls.jsonl --output run/usage.json
```

汇总器读取兼容的 `turn.completed.usage`，分别列出输入、缓存输入、非缓存输入、输出和可用 reasoning 用量。缺失模型日志时用量显示未知，部分日志显示 partial。`--wall-seconds` 可提供实测墙钟时间，工具字节及耗时另列。
