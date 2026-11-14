"""Round-two checks of visible characters, source coordinates and link syntax."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("format_visible_text", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class VisibleTextTests(unittest.TestCase):
    def scan(self, source):
        return LINT.lint_text(source)

    def test_initial_thematic_rule_is_not_unclosed_yaml(self):
        for source in ("---\n\n正文正确。\n", "---\n\n正文正确。\n\n---\n"):
            with self.subTest(source=source):
                self.assertEqual(self.scan(source)["format_assessment"]["verdict"], "pass")

    def test_real_metadata_and_unclosed_metadata_are_distinct(self):
        valid = self.scan("---\ntitle: 中文English\n---\n\n正文正确。\n")
        self.assertEqual(valid["findings"], [])
        invalid = self.scan("---\ntitle: 中文English\n")
        self.assertEqual(invalid["format_assessment"]["verdict"], "non_compliant")
        self.assertTrue(any(s["unverified"] for s in invalid["skipped"]))

    def test_reference_character_is_not_its_source_semicolon(self):
        self.assertEqual(self.scan("中文&amp;后文。\n")["findings"], [])

    def test_encoded_latin_boundary_keeps_original_positions(self):
        source = "中文&#65;中文。\n"
        r = self.scan(source)
        fs = [f for f in r["findings"] if f["rule_id"] == "TXT001"]
        self.assertEqual([(f["column"], f["excerpt"]) for f in fs], [(2, "文&#65;"), (3, "&#65;中")])
        g = next(g for g in r["format_assessment"]["groups"] if g["category"] == "missing_space")
        self.assertEqual((g["confirmed_count"], g["severity"]), (2, "Major"))

    def test_encoded_han_boundary_points_after_complete_entity(self):
        r = self.scan("&#20013;English。\n")
        f = next(f for f in r["findings"] if f["rule_id"] == "TXT001")
        self.assertEqual((f["offset"], f["end_offset"], f["occurrence_key"]), (0, 9, "8"))

    def test_two_character_entity_does_not_duplicate_a_physical_gap(self):
        r = self.scan("中文&fjlig;中文。\n")
        g = next(g for g in r["format_assessment"]["groups"] if g["category"] == "missing_space")
        self.assertEqual(g["confirmed_count"], 2)
        self.assertTrue(all(f["excerpt"] in ("文&fjlig;", "&fjlig;中") for f in r["findings"]))

    def test_numeric_references_match_native_visible_character_categories(self):
        for char in ("A", "9", "，", " ", "\u00a0", "\u3000", "𠮷", "∑", "&"):
            with self.subTest(char=char):
                native = self.scan("中文" + char + "后文。\n")
                encoded = self.scan("中文&#" + str(ord(char)) + ";后文。\n")
                signature = lambda r: sorted((f["category"], f["type"]) for f in r["findings"])
                self.assertEqual(signature(encoded), signature(native))

    def test_encoded_space_satisfies_boundary_space(self):
        self.assertEqual(self.scan("中文&#32;English。\n")["findings"], [])

    def test_encoded_ascii_punctuation_reports_the_whole_entity(self):
        fs = self.scan("中文&#44;随后。\n")["findings"]
        self.assertEqual([(f["rule_id"], f["excerpt"]) for f in fs], [("TXT002", "&#44;")])

    def test_encoded_sentence_period_is_seen_as_terminal_punctuation(self):
        self.assertFalse(any(f["rule_id"] == "TXT005" for f in self.scan("算法可以处理全部状态&#12290;\n")["findings"]))

    def test_encoded_mathematical_expression_and_constant_factor_are_checked(self):
        self.assertTrue(any(f["rule_id"] == "MATH003" for f in self.scan("计算 x&#61;1。\n")["findings"]))
        r = self.scan("复杂度为 O(&#50;n)。\n")
        self.assertTrue(any(f["rule_id"] == "TEX009" and f["excerpt"] == "O(&#50;" for f in r["findings"]))

    def test_encoded_operator_is_not_allowed_to_bypass_math_mode(self):
        self.assertTrue(any(f["rule_id"] == "MATH003" for f in self.scan("求和符号为 &#8721;。\n")["findings"]))

    def test_references_inside_code_are_literal_and_not_decoded(self):
        self.assertEqual(self.scan("代码 `中文&#65;`。\n")["findings"], [])

    def test_escaped_entity_spelling_is_literal(self):
        self.assertEqual(self.scan(r"说明 \&amp; 后文。" + "\n")["findings"], [])

    def test_unknown_named_reference_is_not_partially_decoded(self):
        r = self.scan("中文&notanentity;后文。\n")
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["format_assessment"]["verdict"], "non_compliant")
        self.assertFalse(r["format_assessment"]["complete"])

    def test_encoded_newline_does_not_create_a_source_line(self):
        r = self.scan("中文&#10;English。\n")
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["format_assessment"]["verdict"], "pass")

    def test_encoded_reserved_or_invisible_characters_are_unverified(self):
        for spelling in ("&#57344;", "&#0;", "&#x200B;", "&#00000065;"):
            with self.subTest(spelling=spelling):
                r = self.scan("中文" + spelling + "English。\n")
                self.assertEqual(r["format_assessment"]["verdict"], "non_compliant")
                self.assertTrue(any(s.get("unverified") for s in r["skipped"]))

    def test_extended_han_and_ideographic_zero_are_not_latin(self):
        for han in ("𠮷", "𰀀", "〇"):
            with self.subTest(han=han):
                self.assertTrue(any(f["rule_id"] == "TXT001" for f in self.scan(han + "English。\n")["findings"]))

    def test_nonbreaking_and_thin_spaces_next_to_punctuation_are_confirmed(self):
        for gap in ("\u00a0", "\u2009", "\u202f"):
            with self.subTest(gap=repr(gap)):
                fs = self.scan("成立，" + gap + "继续。\n")["findings"]
                self.assertEqual([(f["rule_id"], f["type"]) for f in fs], [("TXT003", "Confirmed")])

    def test_special_boundary_space_has_unverified_intent(self):
        r = self.scan("中文\u00a0English。\n")
        self.assertTrue(any(f["rule_id"] == "TXT004" and f["type"] == "Warning" for f in r["findings"]))

    def test_encoded_fullwidth_word_space_is_the_same_extra_space_category(self):
        r = self.scan("词&#x3000;句。\n")
        self.assertEqual([(g["category"], g["confirmed_count"]) for g in r["format_assessment"]["groups"]], [("extra_space", 1)])

    def test_fullwidth_reference_preserves_uncertainty(self):
        r = self.scan("示例 &#xFF21;。\n")
        self.assertEqual([(f["rule_id"], f["type"]) for f in r["findings"]], [("TXT004", "Warning")])

    def test_ambiguous_formula_does_not_join_text_into_a_false_spacing_error(self):
        r = self.scan("公式 $ x $。\n")
        self.assertTrue(all(f["type"] == "Warning" for f in r["findings"]))
        self.assertFalse(r["format_assessment"]["complete"])

    def test_unclosed_formula_keeps_its_unverified_scope(self):
        r = self.scan("$$\nx+y\n")
        self.assertFalse(r["format_assessment"]["complete"])
        self.assertEqual(r["format_assessment"]["format_deduction"], 2)

    def test_opaque_inline_content_does_not_join_text_across_it(self):
        for source in ('参考 [说明](not a URL)。\n', '参考 ![说明](https://example.org/x.png)。\n', '参考 `unclosed\n'):
            with self.subTest(source=source):
                r = self.scan(source)
                self.assertFalse(any(f["rule_id"] == "TXT003" and f["type"] == "Confirmed" for f in r["findings"]))

    def test_hidden_html_children_are_unverified_not_visible_spacing_facts(self):
        for html in ('<span hidden>中文English</span>', '<span style="display:none">中文English</span>',
                     '<span hidden><span>正文</span>中文English</span>', '<span hidden>\n\n中文English',
                     '<span hidden><!-- </span> -->中文English</span>', '<span hidden/>中文English</span>'):
            source = "说明 " + html + "。\n"
            with self.subTest(html=html):
                r = self.scan(source)
                self.assertFalse(any(f["category"] == "missing_space" for f in r["findings"]))
                self.assertFalse(r["format_assessment"]["complete"])
                scopes = [s for s in r["skipped"] if s.get("unverified")]
                self.assertTrue(any('中文English' in source[s["offset"]:s["end_offset"]] for s in scopes))

    def test_visible_prose_after_closed_html_remains_checked(self):
        r = self.scan('说明 <span hidden>隐藏文字</span>，中文English。\n')
        self.assertTrue(any(f["rule_id"] == "TXT001" for f in r["findings"]))

    def test_snake_case_names_are_ambiguous_in_both_native_and_encoded_text(self):
        for spelling in ('foo_bar', 'foo&#95;bar', 'dp_i'):
            with self.subTest(spelling=spelling):
                findings = [f for f in self.scan('名称为 ' + spelling + '。\n')["findings"] if f["rule_id"] == "MATH003"]
                self.assertTrue(findings)
                self.assertTrue(all(f["type"] == "Warning" for f in findings))


class LinkSyntaxTests(unittest.TestCase):
    def test_invalid_destination_and_undefined_reference_never_pass_as_links(self):
        for source in ("参考 [标题](not a URL)。\n", "参考 [标题](foo\\ bar)。\n", "参考 [标题][missing]。\n", "参考 [标题](\n"):
            with self.subTest(source=source):
                r = LINT.lint_text(source)
                self.assertTrue(any(f["rule_id"] == "MD008" and f["type"] == "Warning" for f in r["findings"]))

    def test_supported_destination_titles_and_empty_link(self):
        for target in ('https://example.org "标题"', "url (title)", "<foo bar>", '"title"', "foo<bar", "", " foo "):
            with self.subTest(target=target):
                self.assertEqual(LINT.lint_text("参考 [说明](" + target + ")。\n")["findings"], [])

    def test_reference_labels_are_normalized_but_destinations_remain_unverified(self):
        r = LINT.lint_text("参考 [说明][A B]。\n\n[a  b]: https://example.org\n")
        self.assertFalse(any(f["rule_id"] == "MD008" for f in r["findings"]))
        self.assertFalse(r["format_assessment"]["complete"])

    def test_uppercase_bare_url_and_autolink_are_distinct(self):
        bare = LINT.lint_text("参考 HTTPS://example.org。\n")
        self.assertEqual([(f["rule_id"], f["type"]) for f in bare["findings"]], [("MD008", "Confirmed")])
        auto = LINT.lint_text("参考 <HTTPS://example.org>。\n")
        self.assertEqual(auto["findings"], [])

    def test_incomplete_scheme_followed_by_period_is_not_a_confirmed_url(self):
        r = LINT.lint_text("参考 https://。\n")
        self.assertEqual([(f["rule_id"], f["type"]) for f in r["findings"]], [("MD008", "Warning")])

    def test_image_destination_with_title_keeps_host_not_title(self):
        r = LINT.lint_text('![说明](https://cdn.luogu.com.cn/x.png "中文 title")\n')
        self.assertFalse(any(f["rule_id"] == "MD010" for f in r["findings"]))


if __name__ == "__main__":
    unittest.main()
