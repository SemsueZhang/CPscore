"""Evidence-bound LLM review, strict fallback and script-owned scoring."""

import contextlib
import copy
import importlib.util
import io
import json
import random
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/cp-editorial-review/scripts/format_lint.py"
SPEC = importlib.util.spec_from_file_location("format_decisions", SCRIPT)
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


class FormatDecisionTests(unittest.TestCase):
    def setUp(self):
        self.source = "这里刻意展示全角字母 Ａ。\n"
        self.scan = LINT.lint_text(self.source, "题解.md")
        self.candidate = self.scan["review_candidates"][0]
        self.record = {"file": self.scan["file"], "sha256": self.scan["sha256"], "decisions": []}

    def anchor(self, start=0, end=None, source=None):
        source = self.source if source is None else source
        end = len(source) if end is None else end
        return {"offset": start, "end_offset": end, "excerpt": source[start:end]}

    def decision(self, verdict="dismissed"):
        return {"candidate_id": self.candidate["candidate_id"], "verdict": verdict,
                "reason": "上下文明确为刻意展示全角写法。", "evidence": [self.anchor()]}

    def merge(self, record=None, source=None, scan=None):
        return LINT.apply_format_decisions(scan or self.scan, self.source if source is None else source,
                                          self.record if record is None else record)

    def test_warning_can_be_dismissed_with_bound_evidence(self):
        self.record["decisions"] = [self.decision()]
        result = self.merge()
        self.assertEqual(result["format_assessment"]["verdict"], "pass")
        self.assertEqual(self.scan["findings"][0]["type"], "Warning")
        self.assertEqual(len(result["adjudications"]), 1)

    def test_warning_can_be_confirmed_and_script_computes_major(self):
        self.source = "普通变量为 Ａ。\n"
        self.scan = LINT.lint_text(self.source, "题解.md")
        self.candidate = self.scan["review_candidates"][0]
        self.record = {"file": self.scan["file"], "sha256": self.scan["sha256"], "decisions": []}
        decision = self.decision("confirmed")
        decision["reason"] = "此处字母应作普通变量，当前未使用半角。"
        self.record["decisions"] = [decision]
        result = self.merge()
        group = result["format_assessment"]["groups"][0]
        self.assertEqual((group["confirmed_count"], group["severity"], group["deduction"]), (1, "Major", 2))
        self.assertEqual(result["effective_findings"][0]["verified_by"], "llm")

    def test_omitted_and_unverified_decisions_do_not_pass(self):
        for decisions in ([], [self.decision("unverified")]):
            with self.subTest(decisions=decisions):
                self.record["decisions"] = decisions
                assessment = self.merge()["format_assessment"]
                self.assertEqual((assessment["verdict"], assessment["complete"]), ("non_compliant", False))
                self.assertEqual(assessment["groups"][0]["confirmed_count"], 0)

    def test_stale_hash_and_changed_source_rejected(self):
        self.record["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.merge()
        self.record["sha256"] = self.scan["sha256"]
        with self.assertRaises(ValueError):
            self.merge(source=self.source + "变化。")

    def test_wrong_file_and_unknown_candidate_rejected(self):
        self.record["file"] = "另一篇.md"
        with self.assertRaises(ValueError):
            self.merge()
        self.record["file"] = self.scan["file"]
        self.record["decisions"] = [dict(self.decision(), candidate_id="fake")]
        with self.assertRaises(ValueError):
            self.merge()

    def test_static_confirmed_cannot_be_revoked(self):
        source = "中文English。\n"
        scan = LINT.lint_text(source, "题解.md")
        self.assertEqual(scan["review_candidates"], [])
        record = {"file": scan["file"], "sha256": scan["sha256"], "decisions": [self.decision()]}
        with self.assertRaises(ValueError):
            self.merge(record, source, scan)

    def test_duplicate_decision_and_severity_injection_rejected(self):
        self.record["decisions"] = [self.decision(), self.decision()]
        with self.assertRaises(ValueError):
            self.merge()
        for key in ("severity", "deduction", "confirmed_count", "type"):
            self.record["decisions"] = [dict(self.decision(), **{key: "pass"})]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.merge()

    def test_bad_decision_types_and_missing_evidence_are_value_errors(self):
        for field, values in {"candidate_id": [None, []], "verdict": [[], {}, None, "reviewed"],
                              "reason": [None, "", "  ", "\ud800"], "evidence": [None, [], [{}], [None]]}.items():
            for value in values:
                self.record["decisions"] = [dict(self.decision(), **{field: value})]
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.merge()

    def test_evidence_must_match_and_overlap_candidate(self):
        for anchor in (self.anchor(0, 1), dict(self.anchor(), excerpt="伪造摘录"),
                       dict(self.anchor(), offset=True), dict(self.anchor(), end_offset=999)):
            self.record["decisions"] = [dict(self.decision(), evidence=[anchor])]
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                self.merge()

    def test_scope_review_is_separate_from_new_errors(self):
        source = "![说明](https://cdn.luogu.com.cn/x.png)\n"
        scan = LINT.lint_text(source, "题解.md")
        record = {"file": scan["file"], "sha256": scan["sha256"], "decisions": []}
        for c in scan["review_candidates"]:
            self.assertEqual(c["kind"], "scope")
            record["decisions"].append({"candidate_id": c["candidate_id"], "verdict": "reviewed",
                "reason": "测试桩：模拟外部图片已核验，只验证状态合并。", "evidence": [self.anchor(source=source)]})
        self.assertTrue(record["decisions"])
        result = self.merge(record, source, scan)
        self.assertEqual(result["format_assessment"]["verdict"], "pass")
        self.assertTrue(result["format_assessment"]["complete"])

    def additional(self, source, start, end, position, category="width"):
        return dict(self.anchor(start, end, source), position=position, category=category,
                    standard="普通变量使用半角。", reason="已检查该位置的用途。",
                    evidence=[self.anchor(start, end, source)])

    def test_additional_locations_are_deduplicated_and_grade_at_three(self):
        source = "Ａ。\n\nＢ。\n\nＣ。\n"
        scan = LINT.lint_text(source, "题解.md")
        additions = [self.additional(source, pos, pos + 1, pos) for pos in (0, 4, 8)]
        record = {"file": scan["file"], "sha256": scan["sha256"], "additional_findings": additions * 2}
        result = self.merge(record, source, scan)
        group = result["format_assessment"]["groups"][0]
        self.assertEqual((group["confirmed_count"], group["severity"], group["deduction"]), (3, "Fatal", 10))

    def test_static_and_llm_same_physical_gap_count_once(self):
        source = "中文English。\n"
        scan = LINT.lint_text(source, "题解.md")
        fact = scan["findings"][0]
        addition = self.additional(source, fact["offset"], fact["end_offset"], int(fact["occurrence_key"]), "missing_space")
        record = {"file": scan["file"], "sha256": scan["sha256"], "additional_findings": [addition]}
        result = self.merge(record, source, scan)
        self.assertEqual(result["format_assessment"]["groups"][0]["confirmed_count"], 1)

    def test_new_finding_does_not_require_a_candidate_id(self):
        source = "这样即可 $KO$ 此题。\n"
        scan = LINT.lint_text(source, "题解.md")
        start, end = source.index("$"), source.rindex("$") + 1
        addition = self.additional(source, start, end, start + 1, "extra_math")
        addition.update(standard="普通词语不用数学环境。", reason="KO 在此是普通叙述用语，没有数学含义。")
        record = {"file": scan["file"], "sha256": scan["sha256"], "additional_findings": [addition]}
        result = self.merge(record, source, scan)
        self.assertTrue(any(f["rule_id"] == "LLM001" for f in result["effective_findings"]))
        group = next(g for g in result["format_assessment"]["groups"] if g["category"] == "extra_math")
        self.assertEqual((group["confirmed_count"], group["severity"]), (1, "Major"))

    def test_warning_can_be_reclassified_instead_of_silently_dropped(self):
        source = "程序调用写作 $print(x)$。\n"
        scan = LINT.lint_text(source, "题解.md")
        candidate = next(c for c in scan["review_candidates"] if c["rule_id"] == "TEX004")
        start, end = source.index("$"), source.rindex("$") + 1
        addition = self.additional(source, start, end, start + 1, "extra_math")
        addition.update(standard="程序片段使用代码样式。", reason="print(x) 是文中明示的程序调用，误入了数学环境。")
        record = {"file": scan["file"], "sha256": scan["sha256"], "decisions": [{
            "candidate_id": candidate["candidate_id"], "verdict": "dismissed",
            "reason": "它是程序调用，不是需要改正体的数学函数；根因改归多余数学环境。",
            "evidence": [self.anchor(source=source)]}], "additional_findings": [addition]}
        result = self.merge(record, source, scan)
        groups = result["format_assessment"]["groups"]
        self.assertEqual([g["category"] for g in groups], ["extra_math"])
        self.assertEqual(result["format_assessment"]["format_deduction"], 2)
        self.assertEqual(next(f for f in scan["findings"] if f["rule_id"] == "TEX004")["type"], "Warning")

    def test_crlf_coordinates_use_anchor_start_not_counting_position(self):
        source = "说明。\r\n后文。\r\n"
        scan = LINT.lint_text(source, "题解.md")
        for start, end, position, expected in ((4, 5, 5, (1, 5)), (5, 8, 7, (2, 1))):
            record = {"file": scan["file"], "sha256": scan["sha256"],
                      "additional_findings": [self.additional(source, start, end, position)]}
            finding = self.merge(record, source, scan)["effective_findings"][-1]
            self.assertEqual((finding["line"], finding["column"]), expected)

    def test_bad_addition_fields_are_rejected(self):
        addition = self.additional(self.source, 0, 1, 0)
        for key, values in {"category": [[], None, "unknown", "coverage"], "position": [True, -1, 999, []],
                            "offset": [None, True], "standard": [""], "reason": [""], "severity": ["Fatal"]}.items():
            for value in values:
                self.record["additional_findings"] = [dict(addition, **{key: value})]
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.merge()

    def test_generated_candidates_preserve_raw_results_when_unresolved(self):
        generator = random.Random(20261115)
        alphabet = "中文abc123_$`[](){}*~!<>\\%:.,|# &;\n\r\tＡ"
        for case in range(250):
            source = "".join(generator.choice(alphabet) for _ in range(generator.randrange(200)))
            scan = LINT.lint_text(source, "generated.md")
            before = copy.deepcopy(scan)
            record = {"file": scan["file"], "sha256": scan["sha256"], "decisions": []}
            ids = [c["candidate_id"] for c in scan["review_candidates"]]
            self.assertEqual(len(ids), len(set(ids)), case)
            for candidate in scan["review_candidates"]:
                self.assertTrue(0 <= candidate["offset"] < candidate["end_offset"] <= len(source), case)
                record["decisions"].append({"candidate_id": candidate["candidate_id"], "verdict": "unverified",
                    "reason": "生成输入只检查来源和状态不变量，不作格式语义判断。",
                    "evidence": [self.anchor(source=source)]})
            result = self.merge(record, source, scan)
            self.assertEqual(result["format_assessment"], scan["format_assessment"], case)
            self.assertEqual(scan, before, case)


class DecisionCommandTests(unittest.TestCase):
    def call(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = LINT.main(args)
        return code, json.loads(output.getvalue())

    def test_cli_retains_raw_and_effective_results_and_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source, decisions = Path(temp) / "稿件.md", Path(temp) / "review.json"
            source.write_text("刻意展示 Ａ。\n", encoding="utf-8")
            before = source.read_bytes()
            _, raw = self.call([str(source)])
            candidate = raw["review_candidates"][0]
            record = {"file": candidate["file"], "sha256": candidate["sha256"], "decisions": [{
                "candidate_id": candidate["candidate_id"], "verdict": "dismissed", "reason": "这是刻意展示。",
                "evidence": [{"offset": 0, "end_offset": len(source.read_text()), "excerpt": source.read_text()}]}]}
            decisions.write_text(json.dumps({"files": [record]}), encoding="utf-8")
            code, merged = self.call(["--decisions", str(decisions), str(source)])
            self.assertEqual(code, 0)
            self.assertTrue(merged["decisions_applied"])
            self.assertEqual(merged["findings"], raw["findings"])
            self.assertEqual(merged["effective_findings"], [])
            self.assertEqual(merged["format_assessment"]["verdict"], "pass")
            self.assertEqual(source.read_bytes(), before)
            # Invalid later records invalidate the whole batch, retaining raw facts.
            invalid = copy.deepcopy(record)
            invalid["file"] = str(Path(temp) / "other.md")
            decisions.write_text(json.dumps({"files": [record, invalid]}), encoding="utf-8")
            code, failed = self.call(["--decisions", str(decisions), str(source)])
            self.assertEqual(code, 2)
            self.assertFalse(failed["decisions_applied"])
            self.assertEqual(failed["effective_findings"], raw["findings"])
            self.assertEqual(failed["format_assessment"]["verdict"], "non_compliant")

    def test_malformed_records_and_duplicate_json_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source, decisions = Path(temp) / "ok.md", Path(temp) / "review.json"
            source.write_text("正文正确。\n", encoding="utf-8")
            for payload in ('{', '[]', '{"files": {}, "extra": 1}', '{"files": [], "files": []}'):
                decisions.write_text(payload, encoding="utf-8")
                with self.subTest(payload=payload):
                    code, result = self.call(["--decisions", str(decisions), str(source)])
                    self.assertEqual(code, 2)
                    self.assertFalse(result["decisions_applied"])
                    self.assertFalse(result["format_assessment"]["complete"])

    def test_files_are_scored_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            files = [Path(temp) / (str(i) + ".md") for i in range(2)]
            for file in files:
                file.write_text("中文English。\n", encoding="utf-8")
            _, result = self.call([str(file) for file in files])
            groups = result["format_assessment"]["groups"]
            self.assertEqual([g["confirmed_count"] for g in groups], [1, 1])
            self.assertEqual([g["severity"] for g in groups], ["Major", "Major"])


if __name__ == "__main__":
    unittest.main()
