# CPScore · 题面审核

**评分：0/10；档次：不合格，存在重大问题；审核完成。**

共确认 1 项 Fatal，按 Skill 计分：\(10-10=0\)。

### f1 · [Fatal −10] 回复公式与一基下标定义冲突

**原文位置：**[material.md 第 3 行](/tmp/cp-statement-oi8wtd3o/material.md:3)。

> 交互器回复所选位的异或值，即 $b_{i_1-1}\mathbin{\operatorname{xor}}\cdots\mathbin{\operatorname{xor}}b_{i_k-1}$。

**核验依据：**正文已明确隐藏串为 \(b_1b_2\cdots b_n\)，下标从 \(1\) 开始，询问下标属于 \([1,n]\)。回复公式却将下标减去 \(1\)，与上述定义矛盾：

- 最小合法情形 \(n=1\)，询问 `? 1 1` 合法，但公式要求回复未定义的 \(b_0\)。
- 取 \(n=2\)、隐藏串 `01`，询问 `? 1 2`。按“所选位”应回复 \(b_2=1\)，按公式却回复 \(b_1=0\)。

**实际影响：**合法询问的回复可能无定义，且文字规则与公式会给出不同结果，交互接受关系无法可靠确定。上下文虽然指向“询问所选位”，仍不能消除明确公式的冲突。

**可直接采用的局部修订：**保留题面已明确的一基下标规则，将回复公式替换为：

```latex
$b_{i_1}\mathbin{\operatorname{xor}}\cdots\mathbin{\operatorname{xor}}b_{i_k}$
```

**复核结果：**修订后，上述两例分别回复 \(b_1\) 和 \(b_2\)；所有合法询问均只访问已定义的位置。逐个询问下标即可在恰好 \(n\) 次内恢复隐藏串，与末尾说明及询问上限一致。建议未应用到原文件。

其余协议已说明询问格式、下标范围、次数限制、刷新、最终输出、结束及异常处理，未确认其他独立扣分项。材料未提供正式样例，无法开展样例核验；未提供 std、资源实测或译文来源，相应对照未开展，不据此推定违规。审核仅使用当前目录的题面及指定 Skill 参考材料。

```json
{
  "score": 0,
  "complete": true,
  "findings": [
    {
      "id": "f1",
      "severity": "Fatal",
      "quote": "交互器回复所选位的异或值，即 $b_{i_1-1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k-1}$。",
      "evidence": "隐藏串定义为 b_1 至 b_n，询问下标属于 [1,n]，但回复公式将下标减去 1。n=1 时，合法询问 ? 1 1 引用未定义的 b_0；n=2、隐藏串为 01 时，询问 ? 1 2 按所选位应回复 1，按公式却回复 0。该冲突影响合法询问的回复及交互接受关系。",
      "repairs": [
        {
          "find": "$b_{i_1-1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k-1}$",
          "replace": "$b_{i_1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k}$",
          "conditional": false
        }
      ]
    }
  ],
  "optional_suggestions": []
}
```