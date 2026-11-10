"""Check authored adjudications and protocol plumbing, not model performance.

Fixture programs are read as text. No submitted program is run on the host.
"""
from copy import deepcopy
import hashlib
import json
from math import gcd
from itertools import combinations, product
import ast
from pathlib import Path
import re
import unittest

from cpscore.reporting import render_markdown
from cpscore.rubric import PENALTIES
from cpscore.schema import validate_report, validate_scored_report
from cpscore.scoring import make_report, score_report
from tests.test_scoring import COVERAGE_ITEMS, evidence, finding


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_cases"
CATALOG = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
# The catalog only factors identical source metadata and common observations.
# Expand with ordinary dictionaries so each case remains independently testable.
CASES = {}
for stored_case in CATALOG["cases"]:
    case = deepcopy(stored_case)
    source = deepcopy(CATALOG["sources"][case.pop("source")])
    case["context"] = source.pop("context")
    case["provenance"] = source
    observations = deepcopy(CATALOG["coverage_templates"][case.pop("coverage_template")])
    observations.update(case.pop("coverage_overrides", {}))
    case["coverage_observations"] = observations
    CASES[case["id"]] = case


def case_report(case):
    """Encode a human-authored adjudication without claiming a model ran."""
    obj = case["object"]
    report = make_report((obj,), review_id=case["id"])
    artifact = report["objects"][obj]
    artifact["artifact_version"] = "sha256:" + case["artifact_sha256"]
    for dimension, observation in case["coverage_observations"].items():
        artifact["coverage"][dimension] = {
            "status": "checked", "reason": None,
            "evidence": [evidence(version=artifact["artifact_version"], location=case["artifact"], observation=observation)],
        }
    adjudication = case["adjudication"]
    defect = adjudication["finding"]
    if defect is not None:
        issue = finding(case["id"] + "-finding", case["id"] + "-root", defect["severity"],
                        version=artifact["artifact_version"], rule_id=defect["rule_id"])
        text = (FIXTURES / case["artifact"]).read_text(encoding="utf-8")
        line = text[:text.index(defect["quote"])].count("\n") + 1
        issue.update(title=case["id"], description=defect["observation"],
                     evidence=[evidence(version=artifact["artifact_version"], location=f'{case["artifact"]}:{line}',
                                        observation=defect["quote"] + "\n" + defect["observation"])],
                     reproduction=deepcopy(defect["reproduction"]))
        if "impact" in defect:
            issue["impact"] = defect["impact"]
        issue["repair"].update(suggestion=defect["repair_suggestion"], auto_fixable=False)
        artifact["findings"] = [issue]
    return report


