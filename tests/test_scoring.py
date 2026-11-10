from copy import deepcopy
import unittest

from cpscore.reporting import render_markdown
from cpscore.schema import ReportValidationError, validate_scored_report
from cpscore.scoring import make_report, score_report


COVERAGE_ITEMS = {
    "statement": ("definition", "io", "constraints", "boundaries", "samples"),
    "solution": ("algorithm", "correctness", "complexity", "implementation"),
    "editorial": ("claims", "reasoning", "proof", "complexity"),
}


def evidence(*, snapshot="snapshot-1", version="v1", location="solution.cpp:12", observation="n=1 returns 0"):
    return {"snapshot_id": snapshot, "artifact_version": version, "location": location, "observation": observation}


def finding(identifier="f1", root="root1", severity="minor", status="confirmed", *, snapshot="snapshot-1", version="v1", rule_id="other"):
    result = {
        "id": identifier, "root_cause_id": root, "rule_id": rule_id, "severity": severity, "status": status,
        "title": "Boundary defect", "description": "The upper boundary is inconsistent.",
        "evidence": [evidence(snapshot=snapshot, version=version)],
        "reproduction": {"steps": ["Run with n=1"], "expected": "1", "actual": "0"},
        "repair": {"suggestion": "Correct the boundary", "auto_fixable": True, "status": "not_attempted", "patch": None, "verification": []},
    }
    if severity in ("major", "minor"):
        result["impact"] = "Synthetic scoring fixture: the inconsistent boundary explanation obstructs verification; severity is supplied by the test, not a model verdict."
    if status == "suspected":
        result["evidence_gap"] = "The invariant needed to settle this defect has not been supplied."
    return result


def check_coverage(report, name, *, snapshot=None, version=None):
    snapshot = snapshot or report["snapshot"]["id"]
    version = version or report["objects"][name]["artifact_version"]
    for item in COVERAGE_ITEMS[name]:
        report["objects"][name]["coverage"][item] = {
            "status": "checked",
            "evidence": [evidence(snapshot=snapshot, version=version, location=f"{name}.md: {item}",
                                  observation=f"Manually verified the {item} obligations in this test artifact.")],
            "reason": None,
        }
    return report


def reviewed(scope=("solution",)):
    """A synthetic complete review with explicit current-version evidence."""
    report = make_report(scope)
    for name in scope:
        check_coverage(report, name)
    return report


