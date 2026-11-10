from copy import deepcopy
import unittest

from cpscore.schema import SchemaSubsetError, load_schema, loads_json, validate_report, validate_schema, validate_scored_report
from cpscore.scoring import make_report, score_report
from tests.test_scoring import COVERAGE_ITEMS, check_coverage, evidence, finding, reviewed


class SchemaTests(unittest.TestCase):
    def test_valid_report_and_generated_schema(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding()]
        self.assertEqual(validate_report(report), [])
        self.assertEqual(validate_schema(report, load_schema()), [])
        self.assertEqual(validate_scored_report(score_report(report)), [])

    def test_v3_skeleton_has_fixed_unchecked_dimensions(self):
        report = make_report()
        self.assertEqual(report["schema_version"], "3.0")
        for name, dimensions in COVERAGE_ITEMS.items():
            artifact = report["objects"][name]
            self.assertEqual(set(artifact), {"artifact_version", "coverage", "findings"})
            self.assertEqual(set(artifact["coverage"]), set(dimensions))
            for entry in artifact["coverage"].values():
                self.assertEqual(entry, {"status": "unchecked", "evidence": [], "reason": None})

    def test_strict_fields_types_and_score_injection(self):
        cases = []
        report = reviewed(); report["score"] = 10; cases.append(report)
        report = reviewed(); report["objects"]["solution"]["score"] = -1; cases.append(report)
        report = reviewed(); report["snapshot"]["revision"] = True; cases.append(report)
        report = reviewed(); report["snapshot"]["revision"] = 1.5; cases.append(report)
        report = reviewed(); report["scope"] = ["solution", "solution"]; cases.append(report)
        report = reviewed(); report["scope"] = []; cases.append(report)
        report = reviewed(); report["objects"]["solution"]["artifact_version"] = "   "; cases.append(report)
        report = reviewed(); del report["objects"]["statement"]; cases.append(report)
        report = reviewed(); report["schema_version"] = "1.0"; cases.append(report)
        report = reviewed(); report["objects"]["solution"]["review_status"] = "reviewed"; cases.append(report)
        for report in cases:
            with self.subTest(report=report):
                self.assertTrue(validate_report(report))

    def test_json_schema_integer_semantics(self):
        report = reviewed()
        report["snapshot"]["revision"] = 1.0
        self.assertEqual(validate_report(report), [])

    def test_empty_missing_or_stale_finding_evidence_rejected(self):
        for mutate in (
            lambda f: f.update(evidence=[]),
            lambda f: f["evidence"][0].update(observation=""),
            lambda f: f["evidence"][0].update(location="\n"),
            lambda f: f["evidence"][0].update(snapshot_id="old"),
            lambda f: f["evidence"][0].update(artifact_version="old"),
            lambda f: f["reproduction"].update(steps=[]),
            lambda f: f["repair"].update(suggestion=""),
        ):
            report = reviewed(); issue = finding(); mutate(issue)
            report["objects"]["solution"]["findings"] = [issue]
            self.assertTrue(validate_report(report))

    def test_fixed_coverage_maps_reject_missing_unknown_or_foreign_dimensions(self):
        for name, dimensions in COVERAGE_ITEMS.items():
            for variant in ("missing", "unknown", "wrong_object"):
                report = reviewed((name,))
                coverage = report["objects"][name]["coverage"]
                if variant == "missing":
                    del coverage[dimensions[0]]
                elif variant == "unknown":
                    coverage["general_impression"] = deepcopy(coverage[dimensions[0]])
                else:
                    report["objects"][name]["coverage"] = deepcopy(reviewed(("editorial" if name != "editorial" else "statement",))["objects"]["editorial" if name != "editorial" else "statement"]["coverage"])
                with self.subTest(name=name, variant=variant):
                    self.assertTrue(validate_report(report))

    def test_coverage_state_obligations_and_current_evidence_binding(self):
        for mutation in (
            {"status": "checked", "evidence": [], "reason": None},
            {"status": "blocked", "evidence": [], "reason": None},
            {"status": "blocked", "evidence": [], "reason": " "},
            {"status": "not_applicable", "evidence": [], "reason": "No implementation is present."},
            {"status": "not_applicable", "evidence": [evidence()], "reason": None},
            {"status": "checked", "evidence": [evidence(snapshot="old")], "reason": None},
            {"status": "checked", "evidence": [evidence(version="old")], "reason": None},
            {"status": "checked", "evidence": [evidence(observation=" ")], "reason": None},
            {"status": "reviewed", "evidence": [evidence()], "reason": None},
            {"status": "unchecked", "evidence": [evidence()], "reason": None},
            {"status": "unchecked", "evidence": [], "reason": "Not started"},
        ):
            report = reviewed()
            report["objects"]["solution"]["coverage"]["algorithm"] = mutation
            with self.subTest(mutation=mutation):
                self.assertTrue(validate_report(report))

    def test_old_snapshot_or_artifact_version_invalidates_coverage_even_without_findings(self):
        for change in ("snapshot", "artifact_version"):
            report = reviewed()
            if change == "snapshot":
                report["snapshot"] = {"id": "snapshot-2", "revision": 2, "supersedes": "snapshot-1"}
            else:
                report["objects"]["solution"]["artifact_version"] = "v2"
            self.assertTrue(validate_report(report))
            check_coverage(report, "solution")
            self.assertEqual(validate_report(report), [])

    def test_rule_id_is_required_known_and_severity_is_fixed(self):
        fixed = {"incorrect_sample": "fatal", "wrong_answer": "fatal", "invalid_algorithm": "fatal", "invalid_proof": "major",
                 "ambiguous_answer": "fatal", "quality_defect": "major", "local_presentation": "minor"}
        for rule, severity in fixed.items():
            report = reviewed()
            issue = finding(rule_id=rule, severity=severity)
            report["objects"]["solution"]["findings"] = [issue]
            self.assertEqual(validate_report(report), [])
            issue["severity"] = "minor" if severity == "fatal" else "fatal"
            self.assertTrue(validate_report(report), rule)
        for mutate in (lambda f: f.pop("rule_id"), lambda f: f.update(rule_id="my_rule")):
            report = reviewed(); issue = finding(); mutate(issue)
            report["objects"]["solution"]["findings"] = [issue]
            self.assertTrue(validate_report(report))
        for severity in ("fatal", "major", "minor"):
            report = reviewed(); report["objects"]["solution"]["findings"] = [finding(rule_id="other", severity=severity)]
            self.assertEqual(validate_report(report), [])

    def test_suspected_requires_a_specific_evidence_gap(self):
        for gap in (None, "", " "):
            report = reviewed()
            issue = finding(status="suspected")
            if gap is None:
                issue.pop("evidence_gap")
            else:
                issue["evidence_gap"] = gap
            report["objects"]["solution"]["findings"] = [issue]
            self.assertTrue(validate_report(report))
        report["objects"]["solution"]["findings"][0]["evidence_gap"] = "Need the missing invariant proof to establish reachability."
        self.assertEqual(validate_report(report), [])

    def test_explanation_severity_and_quality_impact_are_explicit(self):
        for severity in ("major", "minor"):
            report = reviewed(("editorial",))
            issue = finding(severity=severity, rule_id="incomplete_explanation")
            report["objects"]["editorial"]["findings"] = [issue]
            self.assertEqual(validate_report(report), [])
            for impact in (None, "", " "):
                issue["impact"] = impact
                self.assertTrue(validate_report(report))
            issue.pop("impact")
            self.assertTrue(validate_report(report))
        issue["severity"] = "fatal"
        self.assertTrue(validate_report(report))

    def test_local_root_status_conflict_requires_a_coherent_current_state(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding("f1", "shared", "major"), finding("f2", "shared", "minor", "resolved")]
        self.assertTrue(any("conflicting local status" in i.message for i in validate_report(report)))

    def test_duplicate_finding_ids_across_objects(self):
        report = reviewed(("statement", "solution"))
        for name in report["scope"]:
            report["objects"][name]["findings"] = [finding()]
        errors = validate_report(report)
        self.assertTrue(any("duplicate finding id" in error.message for error in errors))

    def test_out_of_scope_findings_and_coverage_are_rejected(self):
        report = reviewed()
        report["objects"]["statement"]["findings"] = [finding()]
        self.assertTrue(validate_report(report))
        report["objects"]["statement"]["findings"] = []
        check_coverage(report, "statement")
        self.assertTrue(validate_report(report))

    def test_rereview_snapshot_chain(self):
        for snapshot in (
            {"id": "s", "revision": 1, "supersedes": "old"},
            {"id": "s", "revision": 2, "supersedes": None},
            {"id": "s", "revision": 2, "supersedes": "s"},
        ):
            report = reviewed(); report["snapshot"] = snapshot
            self.assertTrue(validate_report(report))

    def test_validation_execution_state_and_duplicate_check_ids(self):
        report = reviewed()
        check = {"id": "check1", "name": "Compilation", "object": "solution", "status": "unexecuted", "command": "g++ solution.cpp", "outcome": None, "reason": "Compiler unavailable", "evidence": []}
        report["validations"] = [check]
        self.assertEqual(validate_report(report), [])
        check["status"] = "executed"
        self.assertTrue(validate_report(report))
        check.update(outcome="passed", reason=None, evidence=deepcopy(finding()["evidence"]))
        self.assertEqual(validate_report(report), [])
        report["validations"].append(deepcopy(check))
        self.assertTrue(validate_report(report))

    def test_stale_validation_evidence_is_rejected(self):
        for stale in (evidence(snapshot="old"), evidence(version="old")):
            report = reviewed()
            report["validations"] = [{"id": "manual", "name": "Manual derivation", "object": "solution", "status": "executed",
                                      "command": None, "outcome": "passed", "reason": None, "evidence": [stale]}]
            self.assertTrue(validate_report(report))

    def test_applied_repair_requires_resolved_and_verification(self):
        report = reviewed(); issue = finding(); issue["repair"]["status"] = "applied"
        report["objects"]["solution"]["findings"] = [issue]
        self.assertTrue(validate_report(report))
        issue["status"] = "resolved"
        self.assertTrue(validate_report(report))
        issue["repair"]["verification"] = ["Run the reproducer on the current version"]
        self.assertEqual(validate_report(report), [])

    def test_non_finite_numbers_and_duplicate_keys(self):
        for raw in ('{"a":1,"a":2}', '{"a":{"b":1,"b":2}}', 'NaN', 'Infinity', '-Infinity', '1e9999'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                loads_json(raw)
        self.assertEqual(loads_json('{"n":1.0}'), {"n": 1.0})

    def test_unsupported_schema_keyword_and_json_equality(self):
        with self.assertRaises(SchemaSubsetError):
            validate_schema("x", {"format": "email"})
        self.assertFalse(validate_schema([{"x": True}, {"x": 1}], {"type": "array", "uniqueItems": True}))
        self.assertTrue(validate_schema([{"x": 1}, {"x": 1.0}], {"type": "array", "uniqueItems": True}))
        self.assertTrue(validate_schema(False, {"enum": [0]}))


if __name__ == "__main__":
    unittest.main()
