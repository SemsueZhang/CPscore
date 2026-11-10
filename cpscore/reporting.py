"""Human-readable reports rendered only from validated deterministic scores."""

from __future__ import annotations

import html
import json
from typing import Any

from .schema import OBJECTS, ReportValidationError, validate_scored_report


def _text(value: Any) -> str:
    text = html.escape(str(value), quote=False).replace("\\", "\\\\")
    for character in ("*", "_", "[", "]", "`", "|", "#"):
        text = text.replace(character, "\\" + character)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def render_json(scored: dict[str, Any]) -> str:
    issues = validate_scored_report(scored)
    if issues:
        raise ReportValidationError(issues)
    return json.dumps(scored, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def render_markdown(scored: dict[str, Any]) -> str:
    """Render the computed result, evidence, limitations and repair metadata."""
    issues = validate_scored_report(scored)
    if issues:
        raise ReportValidationError(issues)
    review, overall = scored["review"], scored["overall"]
    snapshot = review["snapshot"]
    lines = [
        "# CPscore 打分报告", "",
        f"Assessment: {_text(review['review_id'])}  ",
        f"Snapshot: {_text(snapshot['id'])}, revision {_text(snapshot['revision'])}, supersedes {_text(snapshot['supersedes'] or 'none')}  ",
        f"Requested scope: {', '.join(review['scope'])}  ",
        f"Completion: {overall['completion']}; qualification: **{overall['qualification']}**", "",
        "| Object | Scope | Completion | Score | Qualification |", "| --- | --- | --- | ---: | --- |",
    ]
    for name in OBJECTS:
        assessment = scored["objects"][name]
        score = "—" if assessment["score"] is None else f"{assessment['score']}/10"
        scope = "in scope" if name in review["scope"] else "outside scope"
        lines.append(f"| {name} | {scope} | {assessment['completion']} | {score} | {assessment['qualification']} |")
    score = "not available" if overall["score"] is None else f"{overall['score']}/10"
    lines += [
        "", f"Overall score: **{score}**. The overall score deducts each explicit root cause once across in-scope objects; it is not an average. Each object deducts only its locally confirmed roots.",
        "Confirmed fatal: −10. Confirmed minor: −1. Scores start at 10 and stop at 0. Passing requires at least 6, completed scope, and no suspected fatal issue.",
        "Suspected findings do not deduct points. Suspected fatal roots prevent passing. Confirmed deductions below 6 establish failure even when coverage is incomplete or another fatal issue is suspected. Resolved findings do not deduct points.", "",
        "## Independent root causes", "",
        "| Root cause | Severity | Effective status | Local states and deductions | Overall points | Findings |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for root in scored["root_causes"]:
        local = "; ".join(f"{state['object']}: {state['status']}, −{state['points']}" for state in root["local_states"])
        lines.append(f"| {_text(root['root_cause_id'])} | {root['severity']} | {root['status']} | {_text(local)} | {root['points']} | {_text(', '.join(root['finding_ids']))} |")
    if not scored["root_causes"]:
        lines.append("| — | — | — | — | 0 | No findings recorded |")
    lines += ["", "Effective root status uses confirmed > suspected > resolved across objects. Local states and evidence remain attached to each occurrence.", "", "## Coverage", ""]
    for name in OBJECTS:
        lines += [f"### {name}", ""]
        for item, entry in review["objects"][name]["coverage"].items():
            lines.append(f"- {item}: **{entry['status']}**.")
            if entry["reason"] is not None:
                lines.append(f"  Reason: {_text(entry['reason'])}.")
            for index, evidence in enumerate(entry["evidence"]):
                lines.append(f"  Evidence [{index}] at {_text(evidence['location'])}: {_text(evidence['observation'])} (snapshot {_text(evidence['snapshot_id'])}, artifact {_text(evidence['artifact_version'])}).")
        lines.append("")
    lines += ["## Deductions", ""]
    for name, assessment in [(name, scored["objects"][name]) for name in OBJECTS] + [("overall", overall)]:
        lines += [f"### {name}", ""]
        if assessment["score"] is None:
            lines += ["No completed coverage check or finding is recorded. No numerical score is assigned.", ""]
            continue
        lines += [f"max(0, 10 − {assessment['total_penalty']}) = {assessment['score']}", ""]
        for deduction in assessment["deductions"]:
            refs = ", ".join(f"{reference['object']}/{reference['finding_id']}/evidence[{reference['evidence_index']}]" for reference in deduction["evidence_refs"])
            lines.append(f"- {_text(deduction['root_cause_id'])}: −{deduction['points']} ({deduction['severity']}); findings: {_text(', '.join(deduction['finding_ids']))}; evidence: {_text(refs)}")
        if not assessment["deductions"]:
            lines.append("No confirmed deductions.")
        if assessment["pending_finding_ids"]:
            lines.append(f"Pending fatal findings: {_text(', '.join(assessment['pending_finding_ids']))}.")
        lines.append("")
    lines += ["## Findings and repair information", ""]
    for name in OBJECTS:
        for finding in review["objects"][name]["findings"]:
            lines += [
                f"### {_text(finding['id'])}: {_text(finding['title'])}", "",
                f"Object: {name}; root cause: {_text(finding['root_cause_id'])}; rule: {finding['rule_id']}; severity: {finding['severity']}; status: {finding['status']}.", "",
                _text(finding["description"]), "",
            ]
            if finding.get("evidence_gap") is not None:
                lines += [f"Evidence gap: {_text(finding['evidence_gap'])}", ""]
            for index, evidence in enumerate(finding["evidence"]):
                lines.append(f"- Evidence [{index}] at {_text(evidence['location'])}: {_text(evidence['observation'])} (snapshot {_text(evidence['snapshot_id'])}, artifact {_text(evidence['artifact_version'])}).")
            lines += ["", "Reproduction:", ""]
            lines += [f"{index}. {_text(step)}" for index, step in enumerate(finding["reproduction"]["steps"], 1)]
            lines += ["", f"Expected: {_text(finding['reproduction']['expected'])}  ", f"Observed: {_text(finding['reproduction']['actual'])}", ""]
            repair = finding["repair"]
            lines += [f"Repair suggestion: {_text(repair['suggestion'])}  ", f"Automatic repair possible: {str(repair['auto_fixable']).lower()}; repair status: {repair['status']}."]
            if repair["patch"] is not None:
                lines += ["", f"Patch: {_text(repair['patch'])}"]
            if repair["verification"]:
                lines += ["", "Repair verification:", ""] + [f"- {_text(step)}" for step in repair["verification"]]
            lines.append("")
    if not any(review["objects"][name]["findings"] for name in OBJECTS):
        lines += ["No findings recorded. This alone does not establish correctness.", ""]
    lines += ["## Validation execution record", ""]
    if not review["validations"]:
        lines += ["No validation projects recorded. No test execution is claimed.", ""]
    for check in review["validations"]:
        lines += [f"### {_text(check['id'])}: {_text(check['name'])}", "", f"Object: {check['object']}; status: **{check['status']}**; outcome: {check['outcome'] or 'none'}."]
        if check["command"] is not None:
            lines.append(f"Command: {_text(check['command'])}")
        if check["reason"] is not None:
            lines.append(f"Reason unexecuted: {_text(check['reason'])}")
        for index, evidence in enumerate(check["evidence"]):
            lines.append(f"- Evidence [{index}] at {_text(evidence['location'])}: {_text(evidence['observation'])} (snapshot {_text(evidence['snapshot_id'])}, artifact {_text(evidence['artifact_version'])}).")
        lines.append("")
    lines += ["Finite tests and reported observations are evidence, not a general correctness proof. Incomplete coverage and unexecuted checks are explicit above.", ""]
    return "\n".join(lines)
