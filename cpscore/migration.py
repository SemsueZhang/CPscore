"""Conservative v1/v2 import: archive the source and require v3 reassessment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .schema import OBJECTS, ReportValidationError, load_schema, loads_json, require_valid_report, validate_schema
from .scoring import make_report
from .rubric import SCHEMA_VERSION


def migrate_document(document: Any) -> dict[str, Any]:
    """Validate the legacy review structure, then require a fresh adjudication.

    Old derived scores are archived, not authenticated or reinterpreted.
    """
    if not isinstance(document, dict) or document.get("schema_version") not in ("1.0", "2.0"):
        raise ValueError("migration requires an explicit protocol 1.0 or 2.0 document")
    version = document["schema_version"]
    old = document.get("review", document)
    if not isinstance(old, dict) or old.get("schema_version") != version:
        raise ValueError("wrapper and review protocol versions must match")
    issues = validate_schema(old, load_schema("legacy-report" if version == "1.0" else "report-v2"))
    if issues:
        raise ReportValidationError(issues)
    report = make_report(old["scope"], review_id=old["review_id"],
                         snapshot_id=old["snapshot"]["id"] + "-v3")
    report["snapshot"].update(revision=old["snapshot"]["revision"] + 1,
                              supersedes=old["snapshot"]["id"])
    for name in OBJECTS:
        report["objects"][name]["artifact_version"] = old["objects"][name]["artifact_version"]
        if name not in old["scope"]:
            continue
        for item in report["objects"][name]["coverage"].values():
            item.update(status="blocked", reason=f"Protocol {version} review requires reassessment under v3 quality and severity rules; consult the preserved legacy source.")
    require_valid_report(report)
    return report


def migrate_file(source: str, destination: str) -> dict[str, Any]:
    """Write a new report and exact legacy bytes, refusing all overwrites."""
    src, dst = Path(source), Path(destination)
    raw = src.read_bytes()
    old = loads_json(raw.decode("utf-8"))
    report = migrate_document(old)
    metadata = {
        "migration_version": "2.0", "source_protocol": old["schema_version"], "target_protocol": SCHEMA_VERSION,
        "source_path": str(src.resolve()), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "legacy_snapshot": old.get("review", old)["snapshot"],
        "legacy_archive": dst.name + ".legacy.json", "requires_reassessment": True,
        "legacy_check": "review_structure_only; old derived scores are not authenticated",
    }
    encode = lambda value: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    outputs = {dst: encode(report), Path(str(dst) + ".legacy.json"): raw,
               Path(str(dst) + ".migration.json"): encode(metadata)}
    if any(path.exists() or path.is_symlink() for path in outputs):
        raise ValueError("migration refuses to overwrite any report, archive, or metadata file")
    created = []
    try:
        for path, content in outputs.items():
            with path.open("xb") as stream:
                created.append(path)
                stream.write(content)
    except OSError:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return metadata
