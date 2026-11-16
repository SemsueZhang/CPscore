# 共享算法知识目录

唯一发布数据位于 `resources/algorithm-catalog/catalog.json`，同目录的 `catalog.py` 提供查询、校验和更新。八个 Skill 按需使用同一目录，不各自保存副本。目录保留原有知识名称、别名、分类和来源，并在同一文件附加洛谷标签映射、算法知识门槛参考与公开题目标签样本。没有题解、实现或选手能力分数，不新建第二份知识库。

## 共享与查询

在 CPscore 根目录执行：

```sh
export CPSCORE_CATALOG="$(pwd)/resources/algorithm-catalog"
python3 "$CPSCORE_CATALOG/catalog.py" search "树状数组"
python3 "$CPSCORE_CATALOG/catalog.py" search "Binary Indexed Tree"
python3 "$CPSCORE_CATALOG/catalog.py" get oiwiki.ds.fenwick
python3 "$CPSCORE_CATALOG/catalog.py" search --category "数学/数论" --limit 20 --offset 0
python3 "$CPSCORE_CATALOG/catalog.py" categories
python3 "$CPSCORE_CATALOG/catalog.py" tag 42
python3 "$CPSCORE_CATALOG/catalog.py" tag "线段树"
python3 "$CPSCORE_CATALOG/catalog.py" search --luogu-tag 42
python3 "$CPSCORE_CATALOG/catalog.py" levels
python3 "$CPSCORE_CATALOG/catalog.py" stats
```

`search` 同时匹配名称、别名、ID 和分类，忽略大小写及常见空白、连字符差异；`--category` 按分类路径前缀筛选。输出包含总数、分页位置和 `has_more`，不要求模型加载完整目录。`tag` 以精确标签 ID 或名称反查 OI Wiki 条目，`get` 从 OI Wiki ID 返回标签关系与参考，`search` 也匹配已核实标签名称；检索匹配不自动认定算法等价。SA 等缩写可能命中多个知识项，须结合题意消歧，不自动合并。

