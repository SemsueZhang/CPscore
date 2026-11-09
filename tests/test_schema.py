from copy import deepcopy
import unittest

from cpscore.schema import SchemaSubsetError, load_schema, loads_json, validate_report, validate_schema, validate_scored_report
from cpscore.scoring import score_report
from tests.test_scoring import finding, reviewed


class SchemaTests(unittest.TestCase):
    def test_valid_report_and_generated_schema(self):
        report = reviewed()
        report["objects"]["solution"]["findings"] = [finding()]
        self.assertEqual(validate_report(report), [])
        self.assertEqual(validate_schema(report, load_schema()), [])
        self.assertEqual(validate_scored_report(score_report(report)), [])

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
        report = reviewed(); report["schema_version"] = "2.0"; cases.append(report)
        for report in cases:
            with self.subTest(report=report):
                self.assertTrue(validate_report(report))

    def test_json_schema_integer_semantics(self):
        report = reviewed()
        report["snapshot"]["revision"] = 1.0
        self.assertEqual(validate_report(report), [])

    def test_empty_missing_or_stale_evidence_rejected(self):
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

    def test_duplicate_finding_ids_across_objects(self):
        report = reviewed(("statement", "solution"))
        for name in report["scope"]:
            report["objects"][name]["findings"] = [finding()]
        errors = validate_report(report)
        self.assertTrue(any("duplicate finding id" in error.message for error in errors))

    def test_not_reviewed_and_scope_integrity(self):
        report = reviewed()
        report["objects"]["statement"]["findings"] = [finding()]
        self.assertTrue(validate_report(report))
        report["objects"]["statement"].update(review_status="reviewed", findings=[])
        self.assertTrue(validate_report(report))

    def test_rereview_snapshot_chain(self):
        for snapshot in (
            {"id":"s", "revision":1,"supersedes":"old"},
            {"id":"s", "revision":2,"supersedes":None},
            {"id":"s", "revision":2,"supersedes":"s"},
        ):
            report=reviewed(); report["snapshot"]=snapshot
            self.assertTrue(validate_report(report))

    def test_validation_execution_state_and_duplicate_check_ids(self):
        report = reviewed()
        check = {"id":"check1","name":"Compilation","object":"solution","status":"unexecuted","command":"g++ solution.cpp","outcome":None,"reason":"Compiler unavailable","evidence":[]}
        report["validations"] = [check]
        self.assertEqual(validate_report(report), [])
        check["status"] = "executed"
        self.assertTrue(validate_report(report))
        check.update(outcome="passed", reason=None, evidence=deepcopy(finding()["evidence"]))
        self.assertEqual(validate_report(report), [])
        report["validations"].append(deepcopy(check))
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
        self.assertEqual(loads_json('{"n":1.0}'), {"n":1.0})

    def test_unsupported_schema_keyword_and_json_equality(self):
        with self.assertRaises(SchemaSubsetError):
            validate_schema("x", {"format":"email"})
        self.assertFalse(validate_schema([{"x":True},{"x":1}], {"type":"array","uniqueItems":True}))
        self.assertTrue(validate_schema([{"x":1},{"x":1.0}], {"type":"array","uniqueItems":True}))
        self.assertTrue(validate_schema(False, {"enum":[0]}))


if __name__ == "__main__":
    unittest.main()
