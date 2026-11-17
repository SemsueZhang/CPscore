# 审核对象与执行覆盖

## 对象与任务结果

开始详细审核前，固定待审原文和版本，按章节或主要段落列对象，再单列重要声明、关键推导、算法、每份代码、样例及必要附件。对象使用稳定 ID 和原文位置，保持各部分可追踪。按重要内容拆分，避免逐句建表。

默认启用 `content`、`reading`，用户明确要求格式审核时增加 `format`。每个任务分别产生结果，委派时传递相同对象及适用检查项，记录实际执行者与范围。顺序完成同样保留分任务结果。

- 内容按对应核验 Reference 给每种做法或规格对象安排适用维度，分别记录定义、数学结论、依据、输入／操作边界、成本、数值、实现及样例。采用正向与逆向路线互补，重要声明各自有结论。无附件／无某类结构等有依据时记不适用。
- 阅读覆盖全文各部分及主次关系，按文风分类逐类检查，给主旨、叙述依赖和表达影响的依据。题面与题解采用各自的阅读职责。
- 启用格式时按规范类别记录范围，逐项处理 Linter 候选和未核验范围，并补查扫描器不覆盖的类别、图片及容器。未启用记“未请求”，从审核范围中排除。

每条结果记录对象、检查项、结论与具体依据，状态为已核验、发现问题、未确定或不适用。通过依据应含实际核对的关系或边界；依据不足时定向回查。候选问题单独保留位置和核实结论，最终按根因合并。

## 覆盖检查与补查

1. 对照原文检查对象清单是否涵盖每个章节、重要段落、声明、代码、样例和附件，对照核验 Reference 检查适用维度是否齐全。
2. 检查各已启用任务是否有结果，每个对象的检查项是否有结论与依据，候选问题是否已核实，格式结果是否均已处理。
3. 只补查遗漏、未确定和依据不足的对象／检查项。保留已发现候选，撤销或改级以原文证据为据。
4. 合并已确认问题后评分。剩余未核验范围如实报告，审核标为未完成；执行遗漏转为补查任务。

有 Python 时使用随包 `scripts/check_coverage.py` 检查下述记录。无 Python 时按相同字段人工核对。记录齐全仅证明执行覆盖，重要对象是否识别完整、依据是否成立和判断是否正确仍由 LLM 核验。

## 最小结构化接口

内部记录可暂存 `/tmp/review.json`。有 Python 时采用以下 JSON 接口，覆盖工具和格式工具使用各自记录文件。

```json
{
  "version": 1,
  "format_requested": false,
  "sources": [{"id": "s1", "path": "/tmp/original.md", "sha256": "原文件字节的SHA256"}],
  "objects": [{
    "id": "p1", "source": "s1", "start": 0, "end": 23,
    "excerpt": "该对象起始处的原文短摘录",
    "checks": ["content.rules", "reading.main_point", "reading.patterns"]
  }],
  "results": [
    {"object": "p1", "check": "content.rules", "status": "checked", "basis": "实际核对的规则、条件与结论", "findings": []},
    {"object": "p1", "check": "reading.main_point", "status": "checked", "basis": "本段的任务与核心规则及其依赖", "findings": []},
    {"object": "p1", "check": "reading.patterns", "status": "issue", "basis": "重复保证语遮蔽规则，位置见p1", "findings": ["f1"]}
  ],
  "findings": [{"id": "f1", "objects": ["p1"], "status": "confirmed", "basis": "具体原句及阅读影响"}]
}
```

- `sources` 列全部待审稿件及已取得的待审附件，题解审核的参考题面可作为外部依据。相对路径基于记录文件目录。保存原始文本快照，按 UTF-8 解码后计算零起点左闭右开的 `start/end`，保留原始换行。`excerpt` 是范围起始处的非空精确短摘录。图示等非文本材料在文字锚点下记录实际检查结果与未取得范围。
- `checks` 在判断前确定，检查项用 `content.`、`reading.` 或 `format.` 前缀，同前缀属于同一任务，后缀标明具体维度。各任务的对象范围应覆盖原文全部非空白内容。章节对象负责全段覆盖，重要声明可另建重叠的细对象。新增发现涉及漏列声明时先补对象。
- `results` 按对象与检查项一一对应，`status` 取 `checked/issue/uncertain/not_applicable`，`basis` 非空。不适用须给适用性理由。`issue` 关联已确认发现，`findings` 是候选问题 ID 列表。
- 顶层 `findings` 的 `status` 取 `confirmed/rejected/uncertain`，每项须有原文对象、核实依据且被相应结果引用。确认后的级别、类别、影响和修改建议按报告及评分协议给出。
- 启用格式后，Linter 的每个 `review_candidates` ID 作为对应对象的 `format.<candidate_id>` 检查项，保存扫描 JSON，裁定后保存含 `effective_findings/effective_skipped` 的合并结果，用 `--format-scan` 传给覆盖工具。其他规范类别仍需单列；覆盖工具检查候选 ID、文件摘要、结果位置、剩余 Warning／未核验范围及已确认发现是否纳入任务结果，语义裁定与补充发现按格式接口提交。

工具检查引用、字段、源文件摘要、范围及摘录、缺失结果、任务全文范围、未确定状态和未核实候选。输出 `records_complete/incomplete/invalid`，退出码分别为 0/1/2。`records_complete` 表示所列记录齐全，内容结论仍需原文依据支持。未取得材料及未识别的重要声明由主审在第一步补查。

```sh
python3 scripts/check_coverage.py /tmp/review.json
python3 scripts/check_coverage.py /tmp/review.json --format-scan /tmp/format-scan.json
```