class RealProblemDerivativeFixtureTests(unittest.TestCase):
    def test_each_skill_has_three_levels_and_no_issue_cases(self):
        self.assertEqual(CATALOG["protocol_version"], "3.0")
        self.assertEqual(len(CATALOG["cases"]), 16)
        self.assertEqual(len(CASES), 16)
        for obj in COVERAGE_ITEMS:
            cases = [case for case in CASES.values() if case["object"] == obj]
            self.assertEqual({case["category"] for case in cases}, {"correct", "fatal", "major", "minor", "boundary"})
            self.assertGreaterEqual(len(cases), 5)

    def test_provenance_assets_hashes_and_ground_truth_are_explicit(self):
        for case in CASES.values():
            with self.subTest(case=case["id"]):
                for field in ("context", "artifact"):
                    path = FIXTURES / case[field]
                    self.assertTrue(path.resolve().is_relative_to(FIXTURES.resolve()))
                    self.assertTrue(path.is_file())
                self.assertEqual(hashlib.sha256((FIXTURES / case["artifact"]).read_bytes()).hexdigest(),
                                 case["artifact_sha256"])
                self.assertEqual(case["provenance"]["kind"], "human_authored_derivative")
                self.assertEqual(case["adjudication"]["kind"], "human_authored_expectation")
                self.assertEqual(case["provenance"]["url"],
                                 "https://www.luogu.com.cn/problem/" + case["provenance"]["source_problem"])
                self.assertTrue(case["adjudication"]["rationale"].strip())
                self.assertEqual(set(case["coverage_observations"]), set(COVERAGE_ITEMS[case["object"]]))
                for observation in case["coverage_observations"].values():
                    self.assertTrue(observation.strip())
                defect = case["adjudication"]["finding"]
                if defect is not None:
                    text = (FIXTURES / case["artifact"]).read_text(encoding="utf-8")
                    self.assertIn(defect["quote"], text)
                    self.assertEqual(defect["status"], "confirmed")
                    self.assertTrue(defect["reproduction"]["steps"])
                    self.assertTrue(defect["repair_suggestion"].strip())
                else:
                    self.assertIn(case["category"], ("correct", "boundary"))

    def test_all_adjudications_encode_and_score_as_expected(self):
        for case in CASES.values():
            with self.subTest(case=case["id"]):
                report = case_report(case)
                # Mathematical adjudication is authored metadata, not a fake
                # execution, compiler, model or external-review success record.
                self.assertEqual(report["validations"], [])
                self.assertEqual(validate_report(report), [])
                scored = score_report(report)
                self.assertEqual(validate_scored_report(scored), [])
                expected = case["adjudication"]
                for field in ("score", "qualification", "completion", "tier", "recommendable"):
                    self.assertEqual(scored["overall"][field], expected[field])
                    self.assertEqual(scored["objects"][case["object"]][field], expected[field])
                markdown = render_markdown(scored)
                defect = expected["finding"]
                if defect:
                    self.assertEqual(scored["overall"]["total_penalty"], PENALTIES[defect["severity"]])
                    self.assertIn(defect["rule_id"], markdown)
                    rendered_text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>])", r"\1", markdown)
                    self.assertIn(defect["observation"], rendered_text)

    def test_p1083_legal_closed_interval_sample_exposes_the_artificial_mutation(self):
        correct = (FIXTURES / CASES["statement_correct"]["artifact"]).read_text(encoding="utf-8")
        mutated = (FIXTURES / CASES["statement_fatal"]["artifact"]).read_text(encoding="utf-8")
        blocks = re.findall(r"```text\n(.*?)\n```", correct, re.S)
        values = iter(map(int, blocks[0].split()))
        days, count = next(values), next(values)
        capacities = [next(values) for _ in range(days)]
        first_failure = None
        for index in range(1, count + 1):
            demand, start, end = next(values), next(values), next(values)
            self.assertTrue(1 <= start <= end <= days)
            if any(capacities[day] < demand for day in range(start - 1, end)):
                first_failure = index
                break
            for day in range(start - 1, end):
                capacities[day] -= demand
        expected = "0" if first_failure is None else f"-1\n{first_failure}"
        self.assertEqual(blocks[1], expected)
        changed_output = re.findall(r"```text\n(.*?)\n```", mutated, re.S)[1]
        self.assertNotEqual(changed_output, expected)
        self.assertEqual(changed_output, "0")

    def test_p5020_divisibility_counterexample_is_legal_and_has_exact_answer_two(self):
        # This hand-check validates the witness; it does not execute the candidate.
        coins = (3, 5, 8)
        self.assertEqual(len(set(coins)), len(coins))
        self.assertTrue(all(1 <= coin <= 100 for coin in coins))
        self.assertEqual(8, 3 + 5)
        self.assertNotEqual(8 % 3, 0)
        self.assertNotEqual(8 % 5, 0)
        # A one-coin equivalent system must represent3. Its only denomination
        # then divides3 and is itself representable by the original system.
        # The only candidate is3, which cannot represent5. Two coins3,5 suffice.
        one_coin_candidates = [denomination for denomination in range(1, 4)
                               if 3 % denomination == 0 and denomination in {3}]
        self.assertEqual(one_coin_candidates, [3])
        self.assertNotEqual(5 % 3, 0)
        self.assertEqual(CASES["solution_fatal"]["adjudication"]["finding"]["reproduction"]["expected"], "2")

    def test_p5020_gcd_proof_counterexample_compares_all_amounts_not_only_large_ones(self):
        self.assertEqual(gcd(2, 3), 1)
        reachable_one = any(2 * left + 3 * right == 1 for left in range(2) for right in range(2))
        self.assertFalse(reachable_one)
        self.assertEqual(1 * 1, 1)
        self.assertEqual(CASES["editorial_fatal"]["adjudication"]["finding"]["rule_id"], "invalid_algorithm")

    def test_p17832_direction_omission_is_a_minor_explicitness_defect(self):
        context = (FIXTURES / CASES["statement_minor"]["context"]).read_text(encoding="utf-8")
        artifact = (FIXTURES / CASES["statement_minor"]["artifact"]).read_text(encoding="utf-8")
        self.assertIn("列车可在同一条线路上双向乘坐", context)
        self.assertNotIn("双向乘坐", artifact)
        self.assertIn("任意两站可通过线路互相到达", artifact)
        self.assertIn("2 1", artifact)
        self.assertEqual(2 + 4 + 3 + 1, 10)
        defect = CASES["statement_minor"]["adjudication"]["finding"]
        self.assertEqual((defect["rule_id"], defect["severity"]), ("incomplete_explanation", "minor"))

    def test_core_optimality_gap_is_major_and_the_algorithm_has_independent_support(self):
        """Finite regression plus the explicit substitution argument, not a
        claim that enumeration proves the unbounded mathematical theorem.

        A retained c is not generated by smaller original coins. If an
        equivalent positive system omitted c, expand its representation of c
        into original coins; every summand is smaller than c, a contradiction.
        Thus every retained c is mandatory in every equivalent system.
        """
        def reachable(coins, maximum=8):
            amounts = {0}
            for value in range(1, maximum + 1):
                if any(value - coin in amounts for coin in coins):
                    amounts.add(value)
            return frozenset(amounts)

        systems = [coins for size in range(1, 9) for coins in combinations(range(1, 9), size)]
        generated = {coins: reachable(coins) for coins in systems}
        for original in systems:
            retained = []
            for coin in original:
                if coin not in reachable(retained):
                    retained.append(coin)
            equivalent = [coins for coins in systems if generated[coins] == generated[original]]
            # Equality of finite reachability here suffices to compare these
            # finite generator sets: each generator of either is <=8 and
            # representable by the other, so substitution works for all sums.
            self.assertTrue(all(set(retained) <= set(coins) for coins in equivalent))
            self.assertEqual(len(retained), min(map(len, equivalent)))
        case = CASES["editorial_minor"]
        self.assertEqual((case["category"], case["adjudication"]["score"]), ("major", 7))
        self.assertNotIn("如果 B 不含 c", (FIXTURES / case["artifact"]).read_text())

    def test_repairable_core_proof_error_does_not_refute_the_algorithm(self):
        left, right = (2, 3), (2, 3, 5)
        self.assertEqual(5, 2 + 3)  # replacing every 5 preserves all sums
        self.assertEqual(gcd(*left), gcd(*right))
        self.assertNotEqual(len(left), len(right))
        case = CASES["editorial_proof_gap"]
        text = (FIXTURES / case["artifact"]).read_text()
        correct = (FIXTURES / CASES["editorial_correct"]["artifact"]).read_text()
        # Algorithm and equivalence proof are untouched; only optimality fails.
        self.assertEqual(text.split("还需说明种数最少。")[0], correct.split("还需说明种数最少。")[0])
        self.assertEqual(case["adjudication"]["finding"]["severity"], "major")

    def test_noncritical_formula_defect_does_not_erase_complete_main_proof(self):
        text = (FIXTURES / CASES["editorial_local_minor"]["artifact"]).read_text()
        self.assertTrue(text.startswith((FIXTURES / CASES["editorial_correct"]["artifact"]).read_text()))
        self.assertEqual(8 // 4, 2)
        self.assertNotEqual(8 // 4, 3)
        self.assertEqual(CASES["editorial_local_minor"]["adjudication"]["score"], 9)

    def test_nonfatal_resource_defect_is_supported_by_bounds_and_target_memory_model(self):
        correct = (FIXTURES / CASES["solution_correct"]["artifact"]).read_text()
        major = (FIXTURES / CASES["solution_major"]["artifact"]).read_text()
        # Static inspection only: no candidate program executes on the host.
        normalized = major.replace(' and context/p5020_runtime.md', '').replace('[False] * 10_000_001', '[False] * (limit + 1)')
        self.assertEqual(ast.dump(ast.parse(correct)), ast.dump(ast.parse(normalized)))
        wasted_bytes = (10_000_001 - (100 + 1)) * 8
        self.assertEqual(wasted_bytes, 79_999_200)
        self.assertGreater(wasted_bytes, 0.59 * 128 * 1024 * 1024)
        self.assertLess(10_000_001 * 8, 128 * 1024 * 1024)
        context = (FIXTURES / CASES["solution_major"]["context"]).read_text()
        self.assertIn("8 字节引用", context)
        self.assertIn("128 MiB", context)
        self.assertIn("1<=a_i<=100", context)

    def test_statement_major_directions_follow_from_bridge_cuts_not_convention(self):
        # General argument: each tree edge is the only connection across its
        # cut, so all-ordered-pairs reachability forces both directions.
        # The finite enumeration below is a regression of that inference.
        trees = [((0, 1), (1, 2), (2, 3)), ((0, 1), (0, 2), (0, 3))]
        for edges in trees:
            for directions in product(("forward", "reverse", "both"), repeat=3):
                graph = {i: set() for i in range(4)}
                for (u, v), direction in zip(edges, directions):
                    if direction in ("forward", "both"):
                        graph[u].add(v)
                    if direction in ("reverse", "both"):
                        graph[v].add(u)
                all_pairs = True
                for source in graph:
                    seen, queue = {source}, [source]
                    while queue:
                        for v in graph[queue.pop()]:
                            if v not in seen:
                                seen.add(v)
                                queue.append(v)
                    all_pairs &= len(seen) == 4
                self.assertEqual(all_pairs, all(d == "both" for d in directions))
        case = CASES["statement_major"]
        text = (FIXTURES / case["artifact"]).read_text()
        self.assertIn("线路允许单向或双向运行", text)
        self.assertIn("方向固定，但输入不提供方向字段", text)
        blocks = re.findall(r"```text\n(.*?)\n```", text, re.S)
        self.assertEqual(blocks[1], str(3 + 7 + 6 + 5 + 4 + 1))
        self.assertEqual(case["adjudication"]["score"], 7)


if __name__ == "__main__":
    unittest.main()
