"""Regression checks for format ownership, missing rules and occurrence counts."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("format_lint_v2", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class PolicyTests(unittest.TestCase):
    def assessment(self, text):
        return LINT.lint_text(text, "source.md")["format_assessment"]

    def group(self, text, category):
        return next(g for g in self.assessment(text)["groups"] if g["category"] == category)

    def test_zero_occurrences_pass_without_format_deduction(self):
        result = self.assessment("算法为 BFS。\n")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["format_deduction"], 0)

    def test_one_and_two_occurrences_major_three_fatal(self):
        for text, count, severity, deduction in [
            ("中文English。\n", 1, "Major", 2),
            ("中文English中文。\n", 2, "Major", 2),
            ("中文English中文English。\n", 3, "Fatal", 10),
        ]:
            with self.subTest(count=count):
                group = self.group(text, "missing_space")
                self.assertEqual((group["confirmed_count"], group["severity"], group["deduction"]),
                                 (count, severity, deduction))

    def test_text_and_math_missing_space_share_one_category(self):
        group = self.group("中文English，得到$x$，输出$y$。\n", "missing_space")
        self.assertEqual(group["confirmed_count"], 3)
        self.assertEqual(group["severity"], "Fatal")
        self.assertEqual(set(group["rule_ids"]), {"TXT001", "MATH001"})

    def test_formula_has_two_boundaries_not_four_detector_hits(self):
        result = LINT.lint_text("得到$x$结果。\n")
        findings = [f for f in result["findings"] if f["category"] == "missing_space"]
        self.assertEqual(len(findings), 2)
        self.assertEqual(result["format_assessment"]["groups"][0]["confirmed_count"], 2)

    def test_three_warnings_do_not_manufacture_three_errors(self):
        group = self.group("公式 $\\custom{x}$、$\\custom{y}$、$\\custom{z}$。\n", "math_support")
        self.assertEqual(group["confirmed_count"], 0)
        self.assertEqual(group["unconfirmed_count"], 3)
        self.assertEqual(group["severity"], "Major")
        self.assertEqual(group["basis"], "Unverified")

    def test_warning_alone_automatically_fails_strict_approval(self):
        result = self.assessment("示例 ＡＢＣ。\n")
        self.assertEqual(result["verdict"], "non_compliant")
        self.assertFalse(result["complete"])

    def test_same_physical_gap_from_two_detectors_counts_once(self):
        base = {"file": "a.md", "category": "missing_space", "line": 1, "column": 2,
                "excerpt": "缺少间隔", "type": "Confirmed", "occurrence_key": "edge-1"}
        result = LINT.format_assessment([dict(base, rule_id="TXT001"), dict(base, rule_id="MATH001")])
        self.assertEqual(result["groups"][0]["confirmed_count"], 1)
        self.assertEqual(result["format_deduction"], 2)

    def test_two_incomplete_scopes_are_one_material_gap_not_fatal(self):
        scopes = [{"file": "a.md", "line": i, "column": 1, "reason": "未验证范围", "unverified": True}
                  for i in range(1, 5)]
        result = LINT.format_assessment([], scopes)
        self.assertEqual(result["format_deduction"], 2)
        self.assertEqual(result["groups"][0]["confirmed_count"], 0)

    def test_unclosed_code_warning_and_unverified_span_are_one_gap(self):
        result = self.assessment("未闭合的代码 `x\n")
        self.assertEqual(len(result["groups"]), 1)
        group = result["groups"][0]
        self.assertEqual((group["category"], group["unconfirmed_count"]), ("code_fence", 1))
        self.assertEqual(result["format_deduction"], 2)

    def test_files_do_not_combine_to_reach_three(self):
        findings = []
        for file in ("a.md", "b.md", "c.md"):
            findings.extend(LINT.lint_text("中文English。\n", file)["findings"])
        result = LINT.format_assessment(findings)
        self.assertEqual(len(result["groups"]), 3)
        self.assertTrue(all(g["severity"] == "Major" for g in result["groups"]))
        self.assertEqual(result["format_deduction"], 6)

    def test_partial_input_failure_never_reports_format_pass(self):
        result = LINT.format_assessment([], errors=[{"file": "missing.md", "message": "cannot read"}])
        self.assertEqual(result["verdict"], "non_compliant")
        self.assertEqual(result["groups"][0]["basis"], "Unverified")

    def test_repeated_file_arguments_are_not_repeated_occurrences(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "a.md"
            path.write_text("中文English。\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), str(path), str(path.resolve())],
                                 check=True, capture_output=True, text=True)
            result = json.loads(run.stdout)
        self.assertEqual(len(result["files_checked"]), 1)
        self.assertEqual(result["format_assessment"]["groups"][0]["confirmed_count"], 1)


class RuleRegressionTests(unittest.TestCase):
    def scan(self, text):
        return LINT.lint_text(text)

    def has(self, text, rule, kind="Confirmed"):
        result = self.scan(text)
        self.assertTrue(any(f["rule_id"] == rule and f["type"] == kind for f in result["findings"]), result)

    def test_indexed_math_is_not_a_reference_link(self):
        result = self.scan("状态为 $dp[i][j]$。\n")
        self.assertFalse(any(f["rule_id"] == "MATH002" for f in result["findings"]))
        self.has("状态为 $dp[i][j]$。\n", "TEX007")

    def test_math_inside_visible_link_label_stays_math(self):
        result = self.scan("参考 [区间 $[l,r]$](https://example.org)。\n")
        self.assertFalse(any(f["rule_id"] == "MATH002" for f in result["findings"]))

    def test_escaped_brackets_in_problem_title_are_not_math(self):
        result = self.scan(r"参考 [B1234 \[某场比赛\] 标题](/problem/B1234)。" + "\n")
        self.assertFalse(any(f["rule_id"] in ("MATH002", "TEX005") for f in result["findings"]))

    def test_required_heading_and_list_gaps_are_not_extra_spaces(self):
        result = self.scan("## （一）算法\n\n1. （一）第一步。\n2. （二）第二步。\n")
        self.assertFalse(any(f["rule_id"] == "TXT003" for f in result["findings"]))

    def test_paired_emphasis_does_not_hide_missing_spaces(self):
        for text in ("中文**English**。\n", "**English**中文。\n"):
            with self.subTest(text=text):
                result = self.scan(text)
                group = next(g for g in result["format_assessment"]["groups"] if g["category"] == "missing_space")
                self.assertEqual(group["confirmed_count"], 1)

    def test_link_markup_does_not_hide_missing_boundary(self):
        self.has("中文[English](https://example.org)。\n", "TXT001")

    def test_inline_code_literal_context_is_not_forced_into_math(self):
        result = self.scan("输出字符串 `动态规划`，代码 `x+1`。\n")
        self.assertEqual(result["findings"], [])

    def test_inline_formula_misusing_code_is_reported(self):
        self.has("新位置 = `2x - 1`。\n", "MATH003")

    def test_code_purpose_ambiguity_is_not_confirmed(self):
        self.has("这里强调 `动态规划`。\n", "MD007", "Warning")

    def test_chinese_quotes_are_in_extra_space_rules(self):
        result = self.scan("算法 “名称” 说明。\n")
        group = next(g for g in result["format_assessment"]["groups"] if g["category"] == "extra_space")
        self.assertEqual(group["confirmed_count"], 2)

    def test_literal_math_bar_is_not_a_markdown_table(self):
        self.has("结论 $|x|$ 。\n", "TXT003")

    def test_table_alignment_does_not_hide_content_spacing_error(self):
        text = "| 项目 | 内容 |\n| --- | --- |\n| 标签 | 中文  English |\n"
        result = self.scan(text)
        findings = [f for f in result["findings"] if f["rule_id"] == "TXT003"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["line"], 3)

    def test_sentence_end_is_checked_but_heading_is_exempt(self):
        self.has("算法可以处理所有状态，因此答案正确\n", "TXT005")
        self.assertEqual(self.scan("## 算法可以处理所有状态\n")["findings"], [])

    def test_short_list_labels_do_not_require_periods(self):
        self.assertEqual(self.scan("- 正确性\n- 复杂度\n")["findings"], [])

    def test_soft_break_warns_without_fabricating_bad_rendering(self):
        self.has("这是第一行\n这是第二行。\n", "TXT006", "Warning")
        for text in ("第一行。  \n第二行。\n", "第一行。\\\n第二行。\n", "第一行。\n\n第二行。\n"):
            with self.subTest(text=text):
                self.assertFalse(any(f["rule_id"] == "TXT006" for f in self.scan(text)["findings"]))

    def test_missing_list_marker_spaces_in_ordered_sequence(self):
        result = self.scan("1.第一项\n\n2.第二项\n")
        findings = [f for f in result["findings"] if f["rule_id"] == "MD003"]
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f["type"] == "Confirmed" for f in findings))

    def test_list_detachment_is_uncertain(self):
        self.has("- 第一项\n\n未缩进的解释。\n\n- 第二项\n", "MD006", "Warning")

    def test_empty_heading_is_confirmed(self):
        self.has("### \n", "MD001")

    def test_step_heading_without_body_is_not_blindly_confirmed(self):
        text = "## （1）如果状态满足这里所说明的条件，则加入下一次需要处理的队列。\n## （2）结束\n"
        self.has(text, "MD005", "Warning")

    def test_latex_functions_are_checked_outside_text_and_upright_commands(self):
        self.has("公式 $log n+max(a,b)+ans(k,p)$。\n", "TEX004")
        result = self.scan(r"公式 $\log n+\max(a,b)+\operatorname{ans}(k,p)+\mathrm{min}+\text{max}$。" + "\n")
        self.assertFalse(any(f["rule_id"] == "TEX004" for f in result["findings"]))

    def test_environment_mismatch_is_one_occurrence(self):
        result = self.scan(r"公式 $\begin{bmatrix}x\end{cases}$。" + "\n")
        group = next(g for g in result["format_assessment"]["groups"] if g["category"] == "math_delimiter")
        self.assertEqual(group["confirmed_count"], 1)

    def test_tex_text_chinese_is_exempt_but_raw_chinese_is_reported(self):
        self.has("公式 $x+中文说明$。\n", "TEX005")
        result = self.scan(r"公式 $x+\text{中文说明}$。" + "\n")
        self.assertEqual(result["findings"], [])

    def test_whole_chinese_sentence_in_math_is_excess_math(self):
        self.has("说明 $这是普通叙述$。\n", "MATH004")

    def test_fullwidth_math_punctuation_outside_text(self):
        self.has("公式 $x，y$。\n", "TEX006")

    def test_math_ellipsis(self):
        self.has("序列 $a_1,a_2,...,a_n$。\n", "TEX008")
        self.assertEqual(self.scan(r"序列 $a_1,a_2,\ldots,a_n$。" + "\n")["findings"], [])

    def test_constants_not_exponential_bases_are_rejected(self):
        for formula in ("O(2n)", r"O(3n\log n)", r"O(2\cdot n)"):
            with self.subTest(formula=formula):
                self.has("复杂度为 $" + formula + "$。\n", "TEX009")
        for formula in ("O(1)", "O(n^2)", "O(2^n)"):
            with self.subTest(formula=formula):
                self.assertFalse(any(f["rule_id"] == "TEX009" for f in self.scan("复杂度为 $" + formula + "$。\n")["findings"]))

    def test_plain_complexity_also_needs_math_mode(self):
        self.has("复杂度为 O(2n)。\n", "MATH003")
        self.has("复杂度为 O(2n)。\n", "TEX009")

    def test_sum_index_equality_is_not_an_equation_chain(self):
        result = self.scan(r"求和 $S=\sum_{i=1}^{n}a_i$。" + "\n")
        self.assertFalse(any(f["rule_id"] == "TEX010" for f in result["findings"]))
        self.has("推导为 $a=b=c$。\n", "TEX010")
        self.has("推导为 $f(a,b)=g(c,d)=h(e,f)$。\n", "TEX010")
        self.assertFalse(any(f["rule_id"] == "TEX010" for f in self.scan("条件 $x=1,y=2$。\n")["findings"]))

    def test_escaped_underscore_is_not_an_unbraced_index(self):
        result = self.scan(r"阈值 $\mathrm{min\_val}$。" + "\n")
        self.assertFalse(any(f["rule_id"] == "TEX011" for f in result["findings"]))

    def test_duplicated_standalone_multiplication_signs(self):
        self.has("收益。\n×\n×\n深度。\n", "TEX007")
        self.has("节点初始石子数\n×\n× 它在树中的深度。\n", "TEX007")
        self.assertFalse(any(f["rule_id"] == "TEX007" for f in self.scan("石子数\n×\n深度。\n")["findings"]))

    def test_index_grouping_and_large_number_are_warnings(self):
        self.has("公式 $a_ab$。\n", "TEX011", "Warning")
        self.has("常数 $123456$。\n", "TEX012", "Warning")

    def test_standalone_inline_formula_requires_display(self):
        self.has("$x+y$\n", "TEX014")
        self.assertFalse(any(f["rule_id"] == "TEX014" for f in self.scan("结果为 $x+y$。\n")["findings"]))

    def test_image_with_extra_link_is_reported(self):
        self.has("[![说明](https://cdn.luogu.com.cn/x.png)](https://example.org)\n", "MD009")

    def test_raw_url_is_reported_but_destination_and_autolink_are_not(self):
        self.has("参考 https://example.org。\n", "MD008")
        for text in ("参考 [说明](https://example.org)。\n", "<https://example.org>\n"):
            with self.subTest(text=text):
                self.assertFalse(any(f["rule_id"] == "MD008" for f in self.scan(text)["findings"]))

    def test_unfolded_long_code_warns_but_folded_does_not(self):
        text = "```cpp\n" + "int x;\n" * 81 + "```\n"
        self.has(text, "MD011", "Warning")
        folded = ":::details[代码]\n" + text + ":::\n"
        self.assertFalse(any(f["rule_id"] == "MD011" for f in self.scan(folded)["findings"]))

    def test_dense_emphasis_is_a_warning_not_proof_of_bad_style(self):
        self.has("**甲** *乙* **丙** *丁* **戊**。\n", "MD012", "Warning")

    def test_rule_catalog_is_machine_readable(self):
        run = subprocess.run([sys.executable, str(SCRIPT), "--rules"], check=True,
                             capture_output=True, text=True)
        data = json.loads(run.stdout)
        self.assertEqual(len(data["rules"]), len(LINT.RULES))
        self.assertEqual(data["format_assessment"]["verdict"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
