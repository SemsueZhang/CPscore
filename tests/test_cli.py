import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_scoring import finding, reviewed

ROOT = Path(__file__).resolve().parents[1]


def cli(*arguments, input=None):
    return subprocess.run([sys.executable,"-m","cpscore",*arguments], cwd=ROOT, input=input, text=True, capture_output=True, timeout=15)


class CliTests(unittest.TestCase):
    def test_init_validate_and_pending_score(self):
        init = cli("init-report", "--scope", "solution")
        self.assertEqual(init.returncode, 0, init.stderr)
        report = json.loads(init.stdout)
        self.assertEqual(report["scope"], ["solution"])
        valid = cli("validate", "-", input=init.stdout)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        scored = cli("score", "-", "--format", "json", input=init.stdout)
        self.assertEqual(scored.returncode, 0, scored.stderr)
        self.assertEqual(json.loads(scored.stdout)["overall"]["status"], "pending")

    def test_json_markdown_and_file_output(self):
        report = reviewed(); report["objects"]["solution"]["findings"]=[finding()]
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"review.json"; source.write_text(json.dumps(report))
            target = Path(temp)/"review.md"
            result = cli("score", str(source), "--output", str(target))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Overall score: **9/10**", target.read_text())
            scored = cli("score", str(source), "--format", "json")
            self.assertEqual(scored.returncode, 0, scored.stderr)
            valid = cli("validate", "-", "--scored", input=scored.stdout)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            changed = json.loads(scored.stdout); changed["overall"]["score"]=10
            rejected = cli("validate", "-", "--scored", input=json.dumps(changed))
            self.assertEqual(rejected.returncode, 2)

    def test_invalid_inputs_are_structured_and_nonzero(self):
        for source in ('{"score":10}', '{"a":1,"a":2}', '{"a":NaN}', '{broken'):
            result=cli("validate","-",input=source)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout or result.stderr)["valid"])

    def test_schema_and_core_commands_do_not_import_integrations(self):
        result=cli("schema")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["title"], "CPScore review input 1.0")
        script = "import sys; from cpscore.cli import main; main(['init-report']); assert 'cpscore.validation' not in sys.modules; assert 'cpscore.harness' not in sys.modules"
        result=subprocess.run([sys.executable,"-c",script],cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__ == "__main__":
    unittest.main()
