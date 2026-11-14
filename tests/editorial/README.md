# 题面与题解共用格式检查

在仓库根目录运行，无第三方依赖：

```sh
python3 -m unittest discover -s tests/editorial -v
python3 scripts/sync_review_format.py --check
python3 skills/cp-editorial-review/scripts/format_lint.py --check
python3 skills/cp-statement-review/scripts/format_lint.py --check
```

当前 `2.3` 的测试覆盖正常中文与英文／公式混排，缺空格、明显标点和全角空格，代码／数学／链接／图片隔离，Markdown 结构，TeX 环境与参数，字符引用及 Unicode 位置，以及环境检查、路径／编码失败、部分文件成功和不修改原文。Python 版本失败用模拟环境测试，不等于已在所有 Python 3.8+ 版本实跑。历史各轮实际通过数量见 [format-audit.md](format-audit.md)。

共用源位于 `shared/review-format/`，由 `scripts/sync_review_format.py` 打包到两个技能，安装方式仍为独立目录复制。`test_format_shared.py` 验证共用源漂移检查、隔离安装后的两入口结果一致、警告裁定互通、失败批次回退和展示约定补充发现的统一计分。

内容与格式分别核查、分别报告。格式优先静态检查，LLM 负责静态遗漏和不确定范围，脚本统一计分。单篇同类 Confirmed 的独立位置数为 1～2 时 Major、至少 3 时 Fatal，每类扣一次。剩余 Warning 和未验证范围不能充当确定次数。`test_format_decisions.py` 覆盖源码绑定、候选裁定、无候选 ID 的补充发现、排除原警告并重新归类、三处阈值、跨检测器去重、跨文章隔离、批次失败回退和静态事实不可外部撤销。

十篇真实文章快照的复盘见 [format-regression.md](format-regression.md)。这是针对已见材料的开发回归，不是盲测、专家 Gold 或泛化准确率。

`test_format_context.py` 覆盖 v2.1 的上下文修正：软换行生成标点旁多余空格的模型证据，代码与公式后的标点，链接可见文字的句末，残缺条件句，合法列表续行与嵌套围栏，连续动作标题，拆分公式，明确赋值，概念名与字符串隔离，以及空图片目标／不完整 URL 不中断扫描。

`test_format_audit.py` 覆盖多轮核查新发现的缺陷，另含 1,200 组可复现生成输入的位置／片段不变量检查，以及 20 万字符正文与 6,000 个公式的运行检查。当前进展与剩余缺陷见 [format-audit.md](format-audit.md)；这些有限测试不证明已覆盖所有 Markdown／TeX 写法，剩余复杂语法按复核协议处理。

## 教学对照材料

统一题面为 [statement.md](materials/statement.md)。预期读者掌握数组、前缀和与基础遍历，尚不知道本题解法。测试请求为“结合题面审核此 Markdown 源稿的数学、教学与源码格式，不包含尚未发布的目标页面和投稿来源资格，输出机器合规结论与评分”。

| 题解 | 设计预期 | 应避免的错误 |
| --- | --- | --- |
| [clear.md](materials/clear.md) | 数学和讲解完整，通过，无需改写 | 将更新次序与全负数说明当作防御性语言 |
| [defensive.md](materials/defensive.md) | 无信息自辩打断动机与实现的连接，局部冗余 Minor；合规不通过 | 因表达问题声称算法错误，或按句子数重复扣分 |
| [missing-motivation.md](materials/missing-motivation.md) | 指定初学读者需重新发现区间差到前缀最小值的联系，人类思维检查为 Fatal；合规不通过 | 因审核者能补证而降为 Major，或把推导难懂冒称算法已被反例推翻 |
| [repetitive.md](materials/repetitive.md) | 重复总结不增加信息，局部冗余 Minor；合规不通过 | 强迫保留模板总结，或重写正确算法 |
| [concise.md](materials/concise.md) | 简洁但完整，通过，无需扩写 | 按字数、章节或例子数量扣分 |

这些材料及预期由本次修改构造，不是经过人类专家校准的 Gold。单元测试只检查它们没有混入静态格式缺陷，不用关键词断言 LLM 已理解教学质量。新版内容／格式分离、文字过程、人类思维和重新归类的同作者走查见 [review-coverage.md](review-coverage.md)，旧版历史记录见 [walkthrough.md](walkthrough.md)；均不能证明泛化效果提升。

## 无 Python 与严格通过场景

1. 无命令能力或无已有 Python：LLM 继续核查可取得的源码和可见内容，不安装解释器；不能完成的必查范围才合并计核验缺口 Major。
2. 只有截图：源码格式未获验证，记录材料缺口，不能虚构源码违规或三处 Fatal。
3. 全角字母、未定义宏、含糊的软换行或长代码用途不能静态确定：交审核 LLM 核验，未消除的不确定性仍不通过。换行能在已声明模型下证实产生标点旁多余空格时才为静态 Confirmed。不能将多条警告直接升为 Fatal，不设人工裁定。
4. 脚本明确支持的代码、公式、文本命令、空白结构和正常混排不误用中文排版规则。语言或数学信息不足仍由非格式审核负责。

程序测试覆盖环境不可用的失败信号及其结构化输出；完整 Skill 的宿主行为仍需真实环境验证。旧版 [walkthrough.md](walkthrough.md) 保留历史判断，不替代当前入口和评分协议。
