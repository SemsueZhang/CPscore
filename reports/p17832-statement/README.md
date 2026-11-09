# P17832 题面审核记录

本目录记录对用户粘贴的地铁题面的三轮审核。**当前结论以 `report-final.md` 和 `scored-final.json` 为准：9/10，pass。**

| 轮次 | 审核输入 | 可读报告 | 结论及原因 |
| --- | --- | --- | --- |
| 初审 | `review.json` | `report.md` | 10/pass，遗漏了双向乘车规则未明示的问题，后续已修正 |
| 方向复核 | `review-direction.json` | `report-direction.md` | 10/pending，将方向问题暂列严重疑点，后续重新裁定等级 |
| 最终裁定 | `review-final.json` | `report-final.md` | 9/pass，结合地铁的强常识默认与样例，将缺少方向明示确认为一个 Minor |

题面未被修改，变化来自审核结论与分级的纠正。旧记录保留用于追溯，不代表三个同时有效的结论。`direction-witness.in` 是说明两种方向模型答案不同的人工输入，其存在本身不证明两种读法同等合理。

本目录未保存用户粘贴题面的完整副本，审核记录通过章节、引用与明确的用户消息版本标签定位，未将该标签伪称为原题面文件哈希。样例3至7附件、完整官方数据和原平台渲染均未核验。

从仓库根目录可重新校验和计算最终结果：

```sh
python3 -m cpscore validate reports/p17832-statement/review-final.json
python3 -m cpscore score reports/p17832-statement/review-final.json
```
