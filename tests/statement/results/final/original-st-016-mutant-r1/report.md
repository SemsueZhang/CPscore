# CPScore · 题面审核

**评分：0/10。档次：不合格，存在重大问题。题面审核已完成。**

依据当前目录 Skill 及其三份 Reference，按中文原创竞赛题的适用规范审核。

**f1 · [Fatal −10] 回复公式与下标定义矛盾**

- **位置**：[material.md 第 3 行](/tmp/cp-statement-sksys63m/material.md:3)。
- **原文**：“交互器回复所选位的异或值，即 $b_{i_1-1}\mathbin{\operatorname{xor}}\cdots\mathbin{\operatorname{xor}}b_{i_k-1}$。”
- **依据与核验**：正文定义隐藏串为 $b_1b_2\cdots b_n$，明确下标从 $1$ 开始，询问下标也在 $[1,n]$ 内。取最小合法规模 $n=1$，询问 `? 1 1` 合法，但公式要求返回未定义的 $b_0$；按“所选位”则应返回 $b_1$。两处定义不能同时成立。
- **影响**：合法询问的正常回复无法确定，属于评分协议中的核心定义矛盾，按 Fatal 扣分；不能仅作为容易修复的笔误降级。
- **修改建议**：保持已声明的从 $1$ 开始编号，将回复公式改为 $b_{i_1}\mathbin{\operatorname{xor}}\cdots\mathbin{\operatorname{xor}}b_{i_k}$。

其余核验中，初始串固定、询问合法性与次数上限、刷新要求、异常退出及最终接受条件均已有说明，未发现其他独立扣分项。正文简短，规则组织清楚，主要理解障碍就是上述公式矛盾。

材料未提供正式样例、交互器实现及 std 资源实测，因此未进行样例复算、实现核对和时空裕量验证，不据此扣分。中文原创材料不适用译文来源核验。

```json
{
  "score": 0,
  "complete": true,
  "findings": [
    {
      "id": "f1",
      "severity": "Fatal",
      "quote": "交互器回复所选位的异或值，即 $b_{i_1-1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k-1}$。",
      "evidence": "正文定义隐藏串为 b_1 至 b_n，下标从 1 开始，询问下标范围为 [1,n]。当 n=1 时，合法询问 ? 1 1 按公式需要返回未定义的 b_0，按“所选位”则应返回 b_1，导致交互回复规则矛盾。依据评分协议，核心定义矛盾为 Fatal，扣 10 分。",
      "repairs": [
        {
          "find": "交互器回复所选位的异或值，即 $b_{i_1-1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k-1}$。",
          "replace": "交互器回复所选位的异或值，即 $b_{i_1}\\mathbin{\\operatorname{xor}}\\cdots\\mathbin{\\operatorname{xor}}b_{i_k}$。",
          "conditional": false
        }
      ]
    }
  ],
  "optional_suggestions": []
}
```