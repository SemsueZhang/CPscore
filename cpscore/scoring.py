"""The only implementation of CPScore's scoring rules."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .schema import OBJECTS, require_valid_report

INITIAL_SCORE = 10
PASS_THRESHOLD = 6
PENALTIES = {"fatal": 10, "minor": 1}


def make_report(scope: Iterable[str] | None = None, *, review_id: str = "review-1", snapshot_id: str = "snapshot-1") -> dict[str, Any]:
    """Create an unreviewed snapshot; writing findings never implies review."""
    report = {
        "schema_version": "1.0",
        "review_id": review_id,
        "snapshot": {"id": snapshot_id, "revision": 1, "supersedes": None},
        "scope": list(OBJECTS if scope is None else scope),
        "objects": {name: {"review_status": "not_reviewed", "artifact_version": "v1", "findings": []} for name in OBJECTS},
        "validations": [],
    }
    require_valid_report(report)
    return report


def _root_causes(records: list[tuple[str, int, dict[str, Any]]]) -> list[dict[str, Any]]:
    roots: dict[str, list[tuple[str, int, dict[str, Any]]]] = {}
    for record in records:
        roots.setdefault(record[2]["root_cause_id"], []).append(record)
    aggregates = []
    for root in sorted(roots):
        occurrences = roots[root]
        finding = occurrences[0][2]
        aggregates.append({
            "root_cause_id": root,
            "severity": finding["severity"],
            "status": finding["status"],
            "points": PENALTIES[finding["severity"]] if finding["status"] == "confirmed" else 0,
            "finding_ids": sorted(record[2]["id"] for record in occurrences),
            "affected_objects": [name for name in OBJECTS if any(record[0] == name for record in occurrences)],
            "evidence_refs": [
                {"object": obj, "finding_id": finding["id"], "evidence_index": evidence_index}
                for obj, _, finding in sorted(occurrences, key=lambda item: (OBJECTS.index(item[0]), item[2]["id"]))
                for evidence_index in range(len(finding["evidence"]))
            ],
        })
    return aggregates


def _assessment(records: list[tuple[str, int, dict[str, Any]]], *, reviewed: bool, incomplete: bool = False) -> dict[str, Any]:
    deductions = [{key: value for key, value in root.items() if key != "status"} for root in _root_causes(records) if root["status"] == "confirmed"]
    pending = sorted(finding["id"] for _, _, finding in records if finding["status"] == "suspected" and finding["severity"] == "fatal")
    total = sum(deduction["points"] for deduction in deductions)
    score = max(0, INITIAL_SCORE - total) if reviewed else None
    if not reviewed:
        status = "pending" if incomplete else "not_reviewed"
    elif pending or incomplete:
        status = "pending"
    elif score < PASS_THRESHOLD:
        status = "fail"
    else:
        status = "pass"
    return {
        "status": status,
        "score": score,
        "qualified": True if status == "pass" else False if status == "fail" else None,
        "initial_score": INITIAL_SCORE,
        "pass_threshold": PASS_THRESHOLD,
        "total_penalty": total,
        "deductions": deductions,
        "pending_finding_ids": pending,
        "suspected_finding_ids": sorted(finding["id"] for _, _, finding in records if finding["status"] == "suspected"),
        "resolved_finding_ids": sorted(finding["id"] for _, _, finding in records if finding["status"] == "resolved"),
    }


def score_report(report: dict[str, Any]) -> dict[str, Any]:
    """Validate and score a report; never trusts model-provided scores.

    Explicit root_cause_id is the only deduplication key. A root is deducted
    once per affected object and once in the overall score, never averaged.
    """
    require_valid_report(report)
    object_scores: dict[str, Any] = {}
    all_records = []
    reviewed_objects = []
    unreviewed_objects = []
    for name in OBJECTS:
        artifact = report["objects"][name]
        reviewed = artifact["review_status"] == "reviewed"
        records = [(name, i, finding) for i, finding in enumerate(artifact["findings"])]
        object_scores[name] = _assessment(records, reviewed=reviewed)
        if name in report["scope"]:
            if reviewed:
                reviewed_objects.append(name)
                all_records.extend(records)
            else:
                unreviewed_objects.append(name)
    overall = _assessment(all_records, reviewed=bool(reviewed_objects), incomplete=bool(unreviewed_objects))
    overall.update({
        "scope": list(report["scope"]),
        "reviewed_objects": reviewed_objects,
        "unreviewed_objects": unreviewed_objects,
        "completion": "pending" if unreviewed_objects else "complete",
        "aggregation": "unique_root_causes_across_reviewed_objects",
    })
    return {"schema_version": "1.0", "review": deepcopy(report), "root_causes": _root_causes(all_records), "objects": object_scores, "overall": overall}
