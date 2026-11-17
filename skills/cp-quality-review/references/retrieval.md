# 检索与材料整理

## 来源覆盖与原文核实

每题用宿主工具覆盖 [CPRet](https://www.cpret.online)、[arXiv](https://arxiv.org/search/) 和普通网页，按给定及已核实路线的模型、观察、转化和算法查询。CPRet 展开候选及组内成员，必要时读摘要／题意；主张关键观察原创时补查方法与条件。复用已核实对应，无新线索即停。

检索围绕先例或影响评级的具体候选，不无目标找算法。新路线按[另解协议](rubric.md#替代解法检查)核实；比赛回顾以赛前独立工作为先例，原题与转载仅核实本题，不算独立先例。

阅读最接近原题、题解或论文正文，核对任务、约束、转化、算法、成本、随机性和误差；核实别名，题名／分数／分组仅线索，错配转查官方或镜像。

论文重合按[门槛](rubric.md#论文先例门槛)核实重要性及赛时可推导性，区分背景与实质先例，不按命中数判断原创性。

来源失败则说明范围、换可访问来源，不作零命中；无网络只能分析给定材料，不能称完成外部查重。只引用实际读到内容。

## 自动检测与回退

探测已有 `python3`、`python`、Windows `py -3` 或宿主解释器，运行 `scripts/retrieve.py --check`；退出 0 且 `ok: true` 才用其请求 CPRet、缓存及截取。仅需 Python 3.8+ 标准库，探测不联网／写文件，网络不参与解释器判定。

无命令／解释器或探测失败，直接用宿主工具，不安装依赖；请求失败、登录或 JS 页面同样回退。

## 读取方式

先读题意、约束、候选索引再展开。原响应／全文存任务临时目录复用，默认返回索引或位置，不作永久资料库。

沿 `next_start` 读到决定评级的条件、方法与论证，必要时读完整题面／章节／代码；复杂公式图表回原页面／PDF。脚本不评级或按分数裁候选／成员。

网页与arXiv搜索仍用宿主工具，定位后的HTML可交脚本缓存。返回 `needs_pdf_tool` 时用宿主PDF能力。

## 调用

由智能体执行以下命令，替换为已探测的解释器、实际脚本路径及可写临时目录：

```sh
python3 scripts/retrieve.py --check
python3 scripts/retrieve.py --cache-dir /task-temp/retrieval search --query-file /task-temp/query.txt
python3 scripts/retrieve.py --cache-dir /task-temp/retrieval fetch --url 'https://www.cpret.online/p/95131?lang=en'
python3 scripts/retrieve.py --cache-dir /task-temp/retrieval read --id DOCUMENT_ID --start 0 --length 8000
```

CPRet 默认关闭 MMR、启用去重、读前三页且保留全部候选和组链接；用 `--start-page/--pages` 扩展，耗尽即停，异常／失败保留成功部分，不记零命中。

同目录相同 URL 复用，需更新在子命令前加 `--refresh`。响应、索引、原文及文本保留抓取时间和回查位置；别名／分组仍读正文确认。