class ScoringTests(unittest.TestCase):
    def test_required_score_boundaries(self):
        for minor_count, expected in ((0, 10), (1, 9), (4, 6), (5, 5), (10, 0), (12, 0)):
            with self.subTest(minor_count=minor_count):
                report = reviewed()
                report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}") for i in range(minor_count)]
                result = score_report(report)
                self.assertEqual(result["overall"]["score"], expected)
                self.assertEqual(result["overall"]["qualification"], "pass" if expected >= 6 else "fail")
                self.assertEqual(result["overall"]["completion"], "complete")
                self.assertEqual(result["overall"]["tier"], "excellent" if expected >= 9 else "acceptable" if expected >= 6 else "unacceptable")
                self.assertEqual(result["overall"]["recommendable"], expected >= 9)
                self.assertEqual(validate_scored_report(result), [])

    def test_fatal_and_floor(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding(severity="fatal"), finding("f2", "r2")]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["total_penalty"], 11)
        self.assertEqual(result["overall"]["qualification"], "fail")

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

    def test_suspected_fatal_is_undetermined_without_deduction(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding(severity="fatal", status="suspected")]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["qualification"], "undetermined")
        self.assertEqual(result["overall"]["completion"], "complete")
        self.assertEqual(result["root_causes"][0]["points"], 0)

    def test_suspected_minor_does_not_prevent_pass(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding(status="suspected")]
        result = score_report(report)
        self.assertEqual(result["overall"]["qualification"], "pass")
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["suspected_finding_ids"], ["f1"])

    def test_confirmed_failure_takes_priority_over_suspected_fatal(self):
        for count, expected in ((5, 5), (10, 0)):
            report = reviewed()
            report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}") for i in range(count)] + [finding("pending", "suspected-root", "fatal", "suspected")]
            result = score_report(report)
            self.assertEqual(result["objects"]["solution"]["score"], expected)
            self.assertEqual(result["objects"]["solution"]["qualification"], "fail")
            self.assertEqual(result["overall"]["qualification"], "fail")
            self.assertEqual(result["overall"]["pending_finding_ids"], ["pending"])

    def test_fatal_failure_takes_priority_over_incomplete_coverage(self):
        report = make_report()
        report["objects"]["solution"]["findings"] = [finding(severity="fatal")]
        result = score_report(report)
        self.assertEqual(result["objects"]["solution"]["qualification"], "fail")
        self.assertEqual(result["objects"]["solution"]["completion"], "incomplete")
        self.assertEqual(result["objects"]["solution"]["score"], 0)
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["qualification"], "fail")
        self.assertEqual(result["overall"]["completion"], "incomplete")

    def test_minor_failure_takes_priority_over_incomplete_coverage(self):
        report = make_report(("solution",))
        report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}") for i in range(5)]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 5)
        self.assertEqual(result["overall"]["qualification"], "fail")
        self.assertEqual(result["overall"]["completion"], "incomplete")

    def test_resolved_requires_fresh_evidence_and_does_not_deduct(self):
        report = reviewed()
        report["snapshot"] = {"id": "snapshot-2", "revision": 2, "supersedes": "snapshot-1"}
        report["objects"]["solution"]["artifact_version"] = "v2"
        check_coverage(report, "solution")
        resolved = finding(severity="fatal", status="resolved", snapshot="snapshot-2", version="v2")
        resolved["repair"].update(status="applied", verification=["Re-run n=1 and observe 1"])
        report["objects"]["solution"]["findings"] = [resolved]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["root_causes"][0]["status"], "resolved")
        report["objects"]["solution"]["findings"][0]["evidence"][0]["snapshot_id"] = "snapshot-1"
        with self.assertRaises(ReportValidationError):
            score_report(report)

    def test_cross_object_root_uses_highest_confirmed_local_severity(self):
        report = reviewed(("statement", "solution"))
        report["objects"]["statement"]["findings"] = [finding("s", "shared")]
        report["objects"]["solution"]["findings"] = [finding("c", "shared", "major")]
        result = score_report(report)
        self.assertEqual(result["objects"]["statement"]["score"], 9)
        self.assertEqual(result["objects"]["solution"]["score"], 7)
        self.assertEqual(result["overall"]["score"], 7)
        self.assertEqual(result["overall"]["confirmed_counts"], {"fatal": 0, "major": 1, "minor": 0})
        self.assertEqual([state["severity"] for state in result["root_causes"][0]["local_states"]], ["minor", "major"])

    def test_partial_repair_preserves_unfixed_object_failure(self):
        report = reviewed(("statement", "solution", "editorial"))
        for name, status in (("statement", "resolved"), ("solution", "confirmed"), ("editorial", "suspected")):
            report["objects"][name]["findings"] = [finding(name, "shared", "fatal", status)]
        result = score_report(report)
        self.assertEqual(result["objects"]["statement"]["score"], 10)
        self.assertEqual(result["objects"]["statement"]["qualification"], "pass")
        self.assertEqual(result["objects"]["solution"]["qualification"], "fail")
        self.assertEqual(result["objects"]["editorial"]["qualification"], "undetermined")
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["qualification"], "fail")
        self.assertEqual(result["root_causes"][0]["status"], "confirmed")
        self.assertEqual(len(result["overall"]["deductions"]), 1)
        states = {state["object"]: state for state in result["root_causes"][0]["local_states"]}
        self.assertEqual({name: state["status"] for name, state in states.items()},
                         {"statement": "resolved", "solution": "confirmed", "editorial": "suspected"})
        self.assertEqual({name: state["points"] for name, state in states.items()},
                         {"statement": 0, "solution": 10, "editorial": 0})

    def test_root_status_precedence_is_order_independent(self):
        for left, right, expected in (("resolved", "suspected", "suspected"),
                                      ("suspected", "confirmed", "confirmed"),
                                      ("confirmed", "resolved", "confirmed")):
            for first, second in ((left, right), (right, left)):
                report = reviewed(("statement", "solution"))
                report["objects"]["statement"]["findings"] = [finding("s", "shared", status=first)]
                report["objects"]["solution"]["findings"] = [finding("c", "shared", status=second)]
                result = score_report(report)
                self.assertEqual(result["root_causes"][0]["status"], expected)
                self.assertEqual(result["overall"]["total_penalty"], 1 if expected == "confirmed" else 0)

    def test_scope_and_incomplete_review_are_distinct(self):
        scoped = score_report(reviewed())
        self.assertEqual(scoped["overall"]["qualification"], "pass")
        self.assertIsNone(scoped["objects"]["statement"]["score"])
        report = make_report()
        check_coverage(report, "solution")
        partial = score_report(report)
        self.assertEqual(partial["overall"]["score"], 10)
        self.assertEqual(partial["overall"]["qualification"], "undetermined")
        self.assertEqual(partial["overall"]["completion"], "incomplete")
        empty = score_report(make_report())
        self.assertIsNone(empty["overall"]["score"])
        self.assertEqual(empty["overall"]["qualification"], "undetermined")

    def test_partial_checked_coverage_has_score_but_cannot_pass(self):
        report = make_report(("solution",))
        report["objects"]["solution"]["coverage"]["algorithm"] = deepcopy(reviewed()["objects"]["solution"]["coverage"]["algorithm"])
        result = score_report(report)
        self.assertEqual(result["objects"]["solution"]["score"], 10)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["qualification"], "undetermined")
        self.assertEqual(result["overall"]["completion"], "incomplete")

    def test_blocked_coverage_cannot_pass(self):
        report = reviewed()
        report["objects"]["solution"]["coverage"]["correctness"] = {
            "status": "blocked", "evidence": [], "reason": "The referenced invariant proof was not supplied."}
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["qualification"], "undetermined")
        self.assertEqual(result["overall"]["completion"], "incomplete")

    def test_explained_not_applicable_coverage_can_complete(self):
        report = reviewed(("statement",))
        report["objects"]["statement"]["coverage"]["samples"] = {
            "status": "not_applicable", "evidence": [evidence(location="statement.md: full artifact", observation="This reviewed statement intentionally has no sample section.")],
            "reason": "There are no sample claims to check in this artifact."}
        result = score_report(report)
        self.assertEqual(result["overall"]["qualification"], "pass")
        self.assertEqual(result["overall"]["completion"], "complete")

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
        self.assertIn("algorithm", markdown)
        self.assertIn("checked", markdown)

    def test_tampered_output_rejected(self):
        output = score_report(reviewed())
        for value in (-1, 11, 9, True, float("nan")):
            changed = deepcopy(output)
            changed["overall"]["score"] = value
            self.assertTrue(validate_scored_report(changed))
        for field, value in (("qualification", "fail"), ("completion", "incomplete"), ("tier", "acceptable"), ("recommendable", False), ("confirmed_counts", {"fatal": 0, "major": 1, "minor": 0})):
            changed = deepcopy(output)
            changed["overall"][field] = value
            self.assertTrue(validate_scored_report(changed))
        changed = deepcopy(output)
        changed["overall"]["qualified"] = True
        self.assertTrue(validate_scored_report(changed))

    def test_three_level_formula_combinations_and_confirmed_counts(self):
        for severities, score in ((["major"], 7), (["major", "minor"], 6),
                                  (["major", "major"], 4), (["major", "minor", "minor"], 5),
                                  (["fatal", "minor", "minor"], 0)):
            for complete in (True, False):
                with self.subTest(severities=severities, complete=complete):
                    report = reviewed() if complete else make_report(("solution",))
                    report["objects"]["solution"]["findings"] = [finding(f"f{i}", f"r{i}", severity) for i, severity in enumerate(severities)]
                    result = score_report(report)["overall"]
                    self.assertEqual(result["score"], score)
                    self.assertEqual(result["confirmed_counts"], {s: severities.count(s) for s in ("fatal", "major", "minor")})
                    self.assertEqual(result["tier"], "unacceptable" if score < 6 else "acceptable" if complete else "undetermined")
                    self.assertEqual(result["recommendable"], False if score < 6 or complete else None)

    def test_high_provisional_score_never_recommends(self):
        report = reviewed()
        report["objects"]["solution"]["coverage"]["implementation"] = {"status": "unchecked", "evidence": [], "reason": None}
        for severity in (None, "minor", "major", "fatal"):
            for status in ("confirmed", "suspected"):
                report["objects"]["solution"]["findings"] = [] if severity is None else [finding(severity=severity, status=status)]
                result = score_report(report)["overall"]
                if severity == "fatal" and status == "confirmed":
                    self.assertEqual((result["tier"], result["recommendable"]), ("unacceptable", False))
                else:
                    self.assertEqual((result["tier"], result["recommendable"]), ("undetermined", None))

    def test_mixed_states_never_hide_suspected_fatal_or_inflate_penalty(self):
        for suspected_object in ("statement", "solution"):
            report = reviewed(("statement", "solution", "editorial"))
            confirmed_object = "solution" if suspected_object == "statement" else "statement"
            report["objects"][suspected_object]["findings"] = [finding("sus", "shared", "fatal", "suspected")]
            report["objects"][confirmed_object]["findings"] = [finding("con", "shared", "minor")]
            report["objects"]["editorial"]["findings"] = [finding("res", "shared", "major", "resolved")]
            result = score_report(report)
            self.assertEqual(result["overall"]["score"], 9)
            self.assertEqual(result["overall"]["pending_finding_ids"], ["sus"])
            self.assertEqual((result["overall"]["tier"], result["overall"]["recommendable"]), ("undetermined", None))
            self.assertEqual(result["root_causes"][0]["severity"], "minor")
            self.assertEqual(result["root_causes"][0]["status"], "confirmed")
            self.assertEqual(validate_scored_report(result), [])
            # Once the only confirmed occurrence is repaired, the suspected
            # Fatal controls the aggregate status but still does not deduct.
            report["objects"][confirmed_object]["findings"][0]["status"] = "resolved"
            result = score_report(report)
            self.assertEqual((result["overall"]["score"], result["root_causes"][0]["severity"], result["root_causes"][0]["status"]), (10, "fatal", "suspected"))

    def test_partial_repair_recalculates_severity_then_restores_recommendation(self):
        report = reviewed(("statement", "editorial"))
        report["objects"]["statement"]["findings"] = [finding("s", "shared", "minor")]
        report["objects"]["editorial"]["findings"] = [finding("e", "shared", "major")]
        self.assertEqual(score_report(report)["overall"]["score"], 7)
        for obj, expected in (("editorial", 9), ("statement", 10)):
            previous = report["snapshot"]["id"]
            revision = report["snapshot"]["revision"] + 1
            report["snapshot"] = {"id": f"snapshot-{revision}", "revision": revision, "supersedes": previous}
            report["objects"][obj]["artifact_version"] = f"v{revision}"
            # A new snapshot cannot blindly reuse any preceding evidence.
            with self.assertRaises(ReportValidationError):
                score_report(report)
            for name in report["scope"]:
                check_coverage(report, name)
                for issue in report["objects"][name]["findings"]:
                    issue["evidence"] = [evidence(snapshot=report["snapshot"]["id"], version=report["objects"][name]["artifact_version"], observation="Current snapshot verification of the local state.")]
            issue = report["objects"][obj]["findings"][0]
            issue["status"] = "resolved"
            issue["repair"].update(status="applied", verification=["Verified the correction on the new artifact."])
            result = score_report(report)["overall"]
            self.assertEqual(result["score"], expected)
            self.assertEqual((result["tier"], result["recommendable"]), ("excellent", True))

    def test_duplicate_occurrences_use_maximum_not_sum_and_are_order_independent(self):
        report = reviewed()
        issues = [finding("m", "shared", "minor"), finding("M", "shared", "major")]
        report["objects"]["solution"]["findings"] = issues
        first = score_report(report)
        report["objects"]["solution"]["findings"] = list(reversed(issues))
        second = score_report(report)
        self.assertEqual(first["overall"], second["overall"])
        self.assertEqual(first["root_causes"], second["root_causes"])
        self.assertEqual(first["overall"]["score"], 7)


if __name__ == "__main__":
    unittest.main()
