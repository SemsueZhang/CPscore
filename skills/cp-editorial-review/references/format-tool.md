# 格式工具与合并接口

使用 `scripts/format_lint.py` 时读取。规范及计数见[格式协议](format.md)，类别与规则 ID 用 `--rules` 查询；`coverage` 不能作为补充发现类别。`--check` 只查环境，两者都不是稿件已通过。

## 扫描与显示边界

脚本读 UTF-8 Markdown，输出静态发现、Warning 候选及未验证范围。代码、公式、链接地址按上下文隔离，链接可见文字仍受检。

- 段内软换行按 `commonmark-softbreak-whitespace` 模型处理。可证在中文标点旁生成多余空格时，`TXT006` 为 Confirmed，证据记模型和两侧字符；其他意图不明断行留 Warning。模型推导不是页面渲染实测。
- 连续至少三条仅有编号动作句、无章节正文的标题可确认为步骤式标题；单个长标题等含糊情形留 Warning。明确更新／初始化赋值与定义、条件等式分开；定义／分类句中算法概念误用代码样式可确认，真实字符串与程序片段隔离。
- 宏、复杂参数、未知多字母串用途、含糊标题／强调／列表、代码字符串、词内空格及科学计数法阈值由 LLM 核验。图片、复杂 HTML 和部分容器进入 `skipped`；未知 HTML 子文字不视为已确认可见排版。
- 命令对照 [KaTeX 支持表](https://katex.org/docs/support_table.html)及[语法示例](https://katex.org/docs/supported.html)（2026-11-14），不代表洛谷当前配置实测；名称支持不证明任意参数合法。

输出 `schema_version=2`、`linter_version`、`render_model`。`findings/skipped` 为原扫描，`review_candidates` 为候选，`effective_findings/effective_skipped` 为裁定结果；`format_assessment` 对后者计分，单篇 `files` 保留 `static_format_assessment`。`groups` 列类别、次数、位置、等级、扣分和证据性质。状态为 `pass/non_compliant/not_assessed`；退出码 0 只表示执行成功，2 为环境、输入或裁定错误，部分失败仍保留成功扫描。

## 来源绑定与合并

逐项裁定 `review_candidates`，静态遗漏写入 `additional_findings`，不能只写文字报告。原 Warning 类别不适用但有其他问题时，排除原候选后按正确类别补充，注明重分类关系。

临时 JSON 顶层仅 `files`，绑定本次扫描的完整 `file`、`sha256`：

```json
{
  "files": [{
    "file": "/path/to/material.md",
    "sha256": "本次扫描的摘要",
    "decisions": [{
      "candidate_id": "本次候选 ID",
      "verdict": "dismissed",
      "reason": "上下文及允许写法的规范依据",
      "evidence": [{"offset": 0, "end_offset": 2, "excerpt": "原文"}]
    }],
    "additional_findings": []
  }]
}
```

- Warning 用 `confirmed/dismissed/unverified`；scope 用 `reviewed/unverified`。未提交不默认通过；`reviewed` 只表示核查过该范围，错误仍须另补充，不能据此消除。
- 裁定理由非空，证据须为精确原文，且至少一段与候选相交。偏移是解码后 Unicode 字符的零起点左闭右开区间，不是 UTF-8 字节；剥除开头 BOM，保留 CR／LF 后算摘要。
- 补充发现含 `category, offset, end_offset, excerpt, position, standard, reason, evidence`，类别取 `--rules` 中适用项。`position` 在摘录内：缺空格取右侧起点，其他错误取错误起点，整式错误取公式正文起点。先比对静态 `occurrence_key`，同物理位置不能换锚点增次数。
- 静态 Confirmed 不能撤销；疑似误报需修复规则重扫。禁止填写 severity、次数、扣分等结果字段。

运行 `python3 scripts/format_lint.py --decisions /tmp/review.json /path/to/material.md`。脚本重扫后校验整批；旧摘要、伪造 ID、证据不符、重复裁定、非法字段均拒绝整批应用，保留静态结果并报错。JSON 校验只保证来源与计数，语义及渲染裁定仍由 LLM 负责。
