"""Additional source probes found during the multi-round format audit."""

import contextlib
import hashlib
import importlib.util
import io
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("format_audit", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class AuditRoundOne(unittest.TestCase):
    def scan(self, source):
        return LINT.lint_text(source)

    def test_lone_cr_has_real_line_and_column(self):
        result = self.scan("# 思路\r\r中文English。\r")
        f = next(f for f in result["findings"] if f["rule_id"] == "TXT001")
        self.assertEqual((f["line"], f["column"], f["excerpt"]), (3, 2, "文E"))

    def test_unicode_line_separator_is_not_a_markdown_line_or_softbreak(self):
        result = self.scan("说明\u2028中文English。\n")
        self.assertFalse(any(f["rule_id"] == "TXT006" for f in result["findings"]))
        f = next(f for f in result["findings"] if f["rule_id"] == "TXT001")
        self.assertEqual((f["line"], f["column"]), (1, 5))

    def test_single_crlf_does_not_end_a_paragraph(self):
        self.assertEqual(LINT.paragraph_end("one\r\ntwo", 0), len("one\r\ntwo"))
        self.assertEqual(LINT.paragraph_end("one\r\n\r\ntwo", 0), 3)

    def test_cr_math_line_bounds_do_not_trigger_unclosed_math(self):
        result = self.scan("# 思路\r\r公式 $x$。\r\r$$\rx+y\r$$\r")
        self.assertEqual(result["findings"], [])

    def test_setext_heading_is_a_heading_without_sentence_period(self):
        for marker in ("====", "----", "-"):
            with self.subTest(marker=marker):
                self.assertEqual(self.scan("算法可以处理全部状态\n" + marker + "\n")["findings"], [])

    def test_multiline_setext_and_literal_hash_title(self):
        for source in ("算法可以处理\n所有的状态\n===\n", "#标签\n===\n", "$x$\n===\n"):
            with self.subTest(source=source):
                self.assertEqual(self.scan(source)["findings"], [])

    def test_blank_line_before_rule_does_not_create_a_setext_heading(self):
        result = self.scan("算法可以处理全部状态\n\n---\n")
        self.assertTrue(any(f["rule_id"] == "TXT005" and f["type"] == "Confirmed" for f in result["findings"]))

    def test_intraword_underscores_are_not_removed_as_emphasis(self):
        result = self.scan("中文_English_。\n")
        self.assertFalse(any(f["category"] == "missing_space" for f in result["findings"]))
        self.assertTrue(any(f["rule_id"] == "MD014" and f["type"] == "Warning" for f in result["findings"]))

    def test_math_after_intraword_asterisks_is_not_a_bold_boundary(self):
        result = self.scan("中文**$x$**。\n")
        self.assertFalse(any(f["category"] == "missing_space" for f in result["findings"]))
        self.assertTrue(any(f["rule_id"] == "MD014" for f in result["findings"]))
        self.assertEqual(self.scan("中文 **$x$**。\n")["findings"], [])

    def test_escaped_literal_emphasis_inside_code_is_opaque(self):
        self.assertEqual(self.scan("代码 `中文_English_`。\n")["findings"], [])

    def test_verbatim_percent_does_not_hide_unknown_command_after_it(self):
        result = self.scan(r"公式 $\verb|%|+\frca{1}{2}$。" + "\n")
        self.assertTrue(any(f["rule_id"] == "TEX003" for f in result["findings"]))
        self.assertEqual(result["format_assessment"]["verdict"], "non_compliant")

    def test_verbatim_percent_and_braces_are_opaque(self):
        self.assertEqual(self.scan(r"公式 $\verb|%{}|+x$。" + "\n")["findings"], [])

    def test_real_comment_after_verbatim_stops_at_cr(self):
        result = self.scan("$$\r" + r"\verb|%|+x % \badmacro" + "\r" + r"\custom{x}" + "\r$$\r")
        names = [f["excerpt"] for f in result["findings"] if f["rule_id"] in ("TEX003", "TEX013")]
        self.assertEqual(names, [r"\custom"])

    def test_unclosed_verbatim_is_not_assumed_supported(self):
        result = self.scan(r"公式 $\verb|abc$。" + "\n")
        self.assertTrue(any(f["rule_id"] == "TEX013" and f["type"] == "Warning" for f in result["findings"]))

    def test_unverified_commands_cannot_pass_from_a_typo_in_the_catalog(self):
        for command in ("lf", "loor", "dx", "dy", "dt", "and", "or", "xor"):
            with self.subTest(command=command):
                result = self.scan("公式 $\\" + command + " x$。\n")
                self.assertTrue(any(f["rule_id"] == "TEX013" for f in result["findings"]))

    def test_container_open_close_and_unknown_kind_are_not_silent(self):
        for source in (":::details[说明]\n正文正确。\n", ":::info[说明]\n正文正确。\n", ":::\n", "</details>\n"):
            with self.subTest(source=source):
                self.assertEqual(self.scan(source)["format_assessment"]["verdict"], "non_compliant")

    def test_matched_supported_containers_pass_without_an_artificial_gap(self):
        for source in (":::details[代码]\n\n正文正确。\n\n:::\n", "<details>\n<summary>参考代码</summary>\n\n正文正确。\n</details>\n"):
            with self.subTest(source=source):
                self.assertEqual(self.scan(source)["format_assessment"]["verdict"], "pass")

    def test_summary_title_text_is_checked(self):
        result = self.scan("<details>\n<summary>中文English</summary>\n</details>\n")
        self.assertTrue(any(f["rule_id"] == "TXT001" and f["line"] == 2 for f in result["findings"]))

    def test_escaped_pipe_is_not_table_alignment_padding(self):
        result = self.scan("| 标题 | 内容 |\n| --- | --- |\n| 数据 | 中文\\| ，随后 |\n")
        fs = [f for f in result["findings"] if f["rule_id"] == "TXT003"]
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["line"], 3)

    def test_large_hash_prefix_is_unverified_instead_of_passing(self):
        result = self.scan("####### 思路\n")
        self.assertTrue(any(f["rule_id"] == "MD001" and f["type"] == "Warning" for f in result["findings"]))

    def test_reserved_marker_source_is_unverified_not_merged_into_false_gaps(self):
        for char in ("\0", LINT.MATH_TOKEN, LINT.CODE_TOKEN, LINT.OTHER_TOKEN):
            with self.subTest(char=repr(char)):
                result = self.scan("中文" + char + "English。\n")
                self.assertTrue(any(s.get("unverified") for s in result["skipped"]))
                self.assertFalse(any(f["category"] == "missing_space" for f in result["findings"]))

    def test_generated_malformed_inputs_preserve_source_positions(self):
        generator = random.Random(20261114)
        alphabet = "中文abc123_$`[](){}*~!<>\\%:.,|# \n\r\t\u2028\0"
        for case in range(1200):
            source = "".join(generator.choice(alphabet) for _ in range(generator.randrange(220)))
            expected = {}
            row, column = 1, 1
            for pos, char in enumerate(source):
                expected[pos] = (row, column)
                if char == "\n" or (char == "\r" and source[pos + 1:pos + 2] != "\n"):
                    row, column = row + 1, 1
                else:
                    column += 1
            expected[len(source)] = (row, column)
            with self.subTest(case=case):
                result = self.scan(source)
                for finding in result["findings"]:
                    start, end = finding["offset"], finding["end_offset"]
                    self.assertTrue(0 <= start <= end <= len(source))
                    self.assertEqual((finding["line"], finding["column"]), expected[start])
                    if not finding["excerpt_truncated"]:
                        self.assertEqual(finding["excerpt"], source[start:end])


