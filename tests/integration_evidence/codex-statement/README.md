# 真实 Codex 加载与工具烟测

2026-11-09 在独立临时项目调用 Codex CLI 0.167.0-alpha.3.2，模型为 GPT-6.1 Sol，推理强度 xhigh。首次启动被外层沙箱初始化权限阻止，经受审授权重试后，真实会话完成了技能加载、题面读取、报告初始化、校验与 Markdown 生成。

原始提示见 `prompt.txt`，未向模型告知题面是否存在缺陷。模型实际读取安装的 `cp-statement-review` 与共享协议，识别样例中 1+2 被写成 4，记录一项 confirmed minor。安装入口计算结果为 9 分、pass。程序与题解保持 not_reviewed，未执行候选程序，题面 SHA256 前后相同。

文件说明：

- `statement.md`：原始人工题面，刻意保留其中的样例错误。
- `review.json`、`review.md`：真实会话生成的审查记录与报告，未改写其内容。
- `events-summary.jsonl`：选取实际已完成命令事件，保留退出状态、关键校验结果，临时项目绝对路径替换为 `<PROJECT>`，省略大段输出。它不是完整日志，也不是可直接执行的脚本。
- `run-metadata.json`：宿主与模型信息、资源和归档文件的 SHA256、结论及限制。

当前代码可以重新校验并计算此记录：

```sh
python3 -m cpscore validate tests/integration_evidence/codex-statement/review.json
python3 -m cpscore score tests/integration_evidence/codex-statement/review.json
```

这只覆盖一次人工题面的一个技能，验证真实加载与工具接线，不是审核准确率实验、完整正确性证明或三个技能的端到端验收。没有调用 Claude Code 或 OpenCode + DeepSeek。安装时的技能和协议版本哈希保存在 metadata 中，之后文字更新不改变本次历史事件的范围。
