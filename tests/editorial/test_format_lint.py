"""Run: python3 -m unittest discover -s tests/editorial -v"""

import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("editorial_format_lint", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class FormatLintTests(unittest.TestCase):
    def scan(self, text):
        return LINT.lint_text(text, "题解.md")

    def confirmed(self, text):
        return [f for f in self.scan(text)["findings"] if f["type"] == "Confirmed"]

    def test_normal_mixed_prose(self):
        text = "# 思路\n\n使用 BFS 遍历，访问次数为 $n$。\n\nEnglish text with 42 words.\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_spacing_and_unicode_locations(self):
        findings = self.confirmed("# 思路\n\n使用BFS，处理2次。\n")
        gaps = [f for f in findings if f["rule_id"] == "TXT001"]
        self.assertEqual([(f["line"], f["column"]) for f in gaps], [(3, 2), (3, 8), (3, 9)])
        for finding in gaps:
            self.assertEqual(finding["file"], "题解.md")
            self.assertTrue(finding["excerpt"])
            self.assertTrue(finding["standard"])
            self.assertTrue(finding["suggestion"])

    def test_unambiguous_ascii_punctuation(self):
        for mark in (",", ";", ":", "!", "?", "."):
            with self.subTest(mark=mark):
                self.assertIn("TXT002", [f["rule_id"] for f in self.confirmed("成立" + mark + "\n")])
        self.assertEqual(self.scan("思考...\n\nEnglish, with punctuation!\n")["findings"], [])

    def test_missing_formula_boundary_spaces(self):
        findings = self.confirmed("得到$x$结果。\n")
        self.assertEqual([f["rule_id"] for f in findings], ["MATH001", "MATH001"])
        self.assertEqual(self.scan("得到 $x$，然后输出。\n")["findings"], [])

    def test_excess_spaces_and_fullwidth(self):
        text = "中文  English， 后续 $x$ 。\n词\u3000句。\n"
        self.assertEqual({f["rule_id"] for f in self.confirmed(text)}, {"TXT003", "TXT004", "TXT006"})

    def test_fullwidth_letters_are_uncertain(self):
        findings = self.scan("示例 ＡＢＣ。\n")["findings"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["type"], "Warning")

    def test_code_and_math_are_not_chinese_prose(self):
        text = r"""正文 `中文English,变量2`，另见 $a_{i}+2=\text{中文English,变量2}$。

```cpp
// 中文English,变量2
if (x==2) { a[i] = x%2; }
```

~~~text
$未闭合 #标题
~~~

    中文English,变量2

$$
\begin{aligned}
a&=b+c\\
d&=\text{中文English,变量2}
\end{aligned}
$$
"""
        self.assertEqual(self.scan(text)["findings"], [])

    def test_variable_length_code_spans_and_fences(self):
        text = "``含 ` 字符中文English``。\n\n````cpp\n```\n中文English\n````\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_fence_must_use_same_character_and_enough_length(self):
        for text in ("````cpp\n```\n", "```cpp\n~~~\n", "```cpp\n    ```\n"):
            with self.subTest(text=text):
                findings = self.confirmed(text)
                self.assertEqual([f["rule_id"] for f in findings], ["MD002"])
                self.assertEqual(findings[0]["line"], 1)

    def test_blockquoted_fence(self):
        self.assertEqual(self.scan("> ```text\n> 中文English\n> ```\n")["findings"], [])

    def test_nested_list_fence_is_parsed_without_false_positive(self):
        result = self.scan("- ```text\n  中文English,数据2\n  ```\n\n正文正确。\n")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["format_assessment"]["verdict"], "pass")

    def test_headings_and_list_markers(self):
        text = "##### 太深\n\n1) 第一项\n\n#可能是标签\n-可能是减号\n"
        findings = self.scan(text)["findings"]
        self.assertEqual([(f["rule_id"], f["type"]) for f in findings], [
            ("MD001", "Confirmed"), ("MD003", "Confirmed"),
            ("MD001", "Warning"), ("MD003", "Warning"),
        ])

    def test_normal_lists_tables_and_hard_breaks(self):
        text = "# 思路\n\n- 第一项。  \n- 第二项。\n\n1. 第一步。\n2. 第二步。\n\n| 中文    | English |\n| --- | --- |\n| 结论   | 成立。   |\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_links_images_and_autolinks(self):
        text = ('参考 [说明](https://example.org/中文English?q=(变量2) "中文English")。\n'
                '![中文English,变量2](https://example.org/x.png)\n'
                '<https://example.org/中文English>\n'
                '<a href="https://example.org/中文English">说明</a>\n'
                '[ref]: https://example.org/中文English "中文English"\n')
        result = self.scan(text)
        self.assertTrue(all(f["rule_id"] == "MD010" and f["type"] == "Warning" for f in result["findings"]))
        self.assertTrue(result["skipped"])

    def test_visible_link_label_is_checked(self):
        findings = self.confirmed("参考 [中文English](https://example.org)。\n")
        self.assertEqual([f["rule_id"] for f in findings], ["TXT001"])

    def test_bracketed_text_and_math_intervals_are_not_links(self):
        self.assertEqual(self.scan("区间 $[l,r]$，方括号 [说明]。\n")["findings"], [])

    def test_comments_and_raw_html_do_not_leak(self):
        text = "<!--\n##### 中文English ` $\n```\n-->\n<pre>\n中文English ` $\n</pre>\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_literal_html_comment_inside_code(self):
        text = "```html\n<!--\n```\n\n正文 `<!--`，不作为注释。\n\n正文正确。\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_frontmatter_is_not_prose(self):
        result = self.scan('---\ntitle: 中文English\n---\n\n正文正确。\n')
        self.assertEqual(result["findings"], [])
        self.assertTrue(result["skipped"])

    def test_unclosed_display_math(self):
        for text in ("$$\nx+y\n", "\\[\nx+y\n", "由 \\(x+y\n"):
            with self.subTest(text=text):
                self.assertIn("MATH002", [f["rule_id"] for f in self.confirmed(text)])

    def test_dollars_and_unmatched_backticks_are_warnings(self):
        for text in ("费用为 $5。\n", "费用 $5，运费 $10。\n", "符号 ` 的用途。\n", "公式 $ x $。\n"):
            with self.subTest(text=text):
                findings = self.scan(text)["findings"]
                self.assertTrue(findings)
                self.assertTrue(all(f["type"] == "Warning" for f in findings))

    def test_escaped_dollar_and_braces(self):
        self.assertEqual(self.scan(r"字面 \$，集合 $\{x\}$。" + "\n")["findings"], [])

    def test_tex_environment_mismatch_and_braces(self):
        findings = self.confirmed(r"公式 $\begin{bmatrix}x\end{cases}$，另有 $a_{i$。" + "\n")
        self.assertEqual({f["rule_id"] for f in findings}, {"TEX001", "TEX002"})

    def test_tex_comments_and_text_are_preserved(self):
        text = r"""$$
\begin{aligned}
x &= \text{中文English,2}\% + y % } \end{cases}
\end{aligned}
$$
"""
        self.assertEqual(self.scan(text)["findings"], [])

    def test_tex_verbatim_delimiters_and_valid_environments(self):
        text = r"公式 $\verb|{|+\left\{x\right.$，矩阵 $\begin{bmatrix}a&b\\c&d\end{bmatrix}$。" + "\n"
        self.assertEqual(self.scan(text)["findings"], [])

    def test_macro_commands_and_unknown_commands_are_not_confirmed(self):
        text = r"""$$
\newcommand{\frca}[2]{\frac{#1}{#2}}
\frca{1}{2}+\custom{x}
\begin{custom}x\end{custom}
$$
"""
        findings = self.scan(text)["findings"]
        self.assertTrue(findings)
        self.assertTrue(all(f["type"] == "Warning" for f in findings))
        result = self.scan(r"公式 $\custom{x}$。" + "\n")
        self.assertTrue(all(f["type"] == "Warning" for f in result["findings"]))
        self.assertEqual(result["format_assessment"]["verdict"], "non_compliant")

    def test_line_endings(self):
        findings = self.confirmed("# 思路\r\n\r\n中文English。\r\n")
        self.assertEqual((findings[0]["line"], findings[0]["column"]), (3, 2))

    def test_pedagogy_materials_have_clean_format(self):
        for path in sorted((Path(__file__).parent / "materials").glob("*.md")):
            with self.subTest(file=path.name):
                self.assertEqual(self.scan(path.read_text(encoding="utf-8"))["findings"], [])


