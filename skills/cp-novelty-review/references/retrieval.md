# 检索与材料整理

## 来源覆盖与原文核实

使用宿主搜索与浏览能力，每题覆盖[CPRet](https://www.cpret.online)、[arXiv](https://arxiv.org/search/)和普通网页，围绕模型、关键观察及转化查询，按疑点补查自然特例或变体。CPRet 可用时展开候选及相关组内成员，必要时读摘要或题意。以 D/F 为候选结论时，补查模型、核心转化与适用自然特例。已核实整题关系或关键复用后可结束对应比较，复用有效结果，结果重复且无新线索时结束，不凑检索轮次。

阅读最接近的原题、题解或论文正文，核对任务、约束、转化、算法、复杂度、随机性及误差等适用条件。题名、分数和服务分组只作线索，核实别名，正文错配时转查官方来源或独立镜像。

来源不可访问时，在先例比较中说明实际范围并用可访问来源补查，不把检索失败写成未找到先例。无网络时可分析给定材料，不能宣称完成外部查重。只引用实际读到的内容。

## 自动检测与回退

探测已有 `python3`、`python`、Windows 的 `py -3` 或宿主提供的解释器，运行技能目录内的 `retrieve.py --check`。退出码0且返回 `ok: true` 时，使用脚本进行CPRet请求、网页缓存、索引和截取。要求Python 3.8+及标准库，探测不访问网络或写文件。

无命令执行能力、解释器不可用或探测失败时，直接使用宿主工具，不安装Python或包。请求失败、页面需登录或JavaScript渲染时，也回退宿主工具。网络可达性不参与解释器判定。

## 读取方式

逐题先读题意、约束和候选索引，再展开正文。原响应与全文存任务临时目录复用，默认仅返回索引或读取位置，不作为报告或永久资料库。

读到决定评级的任务、条件、方法与关键论证，按 `next_start` 续读，必要时读完整题面、章节或代码。复杂公式、图表和排版回原页面或PDF核对。脚本不评级，也不按分数裁去候选或组内成员。

网页与arXiv搜索仍用宿主工具，定位后的HTML可交脚本缓存。返回 `needs_pdf_tool` 时用宿主PDF能力。

## 调用

由智能体执行以下命令，替换为已探测的解释器、实际脚本路径及可写临时目录：

```sh
python3 retrieve.py --check
python3 retrieve.py --cache-dir /task-temp/retrieval search --query-file /task-temp/query.txt
python3 retrieve.py --cache-dir /task-temp/retrieval fetch --url 'https://www.cpret.online/p/95131?lang=en'
python3 retrieve.py --cache-dir /task-temp/retrieval read --id DOCUMENT_ID --start 0 --length 8000
```

CPRet默认关闭MMR、启用去重，读前三页并保留全部候选及组内链接。以 `--start-page`、`--pages` 扩展，候选耗尽即停。解析异常与失败页保留已完成部分，不作零命中处理。

同目录内复用相同URL，需更新时在子命令前加 `--refresh`。响应、索引、原文及提取文本均保留抓取时间与回查位置，别名和分组仍须读正文核实。
