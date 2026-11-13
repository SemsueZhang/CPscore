# CPScore harness 与直接审题对照

模型 `gpt-6.1-sol`，effort=`xhigh`；CPScore 固定 `5af3cda53b95ef963c81ff0cd6abd3658836d072`。
直接组仅获得题面、通用评分协议和相同输出格式，无 CPScore Skill 或方法 Reference。双方保留相同 Codex 宿主及工具；这不是去掉所有底层宿主的裸 API 对照。
执行状态：harness={'completed': 108}，direct={'completed': 108}；可配对且已裁定正式题面 53/56。两个未确认阅读 Gold 不进入已确认指标。

| 指标 | CPScore harness | 直接审题 |
| --- | --- | --- |
| 语义、样例与文字根因 Recall | 29/29 (100.0%) | 29/29 (100.0%) |
| 格式根因 Recall | 1/1 (100.0%) | 0/1 (0.0%) |
| 全部确认发现 Precision | 32/32 (100.0%) | 29/29 (100.0%) |
| Fatal Recall | 25/25 (100.0%) | 25/25 (100.0%) |
| 正确题误报率 | 0/23 (0.0%) | 0/23 (0.0%) |
| 冻结 Gold 等级准确率 | 30/30 (100.0%) | 27/29 (93.1%) |
| Gold 外确认问题等级准确率 | 1/2 (50.0%) | 0/0 (N/A) |
| 证据有效率 | 32/32 (100.0%) | 29/29 (100.0%) |
| 核心集合众数一致性 | 60/60 (100.0%) | 58/60 (96.7%) |
| 重复审核中出现无依据扣分 | 0/60 (0.0%) | 2/60 (3.3%) |
| 修复有效率（20目标为分母） | 19/20 (95.0%) | 17/20 (85.0%) |
| 语义、样例与文字目标修复有效率 | 18/19 (94.7%) | 17/19 (89.5%) |

## 逐题差异

- `st-009-mutant`：{"harness_only_known": ["literal_markup"], "direct_only_known": [], "harness_fp": [], "direct_fp": [], "harness_new": {}, "direct_new": {}, "severity_differences": {}}
- `st-015-mutant`：{"harness_only_known": [], "direct_only_known": [], "harness_fp": [], "direct_fp": [], "harness_new": {}, "direct_new": {}, "severity_differences": {"distance_transcript": ["Fatal", "Minor"]}}
- `st-029-base`：{"harness_only_known": [], "direct_only_known": [], "harness_fp": [], "direct_fp": [], "harness_new": {"input_field_meanings": "Minor"}, "direct_new": {}, "severity_differences": {}}
- `st-036-base`：{"harness_only_known": [], "direct_only_known": [], "harness_fp": [], "direct_fp": [], "harness_new": {}, "direct_new": {}, "severity_differences": {"missing_negation": ["Fatal", "Minor"]}}
- `st-038-base`：{"harness_only_known": [], "direct_only_known": [], "harness_fp": [], "direct_fp": [], "harness_new": {"input_field_meanings": "Major"}, "direct_new": {}, "severity_differences": {}}

## 未决与 Gold 外发现

- harness/st-030-base：f1 pending：是否可从整数调拨及整数输出恢复a_i类型，以及明确格式要求是否适用到需单独写“整数”，尚待独立规范/语义复核；不能因Gold未列就判误报。；f2 new_confirmed：逐字核对首段两处“乙栏”，后文仅定义“乙册”；册与栏在这套四层登记规则中不是已声明的别名。局部术语不一致与层级组织负担需要不同修订，作为Gold未记载的独立Minor记录，未直接当作误报。
- harness/st-039-base：f1 pending：与Gold中背景映射疑点对应，但显著负担及Major严重程度仍需独立读者确认，不以被测模型同意自动升级Gold。
- harness/st-029-base：f1 matched：三点样例选择权1及2的两边连通且总3，任意连通边集至少两边、正权不改进，输出9错误。；f2 new_confirmed：独立检查全文：描述只称给定（带权）图，输入仅列n,m及(u,v[,w])的类型和数量，数据范围仅列界，未在任何段落说明字段对应的对象或边权。冻结的两版Skill均明确要求交代输入量含义；此处是可恢复的图输入惯例但仍缺少适用明确条款所需说明。按该协议确认独立Major，未修改冻结Gold，不记误报。
- harness/st-038-base：f1 new_confirmed：独立检查全文：描述只称给定（带权）图，输入仅列n,m及(u,v[,w])的类型和数量，数据范围仅列界，未在任何段落说明字段对应的对象或边权。冻结的两版Skill均明确要求交代输入量含义；此处是可恢复的图输入惯例但仍缺少适用明确条款所需说明。按该协议确认独立Major，未修改冻结Gold，不记误报。；f2 matched：原句均均为正整数重复一字，易恢复且不改变正权条件，Minor。
- direct/st-019-base：f1 pending：现有文字给出了抽象边集、整数、二进制串和布尔函数协议，未指定固定C++ ABI。不同C++容器会影响某固定外部接口，但该接口是否为本材料必须给出的内容尚未确定。保留待独立接口规范复核，不直接记FP，也不据被测报告升级冻结Gold。

## 修订、稳定性与资源

- harness：修订复审 20/20；无可用建议 0/20；待复核 0/20；根因消除 20/20 (100.0%)，有效 19/20 (95.0%)；新增规格错误 0，额外明确语义变化 1，范围/协议变化 ['st-001-mutant', 'st-004-mutant', 'st-025-base', 'st-026-base', 'st-034-base']。
- harness：重复审核完整组 12/12，等价版本对 4/4。108 次主审核报告的输入 tokens 合计 9135032，其中缓存 7584000；输出 tokens 合计 297791；调用耗时中位数 80.29686749999999 秒。各项原始计数及中位数见 JSON，不是账单价格。
- direct：修订复审 19/20；无可用建议 1/20；待复核 0/20；根因消除 19/20 (95.0%)，有效 17/20 (85.0%)；新增规格错误 0，额外明确语义变化 2，范围/协议变化 ['st-001-mutant', 'st-004-mutant', 'st-025-base', 'st-026-base', 'st-034-base']。
- direct：重复审核完整组 12/12，等价版本对 4/4。108 次主审核报告的输入 tokens 合计 5936099，其中缓存 5239680；输出 tokens 合计 185748；调用耗时中位数 60.77669950000001 秒。各项原始计数及中位数见 JSON，不是账单价格。

## 解释边界

格式规范收益与语义检出收益分开解释。无建议、失败和待复核修订不计成功；只消除选定根因不等于全文无缺陷。
直接组共享基本等级定义、扣分及输出格式，没有获得完整 CPScore 的细化影响判据与判例。等级一致性反映对 CPScore 专用标准的遵循，不能作为新增数学检错能力的证据。
harness 为较早的真实运行复用，直接组在之后执行；模型别名、后端状态及时间负载没有独立固定。因此耗时只作描述，tokens 不换算为账单价格。
Gold、语义裁定及证明由维护者模型完成，未经人类专家确认；生成者与被测模型未建立独立性。确认子集可能有天花板效应，不能把相同分数解释为所有场景均无收益。
