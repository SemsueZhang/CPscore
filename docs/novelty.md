# 新颖度工具

`cp-novelty-review` 是新颖度打分技能，检索 CPRet、arXiv 和网页，核对相似题与方法后给出 A、B、C、C+、D、F 等级，以合适度和质量判断 C→C+、D→F，保存 `novelty.md` 和证据附件。随包命令负责检索、来源读取和用量汇总，普通网页搜索使用宿主工具。

## 调用技能

提供题面或 idea、解法、约束、材料版本和比较时点：

```text
$cp-novelty-review 为 statement.md 和 editorial.md 评定新颖度，保存 novelty.md 和检索附件。
```

新题查重与已公开题目比较，回顾原场题时比较此前独立工作。报告列出等级、最接近的已读来源、已有方法覆盖的步骤、新增思考、检索范围及缺口。等级单独保存，最终由用户裁决。

暂时没找到经核实的实质性相似先例，就按新颖，以D为基础评级，包括只有未核实线索的情况。仍执行约定检索并记录覆盖、失败和未读内容，不将失败冒充成功零命中。D/F是本轮判断，不宣称全球原创，检索缺口本身也不降低推导质量。

## C→C+、D→F：合适度与质量

C+ 保留 C 的先例关系与新增思考，F 保留 D 的新颖性要求；升级均须有合适度和质量的具体正面依据。C+ 的关键推导自然、独立考点有价值，因此初步推荐用于正式比赛。两者采用同一套标准，具体判据见 `cp-novelty-review` 的 `SKILL.md`。

合适度考察独立出题价值、逐步发现的线索、模板或论文依赖、替代做法对实际考点的影响以及可实现性。质量考察条件自然性、观察价值、推导连贯性、模型与算法协调程度及证明、实现负担。两项按现有材料作初步判断，无需指定比赛或目标选手，也不要求盲测。

报告分别给出两项判断，附发现路径、关键步骤的证据、最强负面解释和综合升级依据。读解法后重建的路径须标明；已知慢解和其他可通过算法也要比较。只因讲解顺畅、复杂度漂亮或实现简短，不能代替独立考点和整体协调的证据；难度高、证明长或缺少实测也不自动判差。

合适度或质量不足时保留基础等级 C/D，并说明具体影响。不确定推导思维链是否足够好，或关键证据不足以支持合适度、质量时，都判为“质量不足”，理由注明不确定的步骤或证据缺口，不另设待定状态。缺少盲测、未指定比赛或未实测本身不构成质量证据不足，已有材料和推导足以支撑判断即可。不能确认足够好是评级理由，不等于已经证实某个数学错误。

不能用多个优点抵消足以推翻升级的核心问题，A/B不因质量好而升为C+。C+和F的初步推荐不替代后续比赛安排、赛制、难度、区分度或做题预测，这些不成为本阶段新增评测要求。两项判断不写入正确性10分制报告。

## 交付结果

`novelty.md` 按“结论—材料与范围—先例比较—合适度与质量—证据与缺口”组织。对C/D都记录升级核验，包括未升为C+/F的情况。暂未找到相似先例按新颖，不能确认思维链足够好按质量不足，不用“待定”替代评级。

最终回复给出等级、合适度与质量结论、决定性理由及报告和证据附件链接。完整检索响应、查询和阅读范围放附件，报告保留可追溯的关键证据。

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
