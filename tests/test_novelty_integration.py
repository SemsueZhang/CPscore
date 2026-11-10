"""Portable CLI, installed entry points, and legacy installation upgrades."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cpscore import novelty_evidence
from cpscore.harness import (
    HARNESSES, LEGACY_SKILLS, MANIFEST, SKILLS, InstallationError,
    check, install, uninstall,
)
from tests.test_novelty_evidence import fixture, options
from tests import downgrade_installation

SOURCE = Path(__file__).resolve().parents[1]


class NoveltyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "problem project"
        self.project.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *arguments, entry=None, expected=0):
        command = ([sys.executable, "-I", str(entry)] if entry else
                   [sys.executable, "-B", "-m", "cpscore"])
        result = subprocess.run(command+list(arguments), cwd=self.root if entry else SOURCE,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return json.loads(result.stdout)

    def legacy_install(self):
        install(self.project, ["codex"], source=SOURCE)
        downgrade_installation(self.project, 1)

    def test_source_cli_recovers_all_candidates_and_required_url_parameters(self):
        path = self.root / "record.json"
        path.write_text(json.dumps(fixture()))
        index = self.run_cli("novelty", "index", "--record", str(path))
        self.assertEqual(len(index["candidates"]), 60)
        member = index["candidates"][24]["group_members"][0]
        expanded = self.run_cli("novelty", "inspect", "--record", str(path), "--ids", member["id"])
        self.assertEqual(expanded["candidates"][0]["url"],
                         "https://acm.timus.ru/problem.aspx?space=1&num=1234")
        self.run_cli("novelty", "inspect", "--record", str(path), "--ids", "unknown", expected=1)

    def test_search_cli_reuses_complete_cache_with_default_depth(self):
        cache = self.root / "cache"
        # A cache miss would reach only a closed local port, never an external service.
        address = "http://127.0.0.1:1"
        with patch.object(novelty_evidence.search_module, "search", return_value=fixture()):
            novelty_evidence.search_cached(options(cpret_url=address), "model",
                self.root/"seed.json", cache)
        result = self.run_cli("novelty", "search", "cpret", "--query", "model",
            "--cpret-url", address, "--cache-dir", str(cache), "--output", str(self.root/"search.json"))
        self.assertTrue(result["cache_hit"])
        self.assertEqual(len(result["candidates"]), 60)

    def test_fourth_skill_moves_and_runs_without_repository_or_pip(self):
        install(self.project, ["codex"], source=SOURCE)
        destination = self.root / "moved project"
        self.project.rename(destination)
        entry = destination / ".agents/skills/cp-novelty-review/scripts/cpscore.py"
        path = self.root / "record.json"
        path.write_text(json.dumps(fixture()))
        index = self.run_cli("novelty", "index", "--record", str(path), entry=entry)
        self.assertEqual(len(index["candidates"]), 60)
        source = self.root / "source.txt"
        source.write_text("Definition\nLemma 10\nnecessary condition\n")
        output = self.root / "excerpt.json"
        excerpt = self.run_cli("novelty", "read", "--source-file", str(source),
            "--find", "Lemma 10", "--output", str(output), entry=entry)
        self.assertIn("necessary condition", excerpt["text"])
        usage = self.run_cli("novelty", "usage", "--ledger", str(self.root/"calls.jsonl"),
            "--output", str(self.root/"usage.json"), entry=entry)
        self.assertIsNone(usage["input_tokens"])
        self.assertEqual(usage["tool_calls"], 2)
        state = check(destination, ["codex"])
        self.assertTrue(state["ok"])
        self.assertEqual(state["harnesses"]["codex"]["skills"], list(SKILLS))
        self.assertEqual(list((destination/".cpscore").rglob("__pycache__")), [])
        uninstall(destination, ["codex"])
        self.assertFalse((destination/MANIFEST).exists())

    def test_all_harnesses_receive_current_skills_and_one_novelty_runtime(self):
        install(self.project, source=SOURCE)
        self.assertEqual(len(list(self.project.rglob("SKILL.md"))), len(SKILLS) * len(HARNESSES))
        self.assertEqual(len(list(self.project.rglob("novelty_evidence.py"))), 1)
        self.assertEqual(len(list(self.project.rglob("novelty_search.py"))), 1)
        for harness, state in check(self.project)["harnesses"].items():
            self.assertEqual(state["skills"], list(SKILLS), harness)
            self.assertEqual(state["file_installation"], "verified")

    def test_legacy_manifest_checks_and_upgrades_to_current_skills(self):
        self.legacy_install()
        state = check(self.project, ["codex"])
        self.assertTrue(state["ok"])
        self.assertEqual(state["harnesses"]["codex"]["skills"], list(LEGACY_SKILLS))
        install(self.project, ["codex"], source=SOURCE)
        self.assertEqual(json.loads((self.project/MANIFEST).read_text())["format"], 4)
        self.assertEqual(check(self.project, ["codex"])["harnesses"]["codex"]["skills"], list(SKILLS))

    def test_legacy_uninstall_remains_supported(self):
        self.legacy_install()
        uninstall(self.project, ["codex"])
        self.assertFalse((self.project/MANIFEST).exists())

    def test_legacy_user_edits_block_upgrade_before_adding_novelty(self):
        self.legacy_install()
        path = self.project / ".agents/skills/cp-statement-review/SKILL.md"
        path.write_text("personal edits")
        with self.assertRaises(InstallationError):
            install(self.project, ["codex"], source=SOURCE)
        self.assertEqual(path.read_text(), "personal edits")
        self.assertFalse((self.project/".agents/skills/cp-novelty-review").exists())

    def test_current_manifest_cannot_omit_novelty_shared_assets(self):
        install(self.project, ["codex"], source=SOURCE)
        path = self.project / MANIFEST
        record = json.loads(path.read_text())
        del record["files"][".cpscore/novelty.md"]
        path.write_text(json.dumps(record))
        with self.assertRaises(InstallationError):
            check(self.project, ["codex"])

    def test_novelty_does_not_add_a_correctness_scoring_object(self):
        initialized = self.run_cli("init-report")
        self.assertEqual(set(initialized["objects"]), {"statement", "solution", "editorial"})


if __name__ == "__main__":
    unittest.main()
