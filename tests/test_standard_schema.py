"""Optional independent Draft 2020-12 checks; not a runtime dependency."""
from copy import deepcopy
import unittest

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
except ImportError:
    Draft202012Validator = None

from cpscore.schema import load_schema, validate_schema
from cpscore.scoring import make_report, score_report
from tests.test_scoring import finding, reviewed


@unittest.skipIf(Draft202012Validator is None, "optional QA dependency jsonschema is not installed")
class StandardSchemaTests(unittest.TestCase):
    def test_versioned_schema_ids_and_independent_validation(self):
        schemas = {name: load_schema(name) for name in ("report", "scored-report", "legacy-report", "report-v2")}
        self.assertEqual(len({s["$id"] for s in schemas.values()}), 4)
        registry = Registry()
        for schema in schemas.values():
            Draft202012Validator.check_schema(schema)
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        reports = [make_report(), reviewed()]
        for state in ("confirmed", "suspected", "resolved"):
            for severity in ("fatal", "major", "minor"):
                report = reviewed()
                report["objects"]["solution"]["findings"] = [finding(status=state, severity=severity)]
                reports.append(report)
        for report in reports:
            for name, value in (("report", report), ("scored-report", score_report(report))):
                validator = Draft202012Validator(schemas[name], registry=registry)
                self.assertTrue(validator.is_valid(value))
                candidates = [value]
                for version in ("1.0", None, True, 2):
                    changed = deepcopy(value)
                    changed["schema_version"] = version
                    candidates.append(changed)
                if name == "report":
                    for coverage in ({}, None, {"status": "reviewed"}):
                        changed = deepcopy(value)
                        changed["objects"]["solution"]["coverage"] = coverage
                        candidates.append(changed)
                else:
                    for score in (True, -1, 11, "10"):
                        changed = deepcopy(value)
                        changed["overall"]["score"] = score
                        candidates.append(changed)
                for candidate in candidates:
                    self.assertEqual(validator.is_valid(candidate), not validate_schema(candidate, schemas[name]))


if __name__ == "__main__":
    unittest.main()
