from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from tests.test_review_fixtures import CASES, FIXTURES, case_report

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

    def test_all_harness_entries_run_v3_and_include_portable_v2_migration(self):
        self.install()
        source = self.project / "review.json"
        source.write_text(json.dumps(case_report(CASES["editorial_minor"])))
        with zipfile.ZipFile(SOURCE / "tests/history/codex-v2.zip") as archive:
            index = json.loads(archive.read("index.json"))
            old_bytes = archive.read(index["runs"]["editorial"]["files"]["review.json"]["archive_path"])
        old = self.project / "v2.json"
        old.write_bytes(old_bytes)
        for name, config in HARNESSES.items():
            with self.subTest(harness=name):
                entry = self.project / config["directory"] / "cp-editorial-review/scripts/cpscore.py"
                def run(*args):
                    return subprocess.run([sys.executable, "-I", str(entry), *args], cwd=self.project.parent,
                                          capture_output=True, text=True, timeout=15)
                result = run("score", str(source), "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                scored = json.loads(result.stdout)
                self.assertEqual(scored["schema_version"], "3.0")
                self.assertEqual((scored["overall"]["score"], scored["overall"]["tier"], scored["overall"]["recommendable"]), (7, "acceptable", False))
                self.assertEqual(run("validate", str(old)).returncode, 2)
                new = self.project / f"{name}-migrated.json"
                result = run("migrate", str(old), "-o", str(new))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(Path(str(new) + ".legacy.json").read_bytes(), old_bytes)
                assessment = json.loads(run("score", str(new), "--format", "json").stdout)["overall"]
                self.assertEqual((assessment["tier"], assessment["recommendable"]), ("undetermined", None))

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
        content = json.loads(report.read_text(encoding="utf-8"))
        # A fresh installed skeleton must never become a false pass.
        initial = run("score", str(report), "--format", "json")
        initial_assessment = json.loads(initial.stdout)["overall"]
        self.assertIsNone(initial_assessment["score"])
        self.assertEqual(initial_assessment["qualification"], "undetermined")
        self.assertEqual(initial_assessment["completion"], "incomplete")
        # Use the checked, concrete P1083 derivative with a content hash and
        # dimension-specific observations, rather than changing a review flag.
        case = CASES["statement_correct"]
        shutil.copyfile(FIXTURES / case["artifact"], destination / "statement.md")
        content = case_report(case)
        for item in content["objects"]["statement"]["coverage"].values():
            for evidence in item["evidence"]:
                evidence["location"] = "statement.md"
        report.write_text(json.dumps(content))
        run("validate", str(report))
        scored = destination / "scored.json"
        run("score", str(report), "--format", "json", "--output", str(scored))
        assessment = json.loads(scored.read_text(encoding="utf-8"))["overall"]
        self.assertEqual(assessment["qualification"], "pass")
        self.assertEqual(assessment["completion"], "complete")
        # The moved bootstrap must also include the migration module and its
        # legacy schema. Preserve historical model bytes, never grant a pass.
        legacy = destination / "legacy.json"
        shutil.copyfile(SOURCE / "tests/history/v1-codex-statement.json", legacy)
        migrated = destination / "migrated.json"
        run("migrate", str(legacy), "--output", str(migrated))
        self.assertEqual(Path(str(migrated) + ".legacy.json").read_bytes(), legacy.read_bytes())
        run("validate", str(migrated))
        migrated_assessment = json.loads(run("score", str(migrated), "--format", "json").stdout)["overall"]
        self.assertEqual(migrated_assessment["qualification"], "undetermined")
        self.assertEqual(migrated_assessment["completion"], "incomplete")
        self.assertTrue(check(destination, ["codex"])["ok"])
        self.assertEqual(list((destination / ".cpscore").rglob("__pycache__")), [])
        uninstall(destination, ["codex"])
        install(destination, ["codex"], source=SOURCE)
        self.assertTrue(check(destination, ["codex"])["ok"])

    def test_installed_migration_is_portable_and_does_not_inherit_pass(self):
        self.install(["codex"])
        moved = self.project.with_name("portable migration")
        self.project.rename(moved)
        entry = moved / ".agents/skills/cp-statement-review/scripts/cpscore.py"
        legacy = moved / "old.json"
        original = (SOURCE / "tests/history/v1-codex-statement.json").read_bytes()
        legacy.write_bytes(original)
        destination = moved / "new.json"
        command = [sys.executable, "-I", str(entry), "migrate", str(legacy), "-o", str(destination)]
        result = subprocess.run(command, cwd=moved.parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertEqual(Path(str(destination) + ".legacy.json").read_bytes(), original)
        scored = subprocess.run([sys.executable, "-I", str(entry), "score", str(destination), "--format", "json"],
                                cwd=moved.parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)
        self.assertEqual(json.loads(scored.stdout)["overall"]["qualification"], "undetermined")
        before = destination.read_bytes()
        repeated = subprocess.run(command, cwd=moved.parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(repeated.returncode, 2)
        self.assertEqual(destination.read_bytes(), before)
        self.assertTrue(check(moved, ["codex"])["ok"])

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
        self.assertEqual((foreign / "SKILL.md").read_text(encoding="utf-8"), "belongs to someone else")

    def test_modified_owned_file_blocks_update_and_uninstall(self):
        self.install(["codex"])
        edited = self.project / ".agents/skills/cp-statement-review/SKILL.md"
        edited.write_text("user's edits")
        self.assertFalse(check(self.project, ["codex"])["ok"])
        before = (self.project / MANIFEST).read_bytes()
        for operation in (lambda: self.install(["codex"]), lambda: uninstall(self.project, ["codex"])):
            with self.assertRaises(InstallationError):
                operation()
        self.assertEqual(edited.read_text(encoding="utf-8"), "user's edits")
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
        self.assertEqual(foreign.read_text(encoding="utf-8"), "keep me")

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
        content = json.loads(path.read_text(encoding="utf-8"))
        content["files"]["../victim.txt"] = "0" * 64
        path.write_text(json.dumps(content))
        for operation in (lambda: check(self.project, ["codex"]), lambda: uninstall(self.project, ["codex"]), lambda: self.install(["codex"])):
            with self.assertRaises(InstallationError):
                operation()
        self.assertEqual(victim.read_text(encoding="utf-8"), "preserve")

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
        content = json.loads(manifest.read_text(encoding="utf-8"))
        content["files"] = {}
        manifest.write_text(json.dumps(content))
        with self.assertRaises(InstallationError):
            uninstall(self.project, ["codex"])


if __name__ == "__main__":
    unittest.main()
