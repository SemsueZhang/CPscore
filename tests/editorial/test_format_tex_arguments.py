"""Required TeX arguments without replacing the target math renderer."""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("tex_arguments", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class TexArgumentTests(unittest.TestCase):
    def scan(self, math):
        return LINT.lint_text("公式 $" + math + "$。\n")

    def arguments(self, math):
        return [f for f in self.scan(math)["findings"] if f["rule_id"] == "TEX015"]

    def test_missing_required_argument_at_formula_end(self):
        for math in (r"\frac{1}", r"\frac", r"\sqrt", r"\text", r"\hat", r"\overset{a}",
                     r"\operatorname*", r"\textcolor{red}", r"\color"):
            with self.subTest(math=math):
                findings = self.arguments(math)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]["type"], "Confirmed")

    def test_valid_grouped_and_atomic_arguments(self):
        for math in (r"\frac{a}{b}", r"\frac a b", r"\frac\alpha\beta", r"\frac12", r"\frac{}{}",
                     r"\sqrt{x}", r"\sqrt x", r"\sqrt[3]{x}", r"\sqrt[{[3]}]{x}",
                     r"\operatorname*{f}(x)", r"\text{中文}", r"\hat\alpha", r"\pmod b",
                     r"\overset{a}{b}", r"\stackrel{!}{=}", r"\color{red}x", r"\textcolor{red}{x}"):
            with self.subTest(math=math):
                self.assertEqual(self.arguments(math), [])

    def test_group_closing_and_environment_end_do_not_supply_arguments(self):
        for math in (r"{\frac{1}}", r"\begin{matrix}\sqrt\end{matrix}", r"\frac1_2", r"\frac1&x"):
            with self.subTest(math=math):
                self.assertTrue(any(f["type"] == "Confirmed" for f in self.arguments(math)))

    def test_unclosed_group_is_not_a_second_argument_error(self):
        result = self.scan(r"\frac{1}{")
        self.assertTrue(any(f["rule_id"] == "TEX002" for f in result["findings"]))
        self.assertFalse(any(f["rule_id"] == "TEX015" for f in result["findings"]))

    def test_root_optional_index_must_close_and_still_needs_radicand(self):
        for math in (r"\sqrt[3", r"\sqrt[3]", r"\sqrt[3]\end{matrix}"):
            with self.subTest(math=math):
                self.assertTrue(any(f["type"] == "Confirmed" for f in self.arguments(math)))

    def test_unbraced_composite_arguments_defer_to_llm(self):
        for math in (r"\frac\sqrt{a}{b}", r"\sqrt\frac12", r"\sqrt[1+[2]]{x}", r"\sqrt[\frac{1}]{x}"):
            with self.subTest(math=math):
                self.assertTrue(self.arguments(math))
                self.assertTrue(all(f["type"] == "Warning" for f in self.arguments(math)))

    def test_macro_expansion_does_not_create_false_text_and_punctuation_facts(self):
        for math in (r"\custom{中文，正文}", r"\begin{custom}中文，正文\end{custom}"):
            with self.subTest(math=math):
                result = self.scan(math)
                self.assertTrue(result["findings"])
                self.assertTrue(all(f["type"] == "Warning" for f in result["findings"]))
                self.assertFalse(result["format_assessment"]["complete"])

    def test_prior_macro_redefinition_is_not_assumed_local_to_one_formula(self):
        result = LINT.lint_text(r"公式 $\gdef\sqrt{X}$，另式 $\sqrt$。" + "\n")
        self.assertFalse(any(f["type"] == "Confirmed" for f in result["findings"]))
        self.assertTrue(any('此前宏' in f['suggestion'] for f in result["findings"]))

    def test_context_sensitive_commands_do_not_pass_on_name_alone(self):
        for math in (r"x\limits", r"\nolimits", r"\color{unknown}x", r"\textcolor{unknown}{x}", r"\hline", r"\cr"):
            with self.subTest(math=math):
                self.assertNotEqual(self.scan(math)["format_assessment"]["verdict"], "pass")

    def test_middle_requires_an_active_left_right_pair(self):
        result = self.scan(r"x\middle|y")
        self.assertTrue(any(f["rule_id"] == "TEX001" and f["type"] == "Confirmed" for f in result["findings"]))
        self.assertEqual(self.scan(r"\left(x\middle|y\right)")["findings"], [])

    def test_unknown_and_custom_macros_do_not_create_confirmed_syntax_facts(self):
        for math in (r"\custom\frac{1}", r"\newcommand{\frac}{x}\frac"):
            with self.subTest(math=math):
                self.assertTrue(self.scan(math)["findings"])
                self.assertTrue(all(f["type"] == "Warning" for f in self.arguments(math)))

    def test_environment_required_parameters(self):
        for env in ("array", "alignedat", "alignat", "alignat*"):
            with self.subTest(env=env):
                missing = self.arguments("\\begin{" + env + "}x\\end{" + env + "}")
                self.assertEqual(len(missing), 1)
                self.assertEqual(missing[0]["type"], "Confirmed")
                parameter = "cc" if env == "array" else "2"
                valid = self.arguments("\\begin{" + env + "}{" + parameter + "}x\\end{" + env + "}")
                self.assertEqual(valid, [])

    def test_complex_environment_parameter_remains_unverified(self):
        for math in (r"\begin{array}{*{2}{c}}x\end{array}", r"\begin{array}{}x\end{array}",
                     r"\begin{alignedat}{0}x\end{alignedat}", r"\begin{array}[t]{cc}x\end{array}"):
            with self.subTest(math=math):
                self.assertTrue(self.arguments(math))
                self.assertTrue(all(f["type"] == "Warning" for f in self.arguments(math)))

    def test_missing_environment_name(self):
        self.assertEqual(self.arguments(r"\begin")[0]["type"], "Confirmed")
        self.assertEqual(self.arguments(r"\end")[0]["type"], "Confirmed")

    def test_delimiter_commands_need_delimiters(self):
        for math in (r"\left x\right y", r"\big", r"\left", r"\right"):
            with self.subTest(math=math):
                self.assertTrue(any(f["type"] == "Confirmed" and f["category"] == "math_delimiter" for f in self.scan(math)["findings"]))
        for math in (r"\left\{x\right.", r"\left(x\right)", r"\Bigl\langle x\Bigr\rangle"):
            with self.subTest(math=math):
                self.assertEqual(self.arguments(math), [])

    def test_commands_without_verified_reference_support_are_not_silent(self):
        for command in ("array", "cases", "multicolumn", "cline", "newenvironment", "renewenvironment",
                        "infinity", "spacing", "percent", "lcm", "mbox"):
            with self.subTest(command=command):
                result = self.scan("\\" + command + "{x}")
                self.assertTrue(any(f["rule_id"] == "TEX013" for f in result["findings"]))

    def test_unverified_environments_do_not_silently_pass(self):
        for env in ("gather*", "multline", "multline*"):
            with self.subTest(env=env):
                result = self.scan("\\begin{" + env + "}x\\end{" + env + "}")
                self.assertTrue(any(f["rule_id"] == "TEX001" and f["type"] == "Warning" for f in result["findings"]))

    def test_distinct_missing_parameters_count_by_command_not_argument(self):
        result = self.scan(r"{\frac}{\sqrt}{\overset}")
        group = next(g for g in result["format_assessment"]["groups"] if g["category"] == "math_arguments")
        self.assertEqual((group["confirmed_count"], group["severity"]), (3, "Fatal"))

    def test_verbatim_comment_code_and_plain_text_are_not_argument_calls(self):
        for math in (r"\verb|\frac|", "x % " + r"\sqrt"):
            with self.subTest(math=math):
                self.assertEqual(self.arguments(math), [])
        self.assertEqual(LINT.lint_text("代码 `\\sqrt`。\n")["findings"], [])


if __name__ == "__main__":
    unittest.main()
