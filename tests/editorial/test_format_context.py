"""Source-context regressions for deterministic format checks (no model calls)."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("format_context", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class ContextTests(unittest.TestCase):
    def findings(self, source, rule):
        return [f for f in LINT.lint_text(source)["findings"] if f["rule_id"] == rule]

    def test_confirmed_softbreak_has_whitespace_model_and_source_edges(self):
        fs = self.findings("假设我们已经找到答案。\n对于每座矿脉进行计算。\n", "TXT006")
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["type"], "Confirmed")
        self.assertEqual(fs[0]["evidence"], {"render_model": LINT.RENDER_MODEL,
                         "rendered_gap": " ", "left": "。", "right": "对"})

    def test_softbreak_before_chinese_punctuation_is_confirmed(self):
        self.assertEqual(self.findings("得到最终的答案\n，继续计算。\n", "TXT006")[0]["type"], "Confirmed")

    def test_softbreak_after_formula_punctuation_is_confirmed(self):
        self.assertEqual(self.findings("答案为 $x$，\n继续计算。\n", "TXT006")[0]["type"], "Confirmed")

    def test_three_confirmed_breaks_count_three_physical_gaps(self):
        r = LINT.lint_text("第一行。\n第二行。\n第三行。\n第四行。\n")
        g = next(g for g in r["format_assessment"]["groups"] if g["category"] == "soft_break")
        self.assertEqual((g["confirmed_count"], g["severity"]), (3, "Fatal"))

    def test_latin_reflow_is_not_confirmed_as_broken_format(self):
        fs = self.findings("This is a normally wrapped\nEnglish paragraph.\n", "TXT006")
        self.assertTrue(all(f["type"] == "Warning" for f in fs))

    def test_breaks_between_list_items_or_around_block_html_are_not_softbreaks(self):
        for s in ("- 第一项。\n- 第二项。\n", "正文。\n<div>未知渲染</div>\n下一段。\n"):
            with self.subTest(source=s):
                self.assertEqual(self.findings(s, "TXT006"), [])

    def test_new_blockquote_is_not_a_continuation_of_plain_paragraph(self):
        self.assertEqual(self.findings("正文已经结束。\n> 这里开始一个引用块。\n", "TXT006"), [])

    def test_escaped_backslash_does_not_create_a_hardbreak(self):
        fs = self.findings("第一行\\\\\n第二行。\n", "TXT006")
        self.assertEqual([f["type"] for f in fs], ["Warning"])

    def test_softbreak_in_code_and_display_math_is_opaque(self):
        self.assertEqual(self.findings("```text\n甲。\n乙。\n```\n\n$$\n甲。\n乙。\n$$\n", "TXT006"), [])

    def test_link_label_terminal_punctuation_is_not_lost(self):
        self.assertEqual(self.findings("算法可以参考 [这里的说明。](https://example.org)\n", "TXT005"), [])

    def test_inline_code_semicolon_is_not_chinese_sentence_punctuation(self):
        fs = self.findings("算法可以输出 `x;`\n", "TXT005")
        self.assertEqual([f["type"] for f in fs], ["Confirmed"])

    def test_math_is_not_removed_from_sentence_end_context(self):
        fs = self.findings("算法的最终答案为\n$x$。\n", "TXT005")
        self.assertEqual(fs, [])

    def test_incomplete_conditional_is_not_confirmed_as_a_sentence(self):
        fs = self.findings("如果\n𝑘\n>\n1\n", "TXT005")
        self.assertFalse(any(f["type"] == "Confirmed" for f in fs))

    def test_prior_sentence_does_not_complete_a_dangling_final_condition(self):
        fs = self.findings("其实算法可以完成计算。\n如果\n𝑘\n>\n1\n", "TXT005")
        self.assertFalse(any(f["type"] == "Confirmed" for f in fs))

    def test_dangling_predicate_is_not_a_confirmed_complete_sentence(self):
        for source in ("我们将状态改为\n", "因此我们现在可以\n"):
            with self.subTest(source=source):
                self.assertFalse(any(f["type"] == "Confirmed" for f in self.findings(source, "TXT005")))

    def test_algorithm_subject_and_given_input_clause_are_complete_sentences(self):
        for source in ("BFS 是这里使用的最短路算法\n", "给定一个数组，要求输出最终答案\n"):
            with self.subTest(source=source):
                self.assertEqual(self.findings(source, "TXT005")[0]["type"], "Confirmed")

    def test_explicit_instruction_sentences_are_confirmed(self):
        for s in ("本题略微复杂新手可不做\n", "因第一题原因讲解[基本框架](https://example.org)内容\n", "希望管理员尽快通过\n"):
            with self.subTest(source=s):
                self.assertEqual(self.findings(s, "TXT005")[0]["type"], "Confirmed")

    def test_label_and_punctuated_quote_do_not_need_extra_periods(self):
        for s in ("**前置知识**\n", "- 正确性与复杂度\n", "我们将其称为“最终答案。”\n"):
            with self.subTest(source=s):
                self.assertEqual(self.findings(s, "TXT005"), [])

    def test_lazy_list_continuation_does_not_leave_the_item(self):
        self.assertEqual(self.findings("- 第一项。\n这行仍然属于前面的项目。\n- 第二项。\n", "MD006"), [])

    def test_wide_ordered_marker_allows_indented_prose(self):
        r = LINT.lint_text("10. 第一项。\n\n    中文English。\n\n11. 第二项。\n")
        self.assertTrue(any(f["rule_id"] == "TXT001" and f["line"] == 3 for f in r["findings"]))
        self.assertFalse(any(s.get("unverified") for s in r["skipped"]))

    def test_nested_fenced_code_is_opaque_and_closes_normally(self):
        r = LINT.lint_text("10. 第一项。\n\n    ```text\n    中文English,数据2\n    ```\n\n11. 第二项。\n")
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["format_assessment"]["verdict"], "pass")

    def test_three_numbered_action_headings_without_body_are_confirmed(self):
        s = "# 算法\n## （1）初始化集合为空集。\n## （2）从集合中选择一个元素。\n## （3）将新的元素放入集合。\n"
        fs = self.findings(s, "MD005")
        self.assertEqual(len(fs), 3)
        self.assertTrue(all(f["type"] == "Confirmed" for f in fs))

    def test_numbered_chapters_with_body_are_not_step_headings(self):
        s = "## （1）初始化集合为空集。\n\n这里说明初始化的具体原因。\n\n## （2）从哪里开始？\n\n这里介绍选择起点的依据。\n"
        self.assertEqual(self.findings(s, "MD005"), [])

    def test_fragmented_operator_chain_is_one_occurrence(self):
        fs = self.findings("约束为 $2$ $\\leq$ $n$ $\\leq$ $10$。\n", "MATH005")
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["type"], "Confirmed")

    def test_separate_quantities_and_code_are_not_a_fragmented_formula(self):
        for s in ("变量 $x$、$y$，数组 $a$ $b$。\n", "代码 `$x$ $+$ $y$`。\n", "公式 $x+y$。\n"):
            with self.subTest(source=s):
                self.assertEqual(self.findings(s, "MATH005"), [])

    def test_explicit_assignments_in_prose_and_math(self):
        for s in ("更新 a_k = a_k + x。\n", "更新 $a_k=a_k+x$。\n", "初始化 $Q=\\{i\\}$。\n"):
            with self.subTest(source=s):
                self.assertEqual([f["type"] for f in self.findings(s, "TEX007")], ["Confirmed"])

    def test_definitions_conditions_and_real_code_are_not_assignments(self):
        for s in ("定义 $f(x)=x+1$。\n", "若 $x=1$，则返回。\n", "代码更新 `x=1`。\n"):
            with self.subTest(source=s):
                self.assertEqual(self.findings(s, "TEX007"), [])

    def test_unknown_multiletter_product_is_not_confirmed_as_function_name(self):
        fs = self.findings("公式 $ab(c+d)$。\n", "TEX004")
        self.assertEqual([f["type"] for f in fs], ["Warning"])

    def test_concept_code_style_is_distinct_from_literal_strings(self):
        self.assertEqual(self.findings("## `动态规划`分类\n", "MD007")[0]["type"], "Confirmed")
        self.assertEqual(self.findings("全称 `Dynamic Programming`。\n", "MD007")[0]["type"], "Confirmed")
        self.assertEqual(self.findings("输出字符串 `动态规划`。\n", "MD007"), [])

    def test_chinese_punctuation_after_protected_math_or_code_is_checked(self):
        for s in ("答案为 $x$,继续计算。\n", "调用 `solve`!\n", "采用 BFS,继续遍历。\n"):
            with self.subTest(source=s):
                self.assertEqual(len(self.findings(s, "TXT002")), 1)

    def test_english_punctuation_inside_quoted_english_is_not_chinese_punctuation(self):
        self.assertEqual(self.findings('说明为“English, with punctuation!”。\n', "TXT002"), [])

    def test_confirmed_fact_suppresses_same_occurrence_warning(self):
        s = LINT.Scanner("abc", "a.md")
        s.add("MD005", 0, 1, "uncertain", "Warning")
        s.add("MD005", 0, 1, "confirmed")
        s.add("MD005", 0, 1, "uncertain", "Warning")
        self.assertEqual([f["type"] for f in s.findings], ["Confirmed"])
        r = LINT.format_assessment(s.findings)
        self.assertEqual(r["groups"][0]["unconfirmed_count"], 0)

    def test_empty_image_destination_does_not_abort_scanning(self):
        r = LINT.lint_text("![说明]()\n\n中文English。\n")
        self.assertTrue(any(f["rule_id"] == "TXT001" for f in r["findings"]))
        self.assertTrue(any(s.get("unverified") for s in r["skipped"]))

    def test_url_scheme_without_host_is_unverified_and_scan_continues(self):
        for scheme in ("http://", "https://"):
            with self.subTest(scheme=scheme):
                r = LINT.lint_text("协议 " + scheme + "\n\n中文English。\n")
                self.assertTrue(any(f["rule_id"] == "MD008" and f["type"] == "Warning" for f in r["findings"]))
                self.assertTrue(any(f["rule_id"] == "TXT001" for f in r["findings"]))


if __name__ == "__main__":
    unittest.main()
