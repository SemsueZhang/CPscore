# 严格审核行为校准

2026-11-09 更新三个正确性审核 Skill 与共享协议后，使用一个独立 GPT-6.1 Sol xhigh 子智能体审核六份人工材料。仅提供材料、对应 Skill 和协议，未提供各例预期结论。没有执行待审程序。主 agent 复核了缺陷依据、材料哈希，并用共享代码重新校验与计分。

| 材料 | 审核对象 | 本次结果 | 依据 |
| --- | --- | --- | --- |
| A | statement | 9 / pass | 地铁双向乘车规则未明示，按一个 Minor 扣分 |
| B | statement | 10 / pass | 完整的两数求和定义，未确认问题 |
| C | solution | 0 / fail | 切片遗漏最后一项，n=1、a=7 时静态推导错误输出0 |
| D | solution | 10 / pass | 合法输入下完整求和，未因代码简短而扣分 |
| E | editorial | 10 / pass | BFS题解可引用标准结论，不强求从头证明 |
| F | editorial | 0 / fail | 面值1、3、4的贪心在金额6时非最优，算法与错误论证同根因只扣一次 |

材料在 `materials/`，路径归一化后的审核记录在 `reviews/`，模型、来源哈希和汇总在 `run.json`。可从仓库根目录重新计算，例如：

```sh
python3 -m cpscore validate tests/integration_evidence/strict-review/reviews/A.json
python3 -m cpscore score tests/integration_evidence/strict-review/reviews/A.json
```

这些命令仅重放确定性校验与算分，不会重新调用模型。要复测审核行为，应让独立评审只读取对应材料、当前 Skill 与协议，先独立输出报告，再对照本记录复核。

这是一次小范围行为校准，没有修改前后的对照实验，不能据此宣称审核准确率提高、没有漏报或没有误报。协议已包含用户确认的地铁分级例子，A验证该规则的应用，不是未见过案例上的泛化能力。标准结论可合理省略、个人风格不扣分、真实缺陷应扣分这三条边界在本次样本上均得到体现。
