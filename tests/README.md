# 验收材料

这里保留小规模、可独立阅读的审核材料和预期，不维护评分程序或模型调用框架。材料由旧有回归样例转换，并增加独立缺陷、完整规模简洁题解、待复核及其余技能的使用场景。预期是维护者的测试裁定，不是模型已经通过的证据。

来源模型包括[NOIP 2012 借教室](https://www.luogu.com.cn/problem/P1083)、[NOIP 2018 货币系统](https://www.luogu.com.cn/problem/P5020)及[CSP-S 2026 地铁](https://www.luogu.com.cn/problem/P17832)。前16项主要是受限摘编或人为变异，不是官方题面全文或官方错解。case-18按借教室的完整规模模型重新表述，算法和证明由本次验收编写。case-08复用case-05的材料，case-12复用case-09的材料，仓库各保留一份输入，实际独立调用的原件仍分别保存。

## 如何验收

1. 创建干净临时目录，只复制所测的一个 `skills/<名称>/` 到宿主技能目录，再复制对应材料为 `material.md`。不要复制本文件、仓库说明、预期、其他技能或共享文件。
2. 让宿主使用该技能处理材料。不要在请求中透露预期分数、类别、疑似错误、修复方式或此前结论。文件名使用中性的 `material.md`。
3. 用户不要求保存文件时，检查是否直接回复Markdown，是否私自创建中间报告、要求运行命令或依赖额外运行时。
4. 完成后再与下表比较。核对推导和分级，而不只比数字。保留原始输出，失败如实记录，不把静态检查或预期本身当成模型验证。

程序材料中的Python代码是供阅读的竞赛程序文本，不是项目运行时或测试脚本。case-20另将 `data/` 下六个文件复制到同一临时目录，使用宿主编译器运行候选。case-22、23是汇总逻辑的合成输入，所给“已有评审”并非外部真实评价，不用来验证题目原创性。

## 正确性预期

| 材料 | Skill | 预期 | 决定性依据 |
| --- | --- | --- | --- |
| [case-01](materials/case-01.md) | statement | 10 | 闭区间、顺序、首次失败及样例均明确 |
| [case-02](materials/case-02.md) | statement | 0 | 容量1、需求2，样例错误输出成功 |
| [case-03](materials/case-03.md) | statement | 0 | 全网互达不能确定每条线路的方向，同一三站环输入可得4或6 |
| [case-04](materials/case-04.md) | statement | 10 | 标准非负整数符号无需展开教学 |
| [case-05](materials/case-05.md) | solution | 10 | 排序完全背包正确，能证明不可约面额必选 |
| [case-06](materials/case-06.md) | solution | 0 | 只检验整除遗漏混合表示，例如8=3+5 |
| [case-07](materials/case-07.md) | solution | 9 | 代码正确，注释却称初始化后的0不可达 |
| [case-08](materials/case-05.md) | solution | 10 | 复用case-05，正确标准实现无需因没有详细注释扣分 |
| [case-09](materials/case-09.md) | editorial | 10 | 等价性、必选性、最优性和复杂度完整 |
| [case-10](materials/case-10.md) | editorial | 0 | gcd不能代替有限正面额的非负整数可表示性 |
| [case-11](materials/case-11.md) | editorial | 7 | 算法正确，但只证等价，缺少种数下界 |
| [case-12](materials/case-09.md) | editorial | 10 | 复用case-09，公认结论、标准更新及合理省略不扣分 |
| [case-13](materials/case-13.md) | statement | 7 | 核心方向规则需用树的桥割及有序点对互达非平凡推断 |
| [case-14](materials/case-14.md) | solution | 7 | 确定浪费至少76.29MiB，未声称已测得TLE/MLE |
| [case-15](materials/case-15.md) | editorial | 7 | 算法正确，原证明由同gcd推出同种数的推理错误 |
| [case-16](materials/case-16.md) | editorial | 9 | 核心证明完整，非关键算例8/4被误写为3 |
| [case-17](materials/case-17.md) | editorial | 6 | 独立的最优性缺漏Major和局部算例错误Minor |
| [case-18](materials/case-18.md) | editorial | 10 | 完整规模的差分检查及单调二分证明简洁充分 |
| [case-19](materials/case-19.md) | solution | 暂定，档次待定，无已确认扣分 | 规格缺范围与资源，不能编造合法反例或判定超限 |
| [case-20](materials/case-20.md) | data | 0 | 只输出首项的错误算法实测得到两个本不应得的点 |

case-11是旧名 `editorial_minor` 对应的材料，现有正确标准为Major。case-14的确定性资源浪费是非致命缺陷，不是未经目标机校准的超时结论。case-17两个问题需要不同修复，独立扣分。不同评分必须用材料中的数学或使用影响解释，不能因预期数字修改判据。

case-03的旧预期为Minor，真实复核发现该裁定不成立。取三条线路1—2、2—3、3—1，所有步行单程费用为1，查询2到1。全双向时直接乘车费用为4，沿1→2→3→1的单向环运行时费用为6，两者均满足任意站对互达。输入未提供方向，反向样例也不能排除其他线路的单向运行，因此影响答案且不能唯一补全，应判Fatal。当前材料已明确单程步行费用，隔离这一实际歧义。

## 其他技能

| 材料 | Skill | 验收重点 |
| --- | --- | --- |
| [case-21](materials/case-21.md) | novelty | 核对已给公开题后为A，不能因换背景或质量好升级，保留独立报告结构 |
| [case-22](materials/case-22.md) | problem | 题解7分但新颖度A，最低档为不合格，不平均，不擅自视为已修复 |
| [case-23](materials/case-23.md) | contest | 结合实际比赛条件，保留较低的单题合格结果，分析时间与梯度 |
| [case-24](materials/case-24.md) | performance | 给路线、障碍、时间、得分及策略，不产生质量评级、不编造实测 |

## 目录和安装检查

运行 `sh tests/check.sh`，检查标准前置信息、独立目录复制、三宿主的全局/项目级目标、单个/全部安装、更新清除旧文件、卸载不影响其他技能，以及新增技能被动态扫描。全局目录用临时用户目录模拟，脚本不会修改实际用户配置。

此检查只证明文件和复制操作，不证明宿主已经发现技能，也不证明模型会正确评审。实际模型调用、未验证环境和原始记录位置见[重构验收记录](../docs/review-notes.md)。
