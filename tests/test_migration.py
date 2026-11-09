from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from cpscore.migration import migrate_document, migrate_file
from cpscore.schema import ReportValidationError, validate_report
from cpscore.scoring import score_report

LEGACY = Path(__file__).parent / "history/v1-codex-statement.json"


class MigrationTests(unittest.TestCase):
    def test_real_historical_output_remains_original_and_requires_reassessment(self):
        self.assertEqual(hashlib.sha256(LEGACY.read_bytes()).hexdigest(), "847be980773b61bf50d7514e50b9c654564a71210ea6aa42ddf99a9f154b339f")
        old = json.loads(LEGACY.read_text(encoding="utf-8"))
        before = deepcopy(old)
        new = migrate_document(old)
        self.assertEqual(old, before)
        self.assertEqual(validate_report(new), [])
        result = score_report(new)
        self.assertEqual(result["overall"]["qualification"], "undetermined")
        self.assertEqual(result["overall"]["completion"], "incomplete")
        self.assertEqual(new["objects"]["statement"]["findings"], [])
        self.assertTrue(all(c["status"] == "blocked" for c in new["objects"]["statement"]["coverage"].values()))
        self.assertEqual(old["objects"]["statement"]["findings"][0]["severity"], "minor")

    def test_new_adjudication_does_not_rewrite_old_model_output(self):
        old = json.loads(LEGACY.read_text(encoding="utf-8"))
        new = migrate_document(old)
        f = deepcopy(old["objects"]["statement"]["findings"][0])
        f.update(severity="fatal", rule_id="incorrect_sample")
        f["description"] = "v2 human re-adjudication: the formal output 4 contradicts 1+2=3; ease of repair does not reduce severity."
        for e in f["evidence"]:
            e["snapshot_id"] = new["snapshot"]["id"]
        new["objects"]["statement"]["findings"].append(f)
        result = score_report(new)
        self.assertEqual(result["overall"]["score"], 0)
        self.assertEqual(result["overall"]["qualification"], "fail")
        self.assertEqual(result["overall"]["completion"], "incomplete")

    def test_archive_exact_bytes_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "new.json"
            meta = migrate_file(str(LEGACY), str(dst))
            archive = Path(str(dst) + ".legacy.json")
            self.assertEqual(archive.read_bytes(), LEGACY.read_bytes())
            self.assertEqual(meta["source_sha256"], hashlib.sha256(LEGACY.read_bytes()).hexdigest())
            self.assertEqual(validate_report(json.loads(dst.read_text(encoding="utf-8"))), [])
            with self.assertRaises(ValueError):
                migrate_file(str(LEGACY), str(dst))
            with self.assertRaises(ValueError):
                migrate_file(str(LEGACY), str(LEGACY))

    def test_preserves_versions_and_keeps_out_of_scope_unchecked(self):
        old = json.loads(LEGACY.read_text(encoding="utf-8"))
        old["objects"]["solution"]["artifact_version"] = "unreviewed-program-v7"
        new = migrate_document(old)
        self.assertEqual(new["objects"]["solution"]["artifact_version"], "unreviewed-program-v7")
        self.assertTrue(all(c["status"] == "unchecked" for c in new["objects"]["solution"]["coverage"].values()))
        self.assertIsNone(score_report(new)["overall"]["score"])

    def test_sidecar_collisions_prevent_all_writes(self):
        for suffix in (".legacy.json", ".migration.json"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                dst = Path(tmp) / "new.json"
                sidecar = Path(str(dst) + suffix)
                sidecar.write_text("preserve existing")
                with self.assertRaises(ValueError):
                    migrate_file(str(LEGACY), str(dst))
                self.assertFalse(dst.exists())
                self.assertEqual(sidecar.read_text(encoding="utf-8"), "preserve existing")

    def test_metadata_carries_legacy_snapshot_and_strict_source_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "new.json"
            meta = migrate_file(str(LEGACY), str(dst))
            self.assertEqual(meta["legacy_snapshot"], json.loads(LEGACY.read_text(encoding="utf-8"))["snapshot"])
            malformed = Path(tmp) / "duplicate.json"
            malformed.write_text('{"schema_version":"1.0","schema_version":"1.0"}')
            with self.assertRaises(ValueError):
                migrate_file(str(malformed), str(Path(tmp) / "bad.json"))
            self.assertFalse((Path(tmp) / "bad.json").exists())

    def test_reject_bad_version_and_malformed_old_input(self):
        with self.assertRaises(ValueError):
            migrate_document({"schema_version": "2.0"})
        with self.assertRaises(ReportValidationError):
            migrate_document({"schema_version": "1.0"})

    def test_old_scored_wrapper_is_imported_without_authenticating_old_scores(self):
        old = json.loads(LEGACY.read_text(encoding="utf-8"))
        new = migrate_document({"schema_version": "1.0", "review": old,
                                "overall": {"score": 10, "status": "pass"}})
        self.assertEqual(score_report(new)["overall"]["qualification"], "undetermined")


class ArchivedInvocationTests(unittest.TestCase):
    def test_archived_real_outputs_are_intact_and_still_score_consistently(self):
        """Replay saved evidence only; this unit test does not call a model."""
        with zipfile.ZipFile(LEGACY.parent / "codex-v2.zip") as archive:
            index = json.loads(archive.read("index.json"))
            self.assertEqual(set(index["runs"]), {"statement", "solution", "editorial"})
            for name, record in index["runs"].items():
                for item in record["files"].values():
                    raw = archive.read(item["archive_path"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"])
                def read(relative):
                    return archive.read(record["files"][relative]["archive_path"])
                report = json.loads(read("review.json"))
                run = json.loads(read("run.json"))
                self.assertEqual(run["status"], "invoked_and_validated")
                self.assertEqual(run["exit_code"], 0)
                self.assertEqual(report["scope"], [name])
                self.assertEqual(validate_report(report), [])
                result = score_report(report)["overall"]
                for key, expected in record["human_verdict"].items():
                    self.assertEqual(result[key], expected)
                for material in run["materials"]:
                    self.assertEqual(hashlib.sha256(read(material["file"])).hexdigest(), material["sha256"])


if __name__ == "__main__":
    unittest.main()