共享目录环境变量需传给宿主进程，或在任务中直接提供目录路径。单独复制 Skill 也可使用这一个外部目录，无需把数据放入 Skill。没有 Python 时，宿主可检索 JSON；目录未配置或不可访问时，原有审核仍可运行，知识名称保留文字，不能编造 ID。具体安装方法见[安装说明](../install.md#共享算法知识目录可选)。

## 数据格式

顶层 `schema_version` 为 `1`，`source` 保存官方仓库提交、导航与来源页面的 SHA256，`entries` 是知识条目列表。每条包含：

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定 ID，例如 `oiwiki.graph.shortest-path.dijkstra`；不按排序编号，也不由显示名称生成。 |
| `name` | 规范中文名称，保留算法专名。 |
| `aliases` | 常见中文别名、英文名称及缩写；不保证缩写全局无歧义。 |
| `category` | 从大类到子类的字符串数组，主要沿用 OI Wiki 导航。 |
| `source_url` | 对应 OI Wiki 页面。 |
| `section` | 可选；同页独立算法的核对节名，保持与固定来源正文一致。 |
| `luogu_tags` | 标签 ID、关系与具体核对说明；显示名称、类型和父子关系只保存于同文件顶层 `luogu.tags`。 |
| `knowledge_level` | 学习、理解和实现基础算法的参考区间、证据、置信状态及适用范围；不是题目难度或掌握度。 |
| `problem_difficulty` | 按已映射标签取缓存题目并去重得到的观测分布，含样本数和题号；不是全站或算法必要性统计。 |

默认 ID 来自初次收录的来源路径，页内独立项加固定英文后缀。名称和分类调整不应改 ID；来源迁移须人工核对，在 `ID_OVERRIDES` 将新路径（拆分项用 `路径#后缀`）映射到旧 ID。更新工具发现已有 ID 消失或来源节改变时会拒绝覆盖。完成来源迁移核对后可用 `update --accept-source-moves`，但仍禁止静默删除已有 ID。

选手画像、题目知识标签及已有检索记录可以只引用 `algorithm_id`／`algorithm_ids`。画像中仍单独记录掌握程度及证据，见[画像填写说明](../skills/cp-performance-predict/references/profiles.md#引用共享算法知识)。现有网页检索缓存不作结构改造，不重复存储题解内容。算法 ID 本身不代表题目难度、原创性或选手能力。

## 洛谷标签与编号

2026-11-16核对实际可用的公开资源：

- [标签元数据](https://www.luogu.com.cn/_lfe/tags)：505个标签，其中 `type=2` / `Algorithm` 为262个，另有区域、来源、时间、特殊题目和其他标签。`模板题`（523）是来源标签，不能映射为算法。
- [页面配置](https://www.luogu.com.cn/_lfe/config)：`ProblemDifficulty` 给出网站真实ID、名称和颜色。接口路径来自实际页面配置，并已读取验证，不假定其他API存在。
- [官方难度说明](https://help.luogu.com.cn/manual/luogu/problem/difficulty)：当前八档名称及临时定义，分开讨论思维与实现负担。
- 34道明确选择的模板题与普通题公开页面：复用页面 `lentille-context` / `data.problem` 投影机制，只保存题号、题名、难度、标签、URL、获取时间与响应SHA256，不保存题面、题解或用户数据。

目录的参考索引按本次约定为 **0～7**：入门、普及-、普及、普及+/提高-、提高、提高+/省选-、省选/NOI-、NOI/NOI+/CTS。网站实际ID为 **1～8**，网站ID=参考索引+1；网站ID 0为暂无评定，对应参考索引 `null`，绝不计入入门。`levels` 输出同一份显式对照，Unicode减号显示名保留原文，规范标签仍用ASCII `-`。

CPScore原有机器输出继续使用网站ID 1～8及未知0，避免破坏既有调用。画像的掌握度0～5又是另一套量表，不从目录难度换算。

## 映射与难度语义

映射以固定OI Wiki目录和已获取的洛谷标签逐项语义核对，不用字符串相似度自动确认。标签的实际 `type/parent` 保留，同时标注 `kind` 区分分类、专题、具体算法、结构、技巧和语言入门。关系为：

| 关系 | 用法 |
| --- | --- |
| `equivalent` | 同一知识概念，例如线段树与42、Z函数与474。 |
| `broader` | 洛谷标签更宽，例如懒标记、权值线段树可关联42；多个匹配算法可关联二分图专题，但不认为它们等价。 |
| `context` | 仅分类或相关背景，不计入成功算法映射，不进入该条目的标签分布。 |

一个条目可有多个标签，一个标签也可覆盖多个条目。不因同属一个OI Wiki页面就合并概念：LCM不映射GCD，Tarjan离线LCA不映射洛谷Tarjan标签，DFT与FFT只作相关上下文。没有合适对应时保留空列表。

`knowledge_level.range` 使用0～7索引的区间，不提供单个固定等级。区间由官方说明、对应OI Wiki内容和可核实题例的基本路线作解释性判断，不是统计测量。`reference` 表示有已核实题例支撑，仍有主观性；`provisional`为暂定待专项校准；`unknown`保留 `range:null`。同一模板可有替代路线，不能因同时标注FFT/NTT或多种结构就断定全都必要。

`problem_difficulty.distribution` 为8格整数数组，位置对应0～7，`null`表示没有有等级的观测。`sample_size`包括未评级样本，`unrated_count`单列，数组之和等于两者之差。多个映射标签的样本按题号取并集，不能相加重复题。`sample_ids`可追溯同文件的 `luogu.problem_samples`。所有分布均标记 `scope=tag_union_curated_sample`、`representative=false`、`population_size=null`。

这只回答所保存题目中带相应标签的等级分布，不回答算法最优解的必要性或全站分布。线性筛知识参考可以较低，而同属素数判断标签的高难普通题仍落在黑色样本格，两者不矛盾。不能用样本均值、最高难度或标签颜色自动评知识门槛和整题难度。

CPScore先保留各条完整正确路线，再对应知识ID并按需参考知识负担，结合具体发现、证明和实现独立判断。画像仍自行提交掌握度和证据，目录不修改K/D/P/I/B。其他Skills共用此协议，没有各自的映射表。

```sh
python3 resources/algorithm-catalog/catalog.py get oiwiki.ds.seg
python3 resources/algorithm-catalog/catalog.py get oiwiki.ds.seg --knowledge-only
python3 resources/algorithm-catalog/catalog.py get oiwiki.ds.seg --exclude-problem P3372
python3 resources/algorithm-catalog/catalog.py get oiwiki.ds.seg --identity-only
python3 skills/cp-performance-predict/scripts/predict.py knowledge
python3 skills/cp-performance-predict/scripts/predict.py knowledge --profiles player.md
```

`--exclude-problem`排除目标题的样本，并隐藏任何以该题为证据的知识参考，避免用真实等级循环校准。明确盲评时用 `--identity-only`，只输出原始身份字段。常规校准可用其他题的缓存参考，但须注明范围。画像 `knowledge` 命令只读取其显式算法引用，默认16锚点合计41个ID，不自动评分。

## 本次适配结果与验证

| 项目 | 数量 |
| --- | ---: |
| 原有知识条目 | 635 |
| 有同义或较宽标签映射 | 433 |
| 其中至少一个同义映射 | 176 |
| 只有较宽映射 | 257 |
| 未映射（包含仅上下文18项） | 202 |
| 有已核实题例支撑的知识区间 `reference` | 42 |
| 暂定知识区间 `provisional` | 43 |
| 知识区间未知 | 550 |
| 公开题目元数据样本 | 34 |

主要修改为唯一 `catalog.json`、其 `catalog.py`、新增同目录 `check.py`，相关 Skill 的共享查询指引，难度 Skill 的参考使用与编号说明，以及画像读取脚本和文档。没有修改16份画像的能力数据、添加目录副本或建立顶层data/tests。

```sh
python3 resources/algorithm-catalog/check.py
python3 resources/algorithm-catalog/catalog.py validate
python3 skills/cp-performance-predict/scripts/predict.py audit
```

目录17项离线回归检查与16个参考画像锚点的结构检查通过，验证双向查找、同义/较宽关系、拒绝来源标签、未知保留、两个编号体系、样本去重与分布、排除目标题、更新保留注释和画像读取。原635个条目的ID、名称、别名、分类和OI Wiki来源投影与改动前完全一致；带上游检出的校验还核对源提交与页面哈希。这些检查不证明所有人工语义判断正确，也不证明难度区间或预测准确率。

当前映射和区间由智能体整理，尚无独立专家逐项确认。202项未映射和550项知识未知保留原条目，可继续补充可靠依据。34题是小型定向样本，不能用于全站统计。已有42个题例支撑区间也不是客观测量或学习成功概率，不宜称为已完成真实选手校准。

## 提取范围

以官方 `mkdocs.yml` 导航为主，覆盖算法基础、搜索、动态规划、字符串、数学、数据结构、图论、计算几何、杂项和专题。补入位集、分段打表、读入输出优化，以及常见技巧页中明确介绍的对拍与内存池。保留导航子分类；部分实现工具来源的条目按知识用途重新归类。

排除赛事介绍、学习路线、编辑器与工具安装、纯语言语法和标准库接口教学；纯导览不单列知识。排序应用、并查集分析／应用、图论中的 DFS/BFS 等重复内容归并到规范条目。最短路、网络流、匹配、背包、数论和多项式等页面内的独立方法，经节名及必要正文核对后拆分，不把“实现”“例题”“证明”或每个操作步骤自动变成知识。

初版包含 635 条，来源提交与完整页面哈希以 JSON 中的 `source` 为准。页内拆分及别名是经核对的整理规则，不能保证穷举所有例题中的技巧、未进入导航的新页面或上游未来新增小节；新内容应核对后再补入，不能仅依据页面标题宣称完全覆盖。

## 校验和更新

普通查询只需 Python 3.8+ 标准库，不联网。更新需要官方仓库的本地 Git 检出及 Markdown 正文，例如在仓库外准备：

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/OI-wiki/OI-wiki.git /tmp/oi-wiki-catalog-source
git -C /tmp/oi-wiki-catalog-source sparse-checkout set --no-cone '/mkdocs.yml' '/docs/**/*.md'
python3 resources/algorithm-catalog/catalog.py update --source /tmp/oi-wiki-catalog-source
python3 resources/algorithm-catalog/catalog.py validate --source /tmp/oi-wiki-catalog-source
```

OI Wiki更新器仅解析导航列表，不执行 YAML 中的 Python 标签，也不需要 PyYAML。它按 `catalog.py` 中的收录、命名、别名、合并和页内拆分规则生成唯一 JSON；OI Wiki身份字段不要分别手改生成品和规则。洛谷映射与知识注释只在这份JSON中维护，避免再存一份规则或等级表；`update`按稳定ID保留已有注释，新条目初始化为未知。新版本先检查导航变化与新增正文，再补充必要规则。无 `--source` 的 `validate` 检查结构、唯一性、分类及 URL；带 `--source` 还核对提交、全部来源哈希和拆分节名。

来源正文与临时检出不随 CPScore 发布。明确盲评时只输出身份字段，不把缓存题例或其等级带入上下文。

洛谷普通查询不联网。明确需要更新时，可执行 `catalog.py refresh-luogu --pid P3372 --pid P3373`，不传题号只检查标签与配置。每次最多40个明确题号、请求间隔至少2秒，无范围扫描、无登录或绕过限制。失败即停止，全部验证后才原子写回。标签增删、含义或层级变化会拒绝自动覆盖，要求先复核映射；题例难度或标签改变时保留原知识区间，但将其支撑的 `reference` 标成 `provisional` 待复核，不按新等级自动调整。官方难度说明仍需按日期人工检查，刷新器不会谎称重新检查了它。

## 来源与署名

名称及分类整理自 [OI Wiki](https://oi-wiki.org/) 和 [OI Wiki 官方仓库](https://github.com/OI-wiki/OI-wiki)，作者为 OI Wiki Team 及贡献者。目录进行了筛选、去重、翻译、别名归一和页内拆分。

其中OI Wiki整理字段按上游非代码内容的 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 及其 [SATA 附加声明](https://github.com/zTrix/sata-license) 保留来源与许可；详见上游 [README 版权声明](https://github.com/OI-wiki/OI-wiki#版权声明)。CPScore 自有脚本继续遵循仓库许可证。

[返回使用说明](README.md)
