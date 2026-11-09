# 历史审计证据

`v1-codex-statement.json` 是真实 Codex CLI 的原始 v1 输出，逐字节保留，不是新版生成的结果。

- 原提交：`f14eadce5d89c6158db656e096e77561936437bf`
- 原路径：`tests/integration_evidence/codex-statement/review.json`
- SHA-256：`847be980773b61bf50d7514e50b9c654564a71210ea6aa42ddf99a9f154b339f`
- 同提交同目录的 statement.md、prompt.txt、run-metadata.json、events-summary.jsonl 保存在 Git 历史，可用 `git show <commit>:<path>` 查看。本轮不重复恢复可再生 Markdown 及事件副本。
- 旧模型把正式样例 `1 2 -> 4` 评为 Minor。**v2 人工重新裁定：Fatal / incorrect_sample**，因为题目明确定义求和，1+2=3。这个裁定不改写旧模型输出，也不意味着完成其余覆盖审核。
- `test_migration.py` 验证旧源不变、迁移不自动继承通过结论，以及新版独立裁定后 0/fail。

## v2 真实调用归档

`codex-v2.zip` 保留三个 Codex CLI 调用的原始 review.json、输入材料、prompt、精简事件索引、run 元数据及实际加载的技能/协议和安装哈希清单。`index.json` 提供各原始文件 SHA-256、实际归档路径和独立人工裁定。完全相同的共享文件只存一份，按索引查找。可以用 `python3 -m zipfile -e tests/history/codex-v2.zip /tmp/cpscore-evidence` 展开阅读。不归档可重算的 scored.json / Markdown 和重复 answer.txt。全量事件日志包含重复代码与输出，未入库，索引保留命令、退出码、原日志及输出 SHA-256。原始 review.json 未删改。

运行模型 gpt-6.1-sol，xhigh，CLI 0.167.0-alpha.3.2。题面错误正式样例 0/fail、标程错误整除算法 0/fail、正确题解 10/pass，三例 completion 均为 complete。标程反例来自人工逐行推导，隔离执行因 Docker 不可用而未执行。原始 review 和隔离工具结果明确记录这个限制。

输入是P5020的自足受限摘编与人工变异，并非官方材料出错。这三个真实调用与人工裁定一致，但不足以建立审核准确率。文档精简后已用最终技能与协议重新完成三个真实调用，归档保存最终被测版本，原始输出不会被重写。

## 工程验证记录

2026-11-10 本地 QA：128 项，123 通过、0 失败、5 项容器集成跳过。完整源码包重跑相同结果，wheel 的独立评分、迁移和不支持的技能安装报错均验证。四个 Skill 的格式与三种 Harness 文件安装/升级/卸载/重装通过，Claude Code 与 OpenCode CLI 缺失，因此不声称真实调用成功。

随后在 Linux GitHub Runner [实际运行 5 项容器集成且全部通过](https://github.com/SemsueZhang/CPscore/actions/runs/42662136100/job/129316155407)：C++/Python 正错解、可复现生成、反例重放、非法输入与工具故障分离、编译/超时/输出限制/清理、隔离探针与性能记录。该工作流的 Windows 单测最初因 Git 自动转换换行导致证据哈希变化而失败，后以 `.gitattributes` 固定 LF，未放宽哈希断言。最新跨平台 CI 结果可在仓库 Actions 中核验。
