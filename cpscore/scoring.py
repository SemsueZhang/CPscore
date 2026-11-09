"""The only implementation of CPScore's deterministic scoring rules."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .rubric import (
    COMPLETE_COVERAGE_STATUSES, COVERAGE_ITEMS, INITIAL_SCORE, OBJECTS,
    PASS_THRESHOLD, PENALTIES, SCHEMA_VERSION, STATUS_PRIORITY,
)
from .schema import require_valid_report


def make_report(scope: Iterable[str] | None = None, *, review_id: str = "review-1", snapshot_id: str = "snapshot-1") -> dict[str, Any]:
    """Create an unchecked snapshot; writing findings never completes coverage."""
    report = {
        "schema_version": SCHEMA_VERSION,
        "review_id": review_id,
        "snapshot": {"id": snapshot_id, "revision": 1, "supersedes": None},
        "scope": list(OBJECTS if scope is None else scope),
        "objects": {
            name: {
                "artifact_version": "v1",
                "coverage": {
                    item: {"status": "unchecked", "evidence": [], "reason": None}
                    for item in COVERAGE_ITEMS[name]
                },
                "findings": [],
            }
            for name in OBJECTS
        },
        "validations": [],
    }
    require_valid_report(report)
    return report


def _evidence_refs(records: list[tuple[str, int, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {"object": obj, "finding_id": finding["id"], "evidence_index": index}
        for obj, _, finding in sorted(records, key=lambda item: (OBJECTS.index(item[0]), item[2]["id"]))
        for index in range(len(finding["evidence"]))
    ]


def _root_causes(records: list[tuple[str, int, dict[str, Any]]]) -> list[dict[str, Any]]:
    roots: dict[str, list[tuple[str, int, dict[str, Any]]]] = {}
    for record in records:
        roots.setdefault(record[2]["root_cause_id"], []).append(record)
    aggregates = []
    for root in sorted(roots):
        occurrences = roots[root]
        severity = occurrences[0][2]["severity"]
        status = max((record[2]["status"] for record in occurrences), key=STATUS_PRIORITY.__getitem__)
        local_states = []
        for obj in OBJECTS:
            local = [record for record in occurrences if record[0] == obj]
            if not local:
                continue
            local_status = local[0][2]["status"]
            local_states.append({
                "object": obj,
                "status": local_status,
                "points": PENALTIES[severity] if local_status == "confirmed" else 0,
                "finding_ids": sorted(record[2]["id"] for record in local),
                "evidence_refs": _evidence_refs(local),
            })
        aggregates.append({
            "root_cause_id": root,
            "severity": severity,
            "status": status,
            "points": PENALTIES[severity] if status == "confirmed" else 0,
            "finding_ids": sorted(record[2]["id"] for record in occurrences),
            "affected_objects": [state["object"] for state in local_states],
            "local_states": local_states,
            "evidence_refs": _evidence_refs(occurrences),
        })
    return aggregates


def _assessment(records: list[tuple[str, int, dict[str, Any]]], *, has_checks: bool, complete: bool) -> dict[str, Any]:
    roots = _root_causes(records)
    deductions = [root for root in roots if root["status"] == "confirmed"]
    total = sum(deduction["points"] for deduction in deductions)
    score = max(0, INITIAL_SCORE - total) if has_checks or records else None
    pending_roots = {root["root_cause_id"] for root in roots if root["status"] == "suspected" and root["severity"] == "fatal"}
    pending = sorted(finding["id"] for _, _, finding in records if finding["root_cause_id"] in pending_roots and finding["status"] == "suspected")
    if score is not None and score < PASS_THRESHOLD:
        qualification = "fail"
    elif score is not None and complete and not pending:
        qualification = "pass"
    else:
        qualification = "undetermined"
    return {
        "qualification": qualification,
        "completion": "complete" if complete else "incomplete",
        "score": score,
        "initial_score": INITIAL_SCORE,
        "pass_threshold": PASS_THRESHOLD,
        "total_penalty": total,
        "deductions": deductions,
        "pending_finding_ids": pending,
        "suspected_finding_ids": sorted(finding["id"] for _, _, finding in records if finding["status"] == "suspected"),
        "resolved_finding_ids": sorted(finding["id"] for _, _, finding in records if finding["status"] == "resolved"),
    }


def score_report(report: dict[str, Any]) -> dict[str, Any]:
    """Validate and score without trusting model-provided scores.

    Explicit root_cause_id is the sole deduplication key. Each object deducts
    only locally confirmed roots. Overall roots use confirmed > suspected >
    resolved across in-scope objects and deduct once, never average.
    """
    require_valid_report(report)
    object_scores: dict[str, Any] = {}
    all_records = []
    completed_objects = []
    incomplete_objects = []
    any_checks = False
    for name in OBJECTS:
        artifact = report["objects"][name]
        states = [entry["status"] for entry in artifact["coverage"].values()]
        complete = all(state in COMPLETE_COVERAGE_STATUSES for state in states)
        has_checks = any(state in COMPLETE_COVERAGE_STATUSES for state in states)
        records = [(name, i, finding) for i, finding in enumerate(artifact["findings"])]
        object_scores[name] = _assessment(records, has_checks=has_checks, complete=complete)
        if name in report["scope"]:
            (completed_objects if complete else incomplete_objects).append(name)
            any_checks |= has_checks
            all_records.extend(records)
    overall = _assessment(all_records, has_checks=any_checks, complete=not incomplete_objects)
    overall.update({
        "scope": list(report["scope"]),
        "completed_objects": completed_objects,
        "incomplete_objects": incomplete_objects,
        "aggregation": "unique_root_causes_across_in_scope_objects",
    })
    return {"schema_version": SCHEMA_VERSION, "review": deepcopy(report), "root_causes": _root_causes(all_records), "objects": object_scores, "overall": overall}
