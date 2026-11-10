"""Controller regressions using explicit stubs, never model-success evidence."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cpscore.harness import MANIFEST
from cpscore.scoring import make_report

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cpscore_harness_smoke", ROOT / "scripts/harness_smoke.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class HarnessSmokeControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.material = self.root / "statement.md"
        self.material.write_text("Print a+b.\n")
        self.project = self.root / "new-run"

    def run_controller(self, mutate=None, *, available=True, scope="statement"):
        def stub_invocation(command, project, timeout):
            # A controlled fixture exercises the controller only. It never runs
            # a CLI or establishes model invocation or review accuracy.
            (project / "review.json").write_text(json.dumps(make_report([scope])))
            (project / "scored.json").write_text('{"overall":{"score":10,"qualification":"pass"}}')
            if mutate:
                mutate(project)
            return 0
        output = io.StringIO()
        with patch.object(smoke.shutil, "which", return_value="/stub/codex" if available else None), \
             patch.object(smoke, "_cli_version", return_value={"status":"recorded","stdout":"stub version"}), \
             patch.object(smoke, "_invoke", side_effect=stub_invocation) as invocation, redirect_stdout(output):
            code = smoke.main(["--harness", "codex", "--skill", "statement", "--material", str(self.material),
                               "--model", "explicit-stub-model", "--output-dir", str(self.project)])
        return code, json.loads(output.getvalue()), invocation.call_count

    def test_unavailable_never_claims_invocation(self):
        code, result, count = self.run_controller(available=False)
        self.assertEqual((code, count, result["status"]), (2, 0, "unavailable"))
        self.assertFalse((self.project / "verified-scored.json").exists())

    def test_rescores_raw_review_and_records_command_and_protection(self):
        code, result, count = self.run_controller()
        self.assertEqual((code, count, result["status"]), (0, 1, "invoked_and_validated"))
        self.assertEqual(result["assessment"], {"score":None,"tier":"undetermined","recommendable":None,"qualification":"undetermined","completion":"incomplete"})
        self.assertEqual(result["ai_accuracy"], "not_established")
        self.assertEqual(result["command"][0], "/stub/codex")
        self.assertIn(MANIFEST, result["protected_files"])
        self.assertIn(".cpscore/runtime/cpscore/scoring.py", result["protected_files"])
        verified = json.loads((self.project / "verified-scored.json").read_text())
        self.assertIsNone(verified["overall"]["score"])
        self.assertEqual(self.material.read_text(), "Print a+b.\n")

    def test_deleted_material_becomes_recorded_invalid_output(self):
        code, result, _ = self.run_controller(lambda p: (p / "material-0-statement.md").unlink())
        self.assertEqual((code, result["status"]), (2, "invalid_output"))
        self.assertIn("protected file", result["detail"])
        self.assertEqual(json.loads((self.project / "run.json").read_text())["status"], "invalid_output")

    def test_modified_runtime_and_manifest_cannot_be_accepted(self):
        for name in (".cpscore/runtime/cpscore/scoring.py", MANIFEST):
            with self.subTest(name=name):
                self.project = self.root / ("run-" + Path(name).name)
                code, result, _ = self.run_controller(lambda p: (p / name).write_text("altered"))
                self.assertEqual((code, result["status"]), (2, "invalid_output"))
                self.assertIn(name, result["detail"])

    def test_reserved_outputs_never_follow_external_symlinks(self):
        victim = self.root / "outside.txt"
        victim.write_text("preserve original")
        for name in ("run.json", "verified-scored.json"):
            with self.subTest(name=name):
                self.project = self.root / ("run-" + name)
                code, result, _ = self.run_controller(lambda p: (p / name).symlink_to(victim))
                self.assertEqual((code, result["status"]), (2, "invalid_output"))
                self.assertEqual(victim.read_text(), "preserve original")

    def test_symlinked_report_and_wrong_scope_are_invalid(self):
        outside = self.root / "outside-review.json"
        outside.write_text(json.dumps(make_report(["statement"])))
        def replace_report(project):
            (project / "review.json").unlink()
            (project / "review.json").symlink_to(outside)
        code, result, _ = self.run_controller(replace_report)
        self.assertEqual((code, result["status"]), (2, "invalid_output"))
        self.project = self.root / "wrong-scope"
        code, result, _ = self.run_controller(scope="solution")
        self.assertEqual((code, result["status"]), (2, "invalid_output"))
        self.assertIn("scope", result["detail"].lower())

    @unittest.skipUnless(os.name == "posix", "process-group termination uses POSIX signals")
    def test_timeout_stops_cli_descendants(self):
        self.project.mkdir()
        marker = self.root / "child-finished"
        child = "import sys,time; from pathlib import Path; time.sleep(1.2); Path(sys.argv[1]).write_text('escaped')"
        driver = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); time.sleep(20)"
        with self.assertRaises(subprocess.TimeoutExpired):
            smoke._invoke([sys.executable, "-c", driver, child, str(marker)], self.project, 0.2)
        time.sleep(1.3)
        self.assertFalse(marker.exists(), "timed-out harness must not leave a running child")


if __name__ == "__main__":
    unittest.main()