class CommandTests(unittest.TestCase):
    def call_main(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = LINT.main(args)
        return code, json.loads(output.getvalue())

    def test_environment_check_cli(self):
        run = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                             capture_output=True, text=True, check=True)
        result = json.loads(run.stdout)
        self.assertTrue(result["supported"])
        self.assertEqual(result["files_checked"], [])

    def test_python38_syntax(self):
        ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_old_python_environment_is_unavailable(self):
        with mock.patch.object(LINT.sys, "version_info", (3, 7, 9)):
            code, result = self.call_main(["--check"])
        self.assertEqual(code, 2)
        self.assertFalse(result["supported"])
        self.assertEqual(result["findings"], [])
        self.assertTrue(result["errors"])

    def test_missing_path_and_pdf_are_errors_not_violations(self):
        with tempfile.TemporaryDirectory() as temp:
            for path in (Path(temp) / "missing.md", Path(temp) / "material.pdf"):
                with self.subTest(path=path):
                    code, result = self.call_main([str(path)])
                    self.assertEqual(code, 2)
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(result["findings"], [])
                    self.assertTrue(result["errors"])

    def test_partial_results_and_no_source_modification(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "带 空格.md"
            source.write_text("中文English。\n", encoding="utf-8")
            before = source.read_bytes()
            code, result = self.call_main([str(source), str(Path(temp) / "missing.md")])
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["files_checked"], [str(source.resolve())])
            self.assertTrue(result["findings"])
            self.assertNotIn("score", result)
            self.assertEqual(source.read_bytes(), before)

    def test_bad_encoding_is_input_error(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "bad.md"
            source.write_bytes(b"\xff\xfe\x00")
            code, result = self.call_main([str(source)])
        self.assertEqual(code, 2)
        self.assertEqual(result["findings"], [])

    def test_no_input(self):
        code, result = self.call_main([])
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
