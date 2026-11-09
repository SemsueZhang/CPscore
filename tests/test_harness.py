from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cpscore.harness import HARNESSES, MANIFEST, SKILLS, InstallationError, check, install, uninstall

SOURCE = Path(__file__).resolve().parents[1]


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cpscore-harness-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project with spaces"
        self.project.mkdir()

    def install(self, names=None):
        return install(self.project, names, source=SOURCE)

    def test_three_targets_share_runtime_and_reinstall(self):
        result = self.install()
        self.assertEqual(result["runtime_copies"], 1)
        self.assertEqual(set(result["harnesses"]), set(HARNESSES))
        before = (self.project / MANIFEST).read_bytes()
        self.install()
        self.assertEqual(before, (self.project / MANIFEST).read_bytes())
        with patch("cpscore.harness.shutil.which", return_value=None):
            result = check(self.project)
        self.assertTrue(result["ok"])
        self.assertEqual(len(list(self.project.rglob("scoring.py"))), 1)
        for entry in result["harnesses"].values():
            self.assertEqual(entry["file_installation"], "verified")
            self.assertFalse(entry["cli"]["on_path"])
            self.assertEqual(entry["invocation"], "not_verified")

    def test_installed_runtime_moves_and_runs_without_source_or_pip(self):
        self.install(["codex"])
        destination = self.project.with_name("moved project")
        self.project.rename(destination)
        entry = destination / ".agents/skills/cp-statement-review/scripts/cpscore.py"
        report = destination / "review.json"
        def run(*args):
            process = subprocess.run([sys.executable, "-I", str(entry), *args], cwd=destination.parent, capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return process
        run("init-report", "--scope", "statement", "--output", str(report))
        content = json.loads(report.read_text())
        content["objects"]["statement"]["review_status"] = "reviewed"
        report.write_text(json.dumps(content))
        run("validate", str(report))
        scored = destination / "scored.json"
        run("score", str(report), "--format", "json", "--output", str(scored))
        self.assertEqual(json.loads(scored.read_text())["overall"]["status"], "pass")
        self.assertTrue(check(destination, ["codex"])["ok"])
        self.assertEqual(list((destination / ".cpscore").rglob("__pycache__")), [])
        uninstall(destination, ["codex"])
        install(destination, ["codex"], source=SOURCE)
        self.assertTrue(check(destination, ["codex"])["ok"])

    def test_incremental_install_and_partial_uninstall(self):
        self.install(["codex"])
        self.install(["claude-code"])
        uninstall(self.project, ["codex"])
        self.assertFalse((self.project / ".agents/skills/cp-statement-review").exists())
        self.assertTrue(check(self.project, ["claude-code"])["ok"])
        self.assertTrue((self.project / ".cpscore/runtime/cpscore/scoring.py").exists())
        uninstall(self.project, ["claude-code"])
        self.assertFalse((self.project / MANIFEST).exists())
        self.install(["codex"])
        self.assertTrue(check(self.project, ["codex"])["ok"])

    def test_refuses_foreign_same_named_skill_before_any_write(self):
        foreign = self.project / ".opencode/skills/cp-editorial-review"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("belongs to someone else")
        with self.assertRaises(InstallationError):
            self.install()
        self.assertFalse((self.project / ".cpscore").exists())
        self.assertFalse((self.project / ".agents").exists())
        self.assertEqual((foreign / "SKILL.md").read_text(), "belongs to someone else")

    def test_modified_owned_file_blocks_update_and_uninstall(self):
        self.install(["codex"])
        edited = self.project / ".agents/skills/cp-statement-review/SKILL.md"
        edited.write_text("user's edits")
        self.assertFalse(check(self.project, ["codex"])["ok"])
        before = (self.project / MANIFEST).read_bytes()
        for operation in (lambda: self.install(["codex"]), lambda: uninstall(self.project, ["codex"])):
            with self.assertRaises(InstallationError):
                operation()
        self.assertEqual(edited.read_text(), "user's edits")
        self.assertEqual((self.project / MANIFEST).read_bytes(), before)

    def test_reinstall_repairs_missing_managed_file(self):
        self.install(["codex"])
        missing = self.project / ".agents/skills/cp-statement-review/scripts/cpscore.py"
        missing.unlink()
        self.assertFalse(check(self.project, ["codex"])["ok"])
        self.install(["codex"])
        self.assertTrue(missing.is_file())

    def test_uninstall_preserves_unknown_files(self):
        self.install(["codex"])
        foreign = self.project / ".agents/skills/cp-statement-review/my-notes.txt"
        foreign.write_text("keep me")
        uninstall(self.project, ["codex"])
        self.assertEqual(foreign.read_text(), "keep me")

    def test_no_fake_deepseek_harness_or_unknown_target(self):
        for name in ("deepseek", "made-up"):
            with self.assertRaises(InstallationError):
                self.install([name])
        self.assertFalse((self.project / ".deepseek").exists())
        self.assertFalse((self.project / ".cpscore").exists())

    def test_symlink_destination_does_not_escape(self):
        outside = self.project.parent / "outside"
        outside.mkdir()
        (self.project / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(InstallationError):
            self.install(["codex"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_traversal_rejected_without_deleting_victim(self):
        self.install(["codex"])
        victim = self.project.parent / "victim.txt"
        victim.write_text("preserve")
        path = self.project / MANIFEST
        content = json.loads(path.read_text())
        content["files"]["../victim.txt"] = "0" * 64
        path.write_text(json.dumps(content))
        for operation in (lambda: check(self.project, ["codex"]), lambda: uninstall(self.project, ["codex"]), lambda: self.install(["codex"])):
            with self.assertRaises(InstallationError):
                operation()
        self.assertEqual(victim.read_text(), "preserve")

    def test_manifest_and_owned_file_symlinks_rejected(self):
        self.install(["codex"])
        source = self.project / MANIFEST
        outside = self.project.parent / "manifest-copy.json"
        shutil.copyfile(source, outside)
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaises(InstallationError):
            uninstall(self.project, ["codex"])
        source.unlink()
        shutil.copyfile(outside, source)
        owned = self.project / ".agents/skills/cp-statement-review/SKILL.md"
        external = self.project.parent / "external.md"
        shutil.copyfile(owned, external)
        owned.unlink()
        owned.symlink_to(external)
        with self.assertRaises(InstallationError):
            uninstall(self.project, ["codex"])
        self.assertTrue(external.is_file())

    def test_foreign_cpscore_directory_is_not_claimed(self):
        (self.project / ".cpscore").mkdir()
        with self.assertRaises(InstallationError):
            self.install(["codex"])

    def test_empty_or_incomplete_forged_manifest_rejected(self):
        self.install(["codex"])
        manifest = self.project / MANIFEST
        content = json.loads(manifest.read_text())
        content["files"] = {}
        manifest.write_text(json.dumps(content))
        with self.assertRaises(InstallationError):
            uninstall(self.project, ["codex"])


if __name__ == "__main__":
    unittest.main()
