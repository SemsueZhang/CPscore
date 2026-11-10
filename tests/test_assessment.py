"""Behavioral contracts for minimum aggregation and portable report delivery.

Analyses here are synthetic fixtures, not claims about a real competition.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cpscore.assessment import assess, make_assessment, render_assessment, CONTEST
from cpscore.harness import HARNESSES, MANIFEST, SKILLS, V3_SKILLS, check, install, uninstall
from cpscore.scoring import make_report, score_report
from tests.test_scoring import evidence, finding
from tests import downgrade_installation

ROOT = Path(__file__).resolve().parents[1]


def judgment(verdict="推荐"):
    return {"verdict": verdict, "reason": "Synthetic analysis: the constraint matches the intended algorithm.", "evidence": ["statement.md: constraints and subtasks"], "edits": [] if verdict == "推荐" else ["Revise the overlapping subtask conditions."]}


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.review = make_report(("statement", "solution", "editorial", "data"))
        for obj in self.review["objects"].values():
            for entry in obj["coverage"].values():
                entry.update(status="checked", evidence=[evidence()], reason=None)
        self.write("review.json", self.review)
        (self.root / "novelty.md").write_text("Synthetic novelty fixture: F.", encoding="utf-8")
        self.problem = make_assessment("problem")
        self.problem.update(title="Synthetic problem", reviews=["review.json"], novelty=[{"grade": "F", "report": "novelty.md", "reason": "Synthetic precedent relation", "edits": []}])
        self.design = self.problem["design_reviews"][0]
        self.design["dimensions"] = {key: judgment() for key in self.design["dimensions"]}
        self.design["original_method"] = {"suitable": True, "reason": "The elementary route is within the intended audience's knowledge.", "simpler_alternative": None}

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def evaluate(self, record=None):
        return assess(record if record is not None else self.problem, base=self.root)

    def alternative(self):
        self.design["original_method"] = {"suitable": False, "reason": "The original method requires an obscure external theorem.", "simpler_alternative": {"verified": True, "description": "An elementary equivalent recurrence", "correctness": "Induction covers the full domain.", "complexity": "Linear in the full input size.", "suitability": "The recurrence follows from the first natural case split.", "evidence": ["alternative.md: proof and complexity"]}}

    def contest(self):
        self.write("problem.json", self.problem)
        record = make_assessment("contest")
        record.update(title="Synthetic contest", requirements={"audience": "Provincial OI contestants", "format": "individual OI", "duration_minutes": 300, "problem_count": 1, "scoring": "100 points, independent subtasks", "goals": ["separate intermediate contestants"], "constraints": []}, problems=[{"id": "T1", "points": 100, "review": "problem.json"}])
        record["assessments"] = {key: {**judgment(), "requirement_refs": ["audience", "duration_minutes", "goals"]} for key in CONTEST}
        return record

    def performance(self):
        record = make_assessment("performance")
        record.update(title="Synthetic prediction", context={"audience": "novices", "format": "individual OI", "duration_minutes": 120}, problems=[{"id": "T1", "title": "Sum", "max_score": 100}], assumptions=["Basic syntax and integer arithmetic are familiar."], cohorts=[{"name": "novice", "profile": "Knows arithmetic", "strategy": "Finish the direct task first", "predictions": [{"problem_id": "T1", "score_range": [20, 60], "time_range_minutes": [20, 50], "route": "Try direct enumeration then exploit the bound", "bottlenecks": "Full-range recurrence", "basis": "The first subtask supports enumeration", "confidence": "medium"}]}])
        return record

    def test_novelty_mapping_all_grades(self):
        for grade, expected in (("A", "不合格"), ("B", "不合格"), ("C", "合格"), ("D", "合格"), ("C+", "推荐"), ("F", "推荐")):
            with self.subTest(grade=grade):
                self.problem["novelty"][0].update(grade=grade, edits=["Change the core task to avoid the precedent."])
                self.assertEqual(self.evaluate()["verdict"], expected)

    def test_fatal_statement_dominates_every_other_recommendation(self):
        self.review["objects"]["statement"]["findings"] = [finding(severity="fatal")]
        self.write("review.json", self.review)
        result = self.evaluate()
        self.assertEqual(result["verdict"], "不合格")
        self.assertIn("Correct the boundary", render_assessment(result))

    def test_each_agent_object_can_veto_and_incomplete_failure_stays_incomplete(self):
        for name in self.review["scope"]:
            with self.subTest(object=name):
                review = deepcopy(self.review)
                review["objects"][name]["findings"] = [finding(severity="fatal")]
                key = next(iter(review["objects"][name]["coverage"]))
                review["objects"][name]["coverage"][key] = {"status": "unchecked", "reason": None, "evidence": []}
                self.write("review.json", review)
                result = self.evaluate()
                self.assertEqual(result["verdict"], "不合格")
                self.assertEqual(result["completion"], "incomplete")
                contest = self.contest()
                result = self.evaluate(contest)
                self.assertEqual(result["verdict"], "不合格")
                self.assertEqual(result["completion"], "incomplete")

    def test_minimum_is_not_cross_object_deduction_or_average(self):
        self.review["objects"]["statement"]["findings"] = [finding("s", "s", severity="major")]
        self.review["objects"]["editorial"]["findings"] = [finding("e", "e", severity="major")]
        self.write("review.json", self.review)
        self.assertEqual(score_report(self.review)["overall"]["tier"], "unacceptable")
        self.assertEqual(self.evaluate()["verdict"], "合格")

    def test_all_agents_participate_even_with_same_object(self):
        second = deepcopy(self.review)
        second["review_id"] = "second-agent"
        second["objects"]["solution"]["findings"] = [finding(severity="fatal")]
        self.write("second.json", second)
        self.problem["reviews"].append("second.json")
        self.assertEqual(self.evaluate()["verdict"], "不合格")
        other = deepcopy(self.design)
        other["id"] = "design-2"
        other["dimensions"]["coherence"] = judgment("不合格")
        self.problem["design_reviews"].append(other)
        self.assertEqual(self.evaluate()["verdict"], "不合格")

    def test_simpler_verified_method_caps_at_acceptable_with_edits(self):
        self.alternative()
        result = self.evaluate()
        self.assertEqual(result["verdict"], "合格")
        self.assertTrue(result["edits"])
        self.design["original_method"]["simpler_alternative"]["verified"] = False
        self.assertEqual(self.evaluate()["verdict"], "不合格")
        self.design["original_method"]["simpler_alternative"] = None
        self.assertEqual(self.evaluate()["verdict"], "不合格")

    def test_alternative_does_not_override_other_failures(self):
        self.alternative()
        self.design["dimensions"]["subtasks"] = judgment("不合格")
        self.assertEqual(self.evaluate()["verdict"], "不合格")
        self.design["dimensions"]["subtasks"] = judgment()
        self.review["objects"]["statement"]["findings"] = [finding(severity="fatal")]
        self.write("review.json", self.review)
        self.assertEqual(self.evaluate()["verdict"], "不合格")

    def test_incomplete_is_not_an_extra_quality_tier_or_false_pass(self):
        result = self.evaluate(make_assessment("problem"))
        self.assertIsNone(result["verdict"])
        self.assertEqual(result["completion"], "incomplete")
        self.review["objects"]["solution"]["coverage"]["correctness"] = {"status": "unchecked", "reason": None, "evidence": []}
        self.write("review.json", self.review)
        self.assertIsNone(self.evaluate()["verdict"])
        self.review["objects"]["statement"]["findings"] = [finding(severity="fatal")]
        self.write("review.json", self.review)
        self.assertEqual(self.evaluate()["verdict"], "不合格")
        self.assertEqual(self.evaluate()["completion"], "incomplete")

    def test_stored_scores_are_recomputed_and_versions_must_match(self):
        scored = score_report(self.review)
        scored["objects"]["statement"]["tier"] = "unacceptable"
        self.write("review.json", scored)
        self.assertEqual(self.evaluate()["verdict"], "推荐")
        other = make_report(("statement",))
        other["objects"]["statement"]["artifact_version"] = "v2"
        self.write("other.json", other)
        self.problem["reviews"].append("other.json")
        with self.assertRaisesRegex(ValueError, "不同材料版本"):
            self.evaluate()

    def test_contest_uses_concrete_requirements_and_problem_minimum(self):
        contest = self.contest()
        result = self.evaluate(contest)
        self.assertEqual(result["verdict"], "推荐")
        self.assertIn("Provincial OI", render_assessment(result))
        contest["assessments"]["time_budget"] = {**judgment("不合格"), "requirement_refs": ["duration_minutes"]}
        self.assertEqual(self.evaluate(contest)["verdict"], "不合格")
        contest = self.contest()
        self.problem["novelty"][0].update(grade="B", edits=["Replace the task."])
        self.write("problem.json", self.problem)
        self.assertEqual(self.evaluate(contest)["verdict"], "不合格")

    def test_contest_missing_requirements_count_and_refs(self):
        contest = self.contest()
        contest["requirements"]["audience"] = None
        self.assertIsNone(self.evaluate(contest)["verdict"])
        contest = self.contest()
        contest["requirements"]["problem_count"] = 2
        self.assertEqual(self.evaluate(contest)["verdict"], "不合格")
        contest["assessments"]["time_budget"]["requirement_refs"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "未知"):
            self.evaluate(contest)

    def test_contest_rejects_nested_contest_before_recursion(self):
        contest = self.contest()
        self.write("problem.json", contest)
        with self.assertRaisesRegex(ValueError, "必须为 problem"):
            self.evaluate(contest)

    def test_performance_report_has_predictions_and_no_verdict(self):
        record = self.performance()
        before = deepcopy(record)
        result = self.evaluate(record)
        self.assertNotIn("verdict", result)
        self.assertEqual(record, before)
        report = render_assessment(result)
        self.assertIn("20～60", report)
        self.assertIn("Full-range recurrence", report)
        self.assertIn("未进行盲测", report)
        self.assertNotIn("修改意见", report)

    def test_performance_rejects_impossible_ranges_and_missing_coverage(self):
        for field, bad in (("score_range", [60, 20]), ("score_range", [0, 101]), ("time_range_minutes", [0, 121])):
            record = self.performance()
            record["cohorts"][0]["predictions"][0][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                self.evaluate(record)
        record = self.performance()
        record["problems"].append({"id": "T2", "title": "Other", "max_score": 100})
        with self.assertRaisesRegex(ValueError, "覆盖所有题目"):
            self.evaluate(record)

    def test_cli_default_markdown_relative_paths_and_invalid_input(self):
        self.write("problem.json", self.problem)
        def run(*args, **options):
            return subprocess.run([sys.executable, "-B", "-m", "cpscore", *args], cwd=ROOT, capture_output=True, text=True, timeout=15, **options)
        for record in (self.problem, self.contest(), self.performance()):
            path = self.root / f"{record['kind']}.json"
            self.write(path.name, record)
            output = self.root / f"{record['kind']}.md"
            response = run("assess", "report", str(path), "-o", str(output))
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertTrue(output.read_text(encoding="utf-8").startswith("# "))
        response = run("assess", "init", "problem")
        self.assertEqual(json.loads(response.stdout)["kind"], "problem")
        response = run("assess", "report", "-", input='{"kind":"problem"}')
        self.assertEqual(response.returncode, 2)
        self.assertFalse(json.loads(response.stderr)["valid"])

    def test_three_new_installed_entries_move_and_render_without_source(self):
        project = self.root / "installed"
        project.mkdir()
        install(project, source=ROOT)
        for source in self.root.glob("*.json"):
            (project / source.name).write_bytes(source.read_bytes())
        (project / "novelty.md").write_bytes((self.root / "novelty.md").read_bytes())
        self.write("problem.json", self.problem)
        contest = self.contest()
        for record in (self.problem, contest, self.performance()):
            (project / f"{record['kind']}.json").write_text(json.dumps(record), encoding="utf-8")
        moved = self.root / "moved project"
        project.rename(moved)
        for config in HARNESSES.values():
            for skill, kind in (("cp-problem-review", "problem"), ("cp-contest-review", "contest"), ("cp-performance-predict", "performance")):
                entry = moved / config["directory"] / skill / "scripts/cpscore.py"
                result = subprocess.run([sys.executable, "-I", str(entry), "assess", "report", str(moved / f"{kind}.json")], cwd=self.root, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("# ", result.stdout)
        self.assertTrue(check(moved)["ok"])

    def test_v3_upgrade_preserves_old_installation_and_adds_new_skills(self):
        project = self.root / "v3"
        project.mkdir()
        install(project, ["codex"], source=ROOT)
        path = project / MANIFEST
        downgrade_installation(project, 3)
        self.assertTrue(check(project, ["codex"])["ok"])
        self.assertEqual(check(project, ["codex"])["harnesses"]["codex"]["skills"], list(V3_SKILLS))
        install(project, ["codex"], source=ROOT)
        self.assertEqual(json.loads(path.read_text())["format"], 4)
        self.assertEqual(check(project, ["codex"])["harnesses"]["codex"]["skills"], list(SKILLS))
        uninstall(project, ["codex"])
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
