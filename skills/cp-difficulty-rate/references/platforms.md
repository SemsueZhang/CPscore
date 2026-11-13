# 洛谷、CF 与 AtCoder 适配

版本：`cpscore-platforms-20261113-v1`。总档使用洛谷八档，CF 与 AT 分别从同题原生标签拟合，不把两站的同一数值视为等难。

## 默认换算表

区间左闭右开，最后一档无上界。CF 指**题目 rating**，AT 指 **AtCoder Problems 显示 difficulty**，两者均不是选手 rating。

| 总档 | 洛谷名称 | CF 题目 rating 参照 | AT 显示 difficulty 参照 |
| --- | --- | --- | --- |
| 0 | 入门 | [800, 1000)；更简单题可能低于 CF 评级下限 | [0, 300) |
| 1 | 普及- | [1000, 1300) | [300, 700) |
| 2 | 普及 | [1300, 1800) | [700, 1300) |
| 3 | 普及+/提高- | [1800, 2000) | [1300, 1700) |
| 4 | 提高 | [2000, 2500) | [1700, 2300) |
| 5 | 提高+/省选- | [2500, 2700) | [2300, 2500) |
| 6 | 省选/NOI- | [2700, 3000) | [2500, 2900) |
| 7 | NOI/NOI+/CTS | [3000, +∞) | [2900, +∞) |

这些是有版本的粗略换算档，区间宽度不表示相等的能力差。将总档反查为原生区间，只得到该换算器的分箱，**不表示该档所有题的原生值均落在此区间**。不要称为统计置信区间、真实难度范围或官方跨站对照表。

有内容评定时，以完整路线、三维依据和总档锚题比较形成主评，再列平台参照。已核实的原生标签单列，两者不一致时说明具体瓶颈和尺度差异，不能为了匹配 rating 改写三维。只有原生数字时可以换算总档，但标为“由原生标签换算”，K/T/I 保持未知。

## 字段与身份

- **洛谷**：八档名称依据[帮助文档](https://help.luogu.com.cn/manual/luogu/problem/difficulty)。2026-11-13 的[配置](https://www.luogu.com.cn/_lfe/config)中，原生 difficulty ID 1～8 依次对应本技能 0～7。原生 ID 0 是“暂无评定”，返回未知，绝不能转成入门或负数。使用名称时按表匹配，注意减号 `-` 与 `−` 的显示差别。
- **CF**：读取[官方 Problem 对象](https://codeforces.com/apiHelp/objects#Problem)的 `rating`。缺失、未定级是未知，不用题目分值、比赛题位或选手 rating 代替。评级下限附近不能细分所有基础题，低于 800 的参考描述不能冒充官方题目 rating。
- **AT**：读取[AtCoder Problems 社区模型](https://kenkoooo.com/atcoder/resources/problem-models.json)的 `difficulty`，按稳定 task ID 匹配。它不是 AtCoder 官方难度，也不是题目分值。ADT 重用题和 ABC/ARC 共享题按 task ID 去重。AHC 的优化分数不适用本表。缺失或非有限值返回未知，experimental 值注明不稳定，不作为可靠校准标签。

AtCoder Problems 的[前端转换](https://github.com/kenkoooo/AtCoderProblems/blob/main/atcoder-problems-frontend/src/utils/index.ts)为：

```text
display = round(raw)                          raw >= 400
display = round(400 * exp(raw / 400 - 1))      raw < 400
```

round 使用 JavaScript `Math.round` 对非负值的规则。raw 可以为负，例如 raw=0 的显示值是 147，raw=400 的显示值是 400。已经显示的 difficulty 不能再次转换。`slope` 属于另一项模型参数，可以为负或缺失，不能据它推断 `difficulty` 缺失。本次将 raw=-10000 的极端地板值单列排除，而非排除所有负 raw 值。

## 适配依据与表现

[同题快照](platform-anchors.json)保留原站 task ID、洛谷镜像、原生值、日期、响应指纹、选题与排除原因、development / holdout 用途。数据来自 CF 官方 API、AtCoder Problems 模型，以及洛谷同 task ID 的题目页和分类列表。只取难度元数据，没有读取 Auto-Insight 原洛谷十六道测试题的题面、题解或三维答案。

共保留 305 条记录，303 条可用：CF 149 条、AT 154 条。原小批对照均作为开发材料。补充时按各站洛谷八档扫描列表，取足够匹配题的最早页面，排除已有身份及无有效原生值的题，再按固定 task ID 哈希顺序选每档五道留出、十道开发。拆分在查看留出指标前固定。开发集 CF 109、AT 114，留出各 40、每档各 5。列表排序与分层选题有偏，未声称是各站总体的随机样本或近变体完全无泄漏的证明。

两站独立拟合七个严格递增切点，在 100 点网格上最小化总档绝对误差。平局优先靠近各边界的最优区间中心，再按切点字典序确定。切点仅用开发集拟合，未在留出结果上调参。模型和逐题结果见[适配参数](platform-calibration.json)。

| 站点 | 留出题数 | 总档平均绝对误差 | 完全命中 | 相差至多一档 | 最大跨档误差 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CF | 40 | 0.600 | 20/40 | 36/40 | 2 |
| AT | 40 | 0.350 | 27/40 | 39/40 | 2 |

结果只衡量**原生难度到洛谷档次的转换**。未验证题面到三维、三维到总档、全 skill 评级准确率，也不检验预训练未见的新 trick。使用时保留“粗略参照”身份，针对题型及路线的偏差说明原因。

## 随包数字工具

在技能目录中，用已有 Python 3.8+ 执行，无第三方包、API key 或联网要求：

```sh
python3 scripts/platforms.py --level 4
python3 scripts/platforms.py --cf 2200
python3 scripts/platforms.py --at-raw -197
python3 scripts/platforms.py --at-display 1528
python3 scripts/platforms.py --luogu-id 0
```

工具只转换传入数字，未自行查询原生标签或分析题目。输出含版本、来源尺度、观察范围外标记及每档开发样本数。实际报告还需说明所用题目、路线与来源。

离线复现拟合和留出指标：`python3 scripts/calibrate_platforms.py`。默认打印 JSON，需要文件时加 `--output /absolute/path/to/result.json`。冻结快照和旧指标不因重复执行而产生新的独立证据。
