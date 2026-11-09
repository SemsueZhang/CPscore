# 新颖度审查与检索工具

`cp-novelty-review`独立给出A–E（含C+）新颖度初判，用户最终裁决。它与题面、程序、题解的正确性评分并列，不增加10分制对象，也不调用`score`给新颖度打分。日常只加载技能正文；本手册用于工具参数、检索失败及证据格式的按需查阅。

## 材料与输出

提供题面或idea、解法、约束、材料版本，以及可用的当前题来源和评审时点。新题查重可以把已公开同题判为A；回顾原场题时，该题自身发布、题解和转载只作为被评对象材料，比较此前独立工作。条件或解法不足时记录影响，不假造完整方法比较。

交付`novelty.md`和证据附件。报告包含等级或待定、最接近来源、覆盖与新增步骤、实际搜索和阅读范围、关键缺口。C+表示新颖度仍属C，但各项推导十分自然，推荐用于正式比赛，报告须附推导自然性的简短依据；E另附简短质量依据。除C+的正式比赛推荐外，这里不输出完整采用结论、赛制、难度或完整正确性评分。检索零命中不证明全球原创，HTTP成功不等于正文有效，工具分数与自动分组不代替原文核对。

## 入口

源码中执行`python3 -m cpscore novelty ...`。安装后，在实际技能目录定位`<技能目录>/scripts/cpscore.py`，替换为`python3 <技能目录>/scripts/cpscore.py novelty ...`；入口共享本项目的`.cpscore`，项目整体移动后仍能运行。每个子命令支持`--help`，不依赖原始仓库路径或某台机器的CLI登录。

普通网页搜索由宿主提供，随包工具负责CPRet、arXiv与来源读取；没有普通网页工具时如实记录覆盖缺口。安装和本地工具检查不调用模型，也不证明宿主模型已加载该技能。

## 检索与候选展开

查询建议写入UTF-8文件，避免Shell展开数学符号。公开服务接收查询文本，`--cpret-url`可切换到已有本地CPRet服务。

```sh
python3 -m cpscore novelty search cpret --query-file model-query.txt --output searches/cpret.json
python3 -m cpscore novelty search arxiv --query-file paper-query.txt --output searches/arxiv.json
python3 -m cpscore novelty index --record searches/cpret.json
python3 -m cpscore novelty inspect --record searches/cpret.json --ids <索引中的ID>
```

CPRet缺省跨页保留60条主候选和全部组内成员；`--limit`、`--page`与`--dedup`可调整数量、起始页和服务分组，不能丢弃分组成员。后续页失败时保留已取得候选，状态为partial。索引保留所有题名、来源和稳定ID，按完整原题URL生成ID，不自动合并不同题目。inspect可批量展开ID，返回原题、镜像链接及可用摘要，原题必要查询参数保留；完整响应在输出JSON中。

arXiv默认站内网页检索，英文查询覆盖数学模型与关键性质；`--arxiv-interface api`改用官方字段语法。缺省保留10条。本次请求前保持3秒间隔。接口失败可切另一接口或由宿主网页检索限定arxiv.org，分别保留结果，不把失败记作成功零命中。

## 来源与缓存

```sh
python3 -m cpscore novelty read --url https://example.org/paper --output sources/paper.json
python3 -m cpscore novelty read --source-file sources/paper.json --find 'Lemma 10' --output sources/lemma.json
python3 -m cpscore novelty read --source-file sources/paper.json --start-line 80 --output sources/next.json
```

读取器保存完整HTML、提取文本及链接，默认返回40个提取行、最多6000字符，长行按240字符拆分。行号是提取文本的位置；按next_line或关键词继续读取，截断与返回范围明确显示。`--max-lines`、`--max-chars`、`--context`可调整片段，`--include-links`显示前20个链接，全部链接留在文件。TeX数学脚本内容保留，未展示部分不算已读。PDF另存并提示需要宿主PDF阅读工具，不冒充已经读取正文。

默认在输出目录的`.cache`中复用24小时内的成功完整记录，`--cache-dir`指定批次共享目录，`--cache-ttl`调整期限，`--refresh`强制刷新。缓存键区分接口、查询、页码、深度、去重参数和服务地址；来源按完整URL区分。错误与partial不作为成功缓存。关键来源版本变化时按需要刷新，缓存不代替本轮评级。

## 证据与实际用量

每次搜索、索引、展开或读取自动写入同目录`calls.jsonl`，含状态、耗时、缓存命中、返回字节及证据位置；`--ledger`可指定共享文件。完整材料留在用户自己的输出目录，不作为CPscore内置题库。

```sh
python3 -m cpscore novelty usage --events run/events.jsonl --ledger searches/calls.jsonl --output run/usage.json
```

汇总器识别CLI的`turn.completed.usage`，输入、缓存输入、非缓存输入、输出与可用reasoning字段分开，子集不重复相加。其他宿主没有兼容日志时，模型用量保持未知，仍可汇总工具日志。中断或缺字段按实际范围显示partial或unavailable；工具耗时可能重叠，不当作墙钟，字节不换算为实际token或费用。可用`--wall-seconds`提供真实测得的墙钟时长。

## 接口来源与验证范围

- [CPRet官方项目](https://github.com/coldchair/CPRet)：相似题检索、公开演示与本地部署。
- [arXiv检索接口说明](https://info.arxiv.org/help/api/user-manual.html)：字段查询与请求间隔。

检索及证据工具从Auto-Insight的判题模块提取，常驻指令只保留新颖度部分。当前CPscore内验证范围见[迁移记录](novelty-migration.md)；工具和安装回归不等于A–E（含C+）准确率、全球原创性或模型费用收益的验证。
