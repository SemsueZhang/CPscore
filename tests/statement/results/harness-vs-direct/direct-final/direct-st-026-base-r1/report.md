审核完成，得分 **0/10**：确认 1 项 Fatal，扣 10 分。正式样例已核验，$|1-7|=6$，输出正确。

**f1 · Fatal：允许 $n=1$，但未定义此时的答案**

- **原文**：[material.md 第 15 行](/tmp/cp-statement-gdyuwol8/material.md:15)：“$1\le n\le2\times10^5$，$-10^9\le a_i\le10^9$。”
- **依据**：题目要求在满足 $1\le i<j\le n$ 的下标对中求最小值。合法输入 `n=1, a₁=0` 不存在这样的下标对，空集没有最小值，而输出格式要求输出一个整数。上下文未提供此情况的输出约定，因此合法输入的正确答案未定义。
- **修改建议**：若题意要求至少存在一对下标，将下界改为 $2\le n$；若需要保留 $n=1$，应由作者明确该情况下的输出约定。这两种方向需要作者选择。

```json
{
  "score": 0,
  "complete": true,
  "findings": [
    {
      "id": "f1",
      "severity": "Fatal",
      "quote": "$1\\le n\\le2\\times10^5$，$-10^9\\le a_i\\le10^9$。",
      "evidence": "合法输入 n=1、a₁=0 时，不存在满足 1≤i<j≤n 的下标对，所求最小值未定义；输出格式要求输出一个整数，且全文未规定此时的输出。",
      "repairs": [
        {
          "find": "$1\\le n\\le2\\times10^5$，$-10^9\\le a_i\\le10^9$。",
          "replace": "$2\\le n\\le2\\times10^5$，$-10^9\\le a_i\\le10^9$。",
          "conditional": true
        }
      ]
    }
  ],
  "optional_suggestions": []
}
```