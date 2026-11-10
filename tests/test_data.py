"""Data scoring, frozen-suite plumbing and adapter regressions.

FakeRunner simulates execution only. The opt-in container test is the only
test here that actually executes candidate programs.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from cpscore.data import evaluate_suite, load_suite, summarize_candidate
from cpscore.harness import HARNESSES, MANIFEST, V2_SKILLS, check, install, InstallationError
from cpscore.reporting import render_markdown
from cpscore.runner import ExecutionResult
from cpscore.schema import load_schema, validate_report, validate_schema, validate_scored_report
from cpscore.scoring import make_report, score_report
from tests.test_scoring import evidence, finding
from tests.test_validation import FakeRunner
from tests import downgrade_installation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/data_strength"


def data_report():
    report = make_report(["data"])
    for item in report["objects"]["data"]["coverage"].values():
        item.update(status="checked", evidence=[evidence(location="suite.json", observation="Synthetic fixture coverage only.")])
    return report


class DataScoringTests(unittest.TestCase):
    def test_default_legacy_report_remains_three_objects(self):
        self.assertEqual(set(make_report()["objects"]), {"statement", "solution", "editorial"})
        report = make_report(["data"])
        self.assertIsNone(score_report(report)["overall"]["score"])
        self.assertEqual(score_report(report)["overall"]["completion"], "incomplete")

    def test_data_deductions_share_the_canonical_scorer(self):
        for rule, severity, expected in (("data_gross_escape", "fatal", 0), ("data_local_escape", "major", 7), ("data_subtle_escape", "minor", 9)):
            report = data_report()
            report["objects"]["data"]["findings"] = [finding(rule_id=rule, severity=severity)]
            result = score_report(report)
            self.assertEqual(result["overall"]["score"], expected)
            self.assertEqual(result["objects"]["data"]["score"], expected)
            self.assertEqual(validate_scored_report(result), [])
            self.assertIn("| data | complete |", render_markdown(result))

    def test_duplicates_suspicions_and_cross_object_roots(self):
        report = data_report()
        report["objects"]["data"]["findings"] = [finding("d1", "same", "major", rule_id="data_local_escape"),
            finding("d2", "same", "minor", rule_id="data_subtle_escape")]
        self.assertEqual(score_report(report)["overall"]["score"], 7)
        report["scope"].append("solution")
        report["objects"]["solution"]["findings"] = [finding("s1", "same", "fatal", rule_id="wrong_answer")]
        self.assertEqual(score_report(report)["overall"]["total_penalty"], 10)
        report["objects"]["solution"]["findings"] = []
        report["objects"]["data"]["findings"] = [finding("d3", "unknown", "fatal", "suspected", rule_id="data_gross_escape")]
        result = score_report(report)
        self.assertEqual(result["overall"]["score"], 10)
        self.assertEqual(result["overall"]["qualification"], "undetermined")

    def test_data_scope_requires_data_and_rules_stay_in_their_object(self):
        report = make_report(["data"])
        del report["objects"]["data"]
        self.assertTrue(validate_schema(report, load_schema()))
        for obj, rule in (("solution", "data_gross_escape"), ("data", "wrong_answer")):
            report = make_report([obj])
            report["objects"][obj]["findings"] = [finding(rule_id=rule, severity="fatal")]
            self.assertTrue(validate_report(report))
        report = data_report()
        report["objects"]["data"]["findings"] = [finding(rule_id="data_local_escape", severity="minor")]
        self.assertTrue(validate_schema(report, load_schema()))

    def test_stale_evidence_and_tampered_scores_are_rejected(self):
        report = data_report()
        result = score_report(report)
        result["objects"]["data"]["score"] = 9
        self.assertTrue(validate_scored_report(result))
        report["objects"]["data"]["artifact_version"] = "new-data"
        self.assertTrue(validate_report(report))


class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / "fixture"
        shutil.copytree(FIXTURE, self.fixture)
        self.path = self.fixture / "suite.json"

    def fake(self, **kwargs):
        return FakeRunner(self.root, **kwargs)

    def run_suite(self, runner):
        return evaluate_suite(self.path, self.root / "evidence", runner=runner)

    def test_original_fixture_has_independently_checkable_weakness(self):
        for filename in ("01", "02", "counterexample"):
            values = list(map(int, (self.fixture / (filename + ".in")).read_text().split()))[1:]
            answer = int((self.fixture / (filename + ".ans")).read_text())
            self.assertEqual(max(values), answer)
            self.assertEqual(values[0] == answer, filename != "counterexample")

    def test_frozen_bytes_and_partial_credit_are_not_misclassified(self):
        document = json.loads(self.path.read_text())
        document["candidates"][0]["allowed_groups"] = ["01"]
        self.path.write_text(json.dumps(document))
        before = self.path.read_bytes()

        def output(program, stdin, arguments):
            # Explicit simulation, not executing any fixture source.
            values = list(map(int, stdin.split()))[1:]
            return ExecutionResult("ok", stdout=f"{max(values)}\n".encode())

        result = self.run_suite(self.fake(results={"candidate": output}))
        self.assertEqual(result["status"], "completed")
        row = result["candidates"][0]
        self.assertEqual((row["pass_fraction"], row["observed_points"], row["unexpected_points"]), (1, 2, 1))
        self.assertEqual(row["unexpected_groups"], ["02"])
        self.assertEqual(result["score_effect"], "none")
        self.assertEqual(self.path.read_bytes(), before)
        for record in json.loads((self.root / "evidence/files.json").read_text()):
            frozen = self.root / "evidence" / record["frozen"]
            self.assertEqual(hashlib.sha256(frozen.read_bytes()).hexdigest(), record["sha256"])
        # Replaying the saved manifest can relocate all of its source/data paths.
        moved = self.root / "moved evidence"
        (self.root / "evidence").rename(moved)
        suite = load_suite(moved / "suite.json")
        self.assertTrue(all(Path(c["input"]).is_relative_to(moved.resolve()) for c in suite["cases"]))

    def test_reference_disagreement_stops_candidate_and_keeps_original_answer(self):
        result = self.run_suite(self.fake(results={"candidate": ExecutionResult("ok", stdout=b"999\n")}))
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["reference_control_passed"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual((self.fixture / "01.ans").read_text().strip(), "3")

    def test_unavailable_and_invalid_input_do_not_claim_survival(self):
        for failure in (ExecutionResult("unavailable"), ExecutionResult("nonzero_exit", exit_code=1)):
            evidence_dir = self.root / failure.status
            fake = self.fake(results={"validator": failure})
            result = evaluate_suite(self.path, evidence_dir, runner=fake)
            self.assertEqual(result["status"], "inconclusive")
            self.assertEqual(result["candidates"], [])

    def test_incomplete_and_ce_never_get_a_rate_or_score(self):
        suite = load_suite(self.path)
        for report in ({"status": "candidate_compile_error", "cases": []},
                       {"status": "completed", "cases": [{"status": "match"}, {"status": "tool_error"}]}):
            row = summarize_candidate(suite, suite["candidates"][0], report)
            self.assertFalse(row["complete"])
            self.assertIsNone(row["pass_fraction"])
            self.assertIsNone(row["observed_points"])
            self.assertIsNone(row["unexpected_points"])

    def test_group_dependencies_obey_all_or_nothing_and_unknowns(self):
        suite = load_suite(self.path)
        suite["groups"] = [{"id": "partial", "points": 20, "cases": ["01"], "depends_on": []},
            {"id": "full", "points": 80, "cases": ["02"], "depends_on": ["partial"]}]
        candidate = {"id": "local", "mechanism": "fixture", "allowed_groups": ["partial"]}
        for outcomes, expected in ((("match", "sample_mismatch"), 20), (("sample_mismatch", "match"), 0), (("match", "match"), 100)):
            report = {"status": "completed", "cases": [{"status": x} for x in outcomes]}
            row = summarize_candidate(suite, candidate, report)
            self.assertEqual(row["observed_points"], expected)
            self.assertEqual(row["unexpected_points"], max(0, expected - 20))

    def test_manifest_rejects_ambiguous_or_invalid_inputs_before_writing(self):
        original = json.loads(self.path.read_text())
        mutations = [lambda d: d["cases"].append(deepcopy(d["cases"][0])),
                     lambda d: d["candidates"][0].pop("allowed_groups"),
                     lambda d: d.update(comparison={"mode": "float"}),
                     lambda d: d.update(checker="unsupported"),
                     lambda d: d.update(groups=[{"id": "g", "points": 100, "cases": ["01", "02"], "depends_on": ["g"]}]),
                     lambda d: d.update(groups=[{"id": "g", "points": True, "cases": ["01", "02"]}])]
        for mutate in mutations:
            document = deepcopy(original)
            mutate(document)
            self.path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                self.run_suite(self.fake())
            self.assertFalse((self.root / "evidence").exists())

    def test_existing_output_is_never_overwritten(self):
        directory = self.root / "evidence"
        directory.mkdir()
        (directory / "keep.txt").write_text("original")
        with self.assertRaises(FileExistsError):
            self.run_suite(self.fake())
        self.assertEqual((directory / "keep.txt").read_text(), "original")


class DataInstallationTests(unittest.TestCase):
    def test_v2_install_upgrades_and_data_entry_is_portable_for_all_harnesses(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            install(project, source=ROOT)
            downgrade_installation(project, 2)
            self.assertTrue(check(project)["ok"])
            self.assertEqual(check(project)["harnesses"]["codex"]["skills"], list(V2_SKILLS))
            install(project, source=ROOT)
            moved = Path(temp) / "moved"
            project.rename(moved)
            for config in HARNESSES.values():
                entry = moved / config["directory"] / "cp-data-review/scripts/cpscore.py"
                result = subprocess.run([sys.executable, "-I", str(entry), "init-report", "--scope", "data"],
                                        cwd=temp, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(validate_report(json.loads(result.stdout)), [])
                result = subprocess.run([sys.executable, "-I", str(entry), "test-data", "--help"],
                                        cwd=temp, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(check(moved)["ok"])

    def test_current_manifest_cannot_omit_data_handbook(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            install(project, ["codex"], source=ROOT)
            path = project / MANIFEST
            manifest = json.loads(path.read_text())
            del manifest["files"][".cpscore/data.md"]
            path.write_text(json.dumps(manifest))
            with self.assertRaises(InstallationError):
                check(project, ["codex"])


@unittest.skipUnless(os.environ.get("CPSCORE_RUN_CONTAINER_TESTS") == "1", "opt-in real container execution")
class DataContainerTests(unittest.TestCase):
    def test_real_first_element_candidate_survives_original_and_fails_counterexample(self):
        with tempfile.TemporaryDirectory() as temp:
            result = evaluate_suite(FIXTURE / "suite.json", Path(temp) / "original")
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(result["candidates"][0]["unexpected_points"], 2)
            suite = json.loads((FIXTURE / "suite.json").read_text())
            for key in ("reference", "validator"):
                suite[key] = str(FIXTURE / suite[key])
            suite["candidates"][0]["source"] = str(FIXTURE / "first.py")
            suite["cases"] = [{"id": "counterexample", "input": str(FIXTURE / "counterexample.in"),
                               "answer": str(FIXTURE / "counterexample.ans")}]
            path = Path(temp) / "probe.json"
            path.write_text(json.dumps(suite))
            result = evaluate_suite(path, Path(temp) / "probe")
            self.assertEqual(result["candidates"][0]["observed_points"], 0)


if __name__ == "__main__":
    unittest.main()
