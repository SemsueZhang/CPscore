# 检索与材料整理

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