class InputAudit(unittest.TestCase):
    def call(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = LINT.main(args)
        return code, json.loads(output.getvalue())

    def test_symlink_loop_preserves_results_for_other_articles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            loop = root / "loop.md"
            loop.symlink_to("loop.md")
            good = root / "good.md"
            good.write_text("算法为 BFS。\n", encoding="utf-8")
            code, result = self.call([str(loop), str(good)])
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["files_checked"]), 1)
        self.assertTrue(result["errors"])

    def test_cli_keeps_original_line_endings_in_offsets_and_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.md"
            raw = "# 思路\r\n\r\n中文English。\r\n".encode("utf-8")
            source.write_bytes(raw)
            code, result = self.call([str(source)])
            self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(code, 0)
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(raw).hexdigest())
        f = next(f for f in result["findings"] if f["rule_id"] == "TXT001")
        self.assertEqual((f["line"], f["column"]), (3, 2))
        self.assertEqual(raw.decode()[f["offset"]:f["end_offset"]], "文E")

    def test_long_plain_text_and_many_math_spans_finish_without_quadratic_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "long.md"
            source.write_text("h" * 200000 + "\n\n" + "$x$ " * 6000 + ".\n", encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), str(source)], capture_output=True,
                                 text=True, check=True, timeout=10)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["findings"], [])


if __name__ == "__main__":
    unittest.main()
