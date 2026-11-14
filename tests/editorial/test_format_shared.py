"""The two independently installed review skills share format behavior and evidence."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sync_review_format", ROOT / "scripts/sync_review_format.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class BundleSyncTests(unittest.TestCase):
    def test_repository_bundles_match_the_common_source(self):
        self.assertEqual(SYNC.sync(ROOT, check=True), [])

    def test_check_is_read_only_and_resync_repairs_a_single_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "shared/review-format"
            source.mkdir(parents=True)
            for name in SYNC.FILES:
                (source / name).write_bytes((ROOT / "shared/review-format" / name).read_bytes())
            self.assertEqual(len(SYNC.sync(root)), len(SYNC.SKILLS) * len(SYNC.FILES))
            target = root / "skills/cp-statement-review/scripts/format_lint.py"
            target.write_bytes(b"local drift\n")
            self.assertEqual(SYNC.sync(root, check=True), [target.relative_to(root).as_posix()])
            self.assertEqual(target.read_bytes(), b"local drift\n")
            SYNC.sync(root)
            self.assertEqual(SYNC.sync(root, check=True), [])
            self.assertEqual(target.read_bytes(), (source / "format_lint.py").read_bytes())


class StandaloneReviewFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="cpscore shared format ")
        cls.root = Path(cls.temporary.name)
        cls.packages = {}
        for skill in SYNC.SKILLS:
            # Each install has only this skill, with no repository or sibling skill.
            package = cls.root / skill / "installed" / skill
            shutil.copytree(ROOT / "skills" / skill, package, ignore=shutil.ignore_patterns("__pycache__"))
            cls.packages[skill] = package

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def call(self, skill, *arguments):
        package = self.packages[skill]
        environment = dict(os.environ, PYTHONPATH="", PYTHONNOUSERSITE="1")
        result = subprocess.run(
            [sys.executable, str(package / "scripts/format_lint.py")] + list(map(str, arguments)),
            cwd=package.parent, env=environment, capture_output=True, text=True,
            encoding="utf-8", timeout=15,
        )
        return result.returncode, json.loads(result.stdout)

    def both(self, *arguments):
        results = [self.call(skill, *arguments) for skill in SYNC.SKILLS]
        self.assertEqual(results[0], results[1])
        return results[0]

    def test_each_standalone_package_exposes_the_same_environment_and_rules(self):
        code, checked = self.both("--check")
        self.assertEqual(code, 0)
        self.assertEqual(checked["format_assessment"]["verdict"], "not_assessed")
        code, rules = self.both("--rules")
        self.assertEqual(code, 0)
        self.assertEqual(next(rule for rule in rules["rules"] if rule["rule_id"] == "DOC001")["category"],
                         "document_layout")
        for package in self.packages.values():
            self.assertTrue((package / "references/format.md").is_file())
            self.assertEqual([p.name for p in package.parent.iterdir()], [package.name])

    def test_statement_inputs_samples_and_format_thresholds_match(self):
        sources = {
            "clean": "# 区间求和\n\n给定长度为 $n$ 的整数序列，要求输出元素之和。\n\n"
                     "## 输入格式\n\n第一行一个整数 $n$。\n\n第二行包含 $n$ 个整数。\n\n"
                     "## 样例输入\n\n```text\n2\n1 2\n```\n\n## 样例输出\n\n```text\n3\n```\n",
            "one": "中文English。\n",
            "two": "中文English中文。\n",
            "three": "中文English中文English。\n",
            "sentence": "给定一棵有根树，要求输出结点数量\n",
            "math": "数据保证 n >= 1。\n",
        }
        paths = []
        for name, source in sources.items():
            path = self.root / (name + ".md")
            path.write_text(source, encoding="utf-8")
            paths.append(path)
        before = {path: path.read_bytes() for path in paths}
        code, output = self.both(*paths)
        self.assertEqual(code, 0)
        files = {Path(item["file"]).stem: item["format_assessment"] for item in output["files"]}
        self.assertEqual(files["clean"]["verdict"], "pass")
        for name, count, severity, deduction in (("one", 1, "Major", 2), ("two", 2, "Major", 2),
                                                  ("three", 3, "Fatal", 10)):
            group = next(g for g in files[name]["groups"] if g["category"] == "missing_space")
            self.assertEqual((group["confirmed_count"], group["severity"], group["deduction"]),
                             (count, severity, deduction))
        self.assertTrue(any(g["category"] == "sentence_end" and g["confirmed_count"] == 1
                            for g in files["sentence"]["groups"]))
        self.assertEqual(before, {path: path.read_bytes() for path in paths})

    def test_decisions_work_across_both_skills_and_stale_evidence_is_rejected(self):
        source = self.root / "warning.md"
        source.write_text("这里刻意展示全角字母 Ａ。\n", encoding="utf-8")
        code, scan = self.both(source)
        self.assertEqual(code, 0)
        candidate = scan["review_candidates"][0]
        evidence = {"offset": candidate["offset"], "end_offset": candidate["end_offset"],
                    "excerpt": source.read_text(encoding="utf-8")[candidate["offset"]:candidate["end_offset"]]}
        record = {"files": [{"file": scan["files_checked"][0], "sha256": scan["files"][0]["sha256"],
                            "decisions": [{"candidate_id": candidate["candidate_id"], "verdict": "dismissed",
                                           "reason": "上下文明确是刻意展示该全角字母。",
                                           "evidence": [evidence]}]}]}
        decisions = self.root / "review.json"
        decisions.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        code, reviewed = self.both("--decisions", decisions, source)
        self.assertEqual(code, 0)
        self.assertTrue(reviewed["decisions_applied"])
        self.assertEqual(reviewed["format_assessment"]["verdict"], "pass")
        record["files"][0]["sha256"] = "0" * 64
        decisions.write_text(json.dumps(record), encoding="utf-8")
        code, rejected = self.both("--decisions", decisions, source)
        self.assertEqual(code, 2)
        self.assertFalse(rejected["decisions_applied"])
        self.assertEqual(rejected["effective_findings"], scan["findings"])
        self.assertNotEqual(rejected["format_assessment"]["verdict"], "pass")

    def test_llm_layout_findings_use_the_same_counting_and_deduplication(self):
        # Synthetic evidence checks the shared merge interface, not actual layout compliance.
        source = self.root / "layout.md"
        text = "# 输入格式\n\n# 数据范围\n\n# 子任务\n"
        source.write_text(text, encoding="utf-8")
        _, scan = self.both(source)
        additions = []
        for excerpt in ("输入格式", "数据范围", "子任务"):
            offset = text.index(excerpt)
            evidence = dict(offset=offset, end_offset=offset + len(excerpt), excerpt=excerpt)
            additions.append(dict(evidence, position=offset, category="document_layout",
                                  standard="合成接口测试的展示约定。", reason="模拟已核验的独立展示问题。",
                                  evidence=[evidence]))
        record = {"files": [{"file": scan["files_checked"][0], "sha256": scan["files"][0]["sha256"],
                            "additional_findings": additions + additions}]}
        decisions = self.root / "layout-review.json"
        decisions.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        code, output = self.both("--decisions", decisions, source)
        self.assertEqual(code, 0)
        group = next(g for g in output["format_assessment"]["groups"] if g["category"] == "document_layout")
        self.assertEqual((group["confirmed_count"], group["severity"], group["deduction"]), (3, "Fatal", 10))


if __name__ == "__main__":
    unittest.main()
