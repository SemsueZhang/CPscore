from copy import deepcopy
import unittest

from cpscore.reporting import render_markdown
from cpscore.schema import ReportValidationError, validate_scored_report
from cpscore.scoring import make_report, score_report


def finding(identifier="f1", root="root1", severity="minor", status="confirmed", *, snapshot="snapshot-1", version="v1"):
    return {
        "id": identifier, "root_cause_id": root, "severity": severity, "status": status,
        "title": "Boundary defect", "description": "The upper boundary is inconsistent.",
        "evidence": [{"snapshot_id": snapshot, "artifact_version": version, "location": "solution.cpp:12", "observation": "n=1 returns 0"}],
        "reproduction": {"steps": ["Run with n=1"], "expected": "1", "actual": "0"},
        "repair": {"suggestion": "Correct the boundary", "auto_fixable": True, "status": "not_attempted", "patch": None, "verification": []},
    }


def reviewed(scope=("solution",)):
    report = make_report(scope)
    for name in scope:
        report["objects"][name]["review_status"] = "reviewed"
    return report


class ScoringTests(unittest.TestCase):
    def test_required_score_boundaries(self):
        for minor_count, expected in ((0, 10), (1, 9), (4, 6), (5, 5), (10, 0), (12, 0)):
            with self.subTest(minor_count=minor_count):
                report = reviewed()
                report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}") for i in range(minor_count)]
                result = score_report(report)
                self.assertEqual(result["overall"]["score"], expected)
                self.assertEqual(result["overall"]["qualified"], expected >= 6)
                self.assertEqual(validate_scored_report(result), [])

    def test_fatal_and_floor(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding(severity="fatal"), finding("f2", "r2")]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["total_penalty"], 11)
        self.assertEqual(result["overall"]["status"], "fail")

    def test_explicit_root_only_and_cross_object_deduplication(self):
        report = reviewed(("statement", "solution"))
        report["objects"]["statement"]["findings"] = [finding("s1", "shared"), finding("s2", "shared")]
        report["objects"]["solution"]["findings"] = [finding("c1", "shared"), finding("c2", "different")]
        result = score_report(report)
        self.assertEqual(result["objects"]["statement"]["score"], 9)
        self.assertEqual(result["objects"]["solution"]["score"], 8)
        self.assertEqual(result["overall"]["score"], 8)
        self.assertEqual(len(result["overall"]["deductions"]), 2)
        shared = next(root for root in result["root_causes"] if root["root_cause_id"] == "shared")
        self.assertEqual(shared["finding_ids"], ["c1", "s1", "s2"])
        self.assertEqual(len(shared["evidence_refs"]), 3)

    def test_suspected_fatal_is_pending_without_deduction(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding(severity="fatal", status="suspected")]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["status"], "pending")
        self.assertIsNone(result["overall"]["qualified"])
        self.assertEqual(result["root_causes"][0]["points"], 0)

    def test_pending_fatal_takes_priority_over_low_numeric_scores(self):
        for count, expected in ((5, 5), (10, 0)):
            report = reviewed()
            report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}") for i in range(count)] + [finding("pending", "suspected-root", "fatal", "suspected")]
            result = score_report(report)
            self.assertEqual(result["objects"]["solution"]["score"], expected)
            self.assertEqual(result["objects"]["solution"]["status"], "pending")
            self.assertEqual(result["overall"]["status"], "pending")
            self.assertIsNone(result["overall"]["qualified"])

    def test_incomplete_scope_takes_priority_over_low_numeric_score(self):
        report = make_report()
        report["objects"]["solution"]["review_status"] = "reviewed"
        report["objects"]["solution"]["findings"] = [finding(severity="fatal")]
        result = score_report(report)
        self.assertEqual(result["objects"]["solution"]["status"], "fail")
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["status"], "pending")
        self.assertIsNone(result["overall"]["qualified"])

    def test_resolved_requires_fresh_evidence_and_does_not_deduct(self):
        report = reviewed()
        report["snapshot"] = {"id": "snapshot-2", "revision": 2, "supersedes": "snapshot-1"}
        report["objects"]["solution"]["artifact_version"] = "v2"
        resolved = finding(severity="fatal", status="resolved", snapshot="snapshot-2", version="v2")
        resolved["repair"].update(status="applied", verification=["Re-run n=1 and observe 1"])
        report["objects"]["solution"]["findings"] = [resolved]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["root_causes"][0]["status"], "resolved")
        report["objects"]["solution"]["findings"][0]["evidence"][0]["snapshot_id"] = "snapshot-1"
        with self.assertRaises(ReportValidationError):
            score_report(report)

    def test_conflicting_root_status_or_severity_rejected(self):
        for severity, status in (("fatal", "confirmed"), ("minor", "resolved"), ("minor", "suspected")):
            report = reviewed(("statement", "solution"))
            report["objects"]["statement"]["findings"] = [finding("s", "shared")]
            report["objects"]["solution"]["findings"] = [finding("c", "shared", severity, status)]
            with self.subTest(severity=severity, status=status), self.assertRaises(ReportValidationError):
                score_report(report)

    def test_scope_and_incomplete_review_are_distinct(self):
        scoped = score_report(reviewed())
        self.assertEqual(scoped["overall"]["status"], "pass")
        self.assertEqual(scoped["objects"]["statement"]["status"], "not_reviewed")
        report = make_report()
        report["objects"]["solution"]["review_status"] = "reviewed"
        partial = score_report(report)
        self.assertEqual(partial["overall"]["score"], 10)
        self.assertEqual(partial["overall"]["status"], "pending")
        self.assertEqual(partial["overall"]["completion"], "pending")
        empty = score_report(make_report())
        self.assertIsNone(empty["overall"]["score"])
        self.assertEqual(empty["overall"]["status"], "pending")

    def test_deterministic_no_mutation_and_markdown_trace(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding()]
        before = deepcopy(report)
        first = score_report(report)
        self.assertEqual(first, score_report(report))
        self.assertEqual(report, before)
        markdown = render_markdown(first)
        self.assertIn("max(0, 10 − 1) = 9", markdown)
        self.assertIn("solution.cpp:12", markdown)
        self.assertIn("Independent root causes", markdown)
        self.assertIn("No validation projects recorded", markdown)

    def test_tampered_output_rejected(self):
        output = score_report(reviewed())
        for value in (-1, 11, 9, True, float("nan")):
            changed = deepcopy(output)
            changed["overall"]["score"] = value
            self.assertTrue(validate_scored_report(changed))


if __name__ == "__main__":
    unittest.main()
