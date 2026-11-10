"""Human-readable reports rendered only from validated deterministic scores."""

from __future__ import annotations

import html
import json
from typing import Any

from .schema import ReportValidationError, validate_scored_report


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
    """Render quality decisions once, with evidence and local repair states."""
    issues = validate_scored_report(scored)
    if issues:
        raise ReportValidationError(issues)
    review, overall = scored["review"], scored["overall"]
    snapshot = review["snapshot"]

    def score_text(assessment):
        return "not available" if assessment["score"] is None else f"{assessment['score']}/10"

    def recommendation(assessment):
        value = assessment["recommendable"]
        return "undetermined" if value is None else str(value).lower()

    counts = overall["confirmed_counts"]
    lines = [
        "# CPscore 打分报告", "",
        f"Assessment: {_text(review['review_id'])} · protocol {scored['schema_version']}  ",
        f"Snapshot: {_text(snapshot['id'])}, revision {_text(snapshot['revision'])}, supersedes {_text(snapshot['supersedes'] or 'none')}  ",
        f"Requested scope: {', '.join(review['scope'])}", "",
        f"Overall score: **{score_text(overall)}** · tier: **{overall['tier']}**  ",
        f"Qualification: **{overall['qualification']}** · recommendable: **{recommendation(overall)}** · completion: **{overall['completion']}**  ",
        f"Confirmed independent roots: Fatal **{counts['fatal']}**, Major **{counts['major']}**, Minor **{counts['minor']}**.", "",
        "| Object | Completion | Score | Tier | Qualification | Recommendable | Fatal / Major / Minor |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for name in review["scope"]:
        assessment = scored["objects"][name]
        local_counts = assessment["confirmed_counts"]
        lines.append(f"| {name} | {assessment['completion']} | {score_text(assessment)} | {assessment['tier']} | {assessment['qualification']} | {recommendation(assessment)} | {local_counts['fatal']} / {local_counts['major']} / {local_counts['minor']} |")
    if overall["score"] is not None:
        lines += ["", f"max(0, 10 − {overall['total_penalty']}) = {overall['score']}"]
    lines += [
        "", "Fatal −10 · Major −3 · Minor −1; each confirmed root deducts once at its highest currently confirmed severity across scope. Suspected/resolved occurrences do not deduct. 9–10 is excellent, 6–8 acceptable, 0–5 unacceptable. Incomplete coverage or any suspected Fatal prevents a pass/recommendation unless confirmed deductions already establish failure.", "",
        "## Independent root causes", "",
        "| Root cause | Severity | Effective status | Local severity / status / deduction | Overall points | Findings |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for root in scored["root_causes"]:
        local = "; ".join(f"{state['object']}: {state['severity']} / {state['status']} / −{state['points']}" for state in root["local_states"])
        lines.append(f"| {_text(root['root_cause_id'])} | {root['severity']} | {root['status']} | {_text(local)} | {root['points']} | {_text(', '.join(root['finding_ids']))} |")
    if not scored["root_causes"]:
        lines.append("| — | — | — | — | 0 | No findings recorded |")
    lines += ["", "## Pending findings", ""]
    if overall["pending_finding_ids"]:
        lines.append(f"Pending fatal findings: {_text(', '.join(overall['pending_finding_ids']))}.")
    lines.append("Suspected findings: " + (_text(', '.join(overall['suspected_finding_ids'])) or "none") + ".")
    lines += ["", "## Findings and repair information", ""]
    for name in review["scope"]:
        for finding in review["objects"][name]["findings"]:
            lines += [
                f"### {_text(finding['id'])}: {_text(finding['title'])}", "",
                f"{name} · root {_text(finding['root_cause_id'])} · {finding['rule_id']} · **{finding['severity']} / {finding['status']}**", "",
                _text(finding["description"]), "",
            ]
            if finding.get("impact"):
                lines += [f"Quality impact / severity rationale: {_text(finding['impact'])}", ""]
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
    if not any(review["objects"][name]["findings"] for name in review["scope"]):
        lines += ["No findings recorded. Coverage determines whether this review is complete.", ""]
    lines += ["## Coverage", ""]
    for name in review["scope"]:
        lines += [f"### {name}", ""]
        for item, entry in review["objects"][name]["coverage"].items():
            lines.append(f"- {item}: **{entry['status']}**.")
            if entry["reason"] is not None:
                lines.append(f"  Reason: {_text(entry['reason'])}.")
            for evidence in entry["evidence"]:
                lines.append(f"  Evidence at {_text(evidence['location'])}: {_text(evidence['observation'])} (snapshot {_text(evidence['snapshot_id'])}, artifact {_text(evidence['artifact_version'])}).")
        lines.append("")
    lines += ["## Validation execution record", ""]
    if not review["validations"]:
        lines += ["No validation projects recorded. No test execution is claimed.", ""]
    for check in review["validations"]:
        lines += [f"### {_text(check['id'])}: {_text(check['name'])}", "", f"Object: {check['object']}; status: **{check['status']}**; outcome: {check['outcome'] or 'none'}."]
        if check["command"] is not None:
            lines.append(f"Command: {_text(check['command'])}")
        if check["reason"] is not None:
            lines.append(f"Reason unexecuted: {_text(check['reason'])}")
        for evidence in check["evidence"]:
            lines.append(f"- Evidence at {_text(evidence['location'])}: {_text(evidence['observation'])} (snapshot {_text(evidence['snapshot_id'])}, artifact {_text(evidence['artifact_version'])}).")
        lines.append("")
    lines += ["Finite tests and reported observations are evidence, not a general correctness proof.", ""]
    return "\n".join(lines)
