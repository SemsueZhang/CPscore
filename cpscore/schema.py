"""Strict validation of the *documented subset* used by our JSON Schemas.

This is not a general JSON Schema implementation. The published schemas describe
structural constraints; CPScore additionally checks cross-record semantics in
``validate_report``. Every error identifies that layer in its ``code``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
import math
import re
from typing import Any

from .rubric import OBJECTS, RULE_SEVERITIES


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: str = "schema"

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message, "code": self.code}


class ReportValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in issues))


class SchemaSubsetError(ValueError):
    """The supplied schema uses unsupported keywords, not an invalid report."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number is not allowed: {value}")
    return number


def loads_json(text: str) -> Any:
    """Read strict JSON, rejecting repeated keys and NaN/Infinity/overflow."""
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)


def load_schema(name: str = "report") -> dict[str, Any]:
    if name not in {"report", "scored-report", "legacy-report", "report-v2"}:
        raise ValueError(f"unknown schema: {name}")
    return loads_json(files("cpscore").joinpath("schemas", f"{name}.schema.json").read_text(encoding="utf-8"))


_KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "$comment", "title", "description",
    "type", "const", "enum", "properties", "required", "additionalProperties",
    "items", "minItems", "maxItems", "uniqueItems", "minLength", "pattern",
    "minimum", "maximum", "anyOf", "oneOf", "allOf", "if", "then", "else",
}


def _is_type(value: Any, kind: str) -> bool:
    return {
        "object": lambda: isinstance(value, dict) and all(isinstance(k, str) for k in value),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and math.isfinite(value) and value.is_integer()),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool) and (not isinstance(value, float) or math.isfinite(value)),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }[kind]()


def _equal(a: Any, b: Any) -> bool:
    # JSON equality does not consider true and 1 equal.
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[key], b[key]) for key in a)
    return a == b


def _reference(ref: str, root: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    name, marker, fragment = ref.partition("#")
    target_root = load_schema(name.removesuffix(".schema.json")) if name else root
    target: Any = target_root
    if marker and fragment:
        if not fragment.startswith("/"):
            raise SchemaSubsetError(f"unsupported reference: {ref}")
        for key in fragment[1:].split("/"):
            target = target[key.replace("~1", "/").replace("~0", "~")]
    return target, target_root


def validate_schema(value: Any, schema: dict[str, Any], *, path: str = "$", root: dict[str, Any] | None = None) -> list[ValidationIssue]:
    """Validate the structural keyword subset used in ``schemas/`` only."""
    root = schema if root is None else root
    unknown = set(schema) - _KEYWORDS
    if unknown:
        raise SchemaSubsetError(f"unsupported schema keywords: {sorted(unknown)}")
    issues: list[ValidationIssue] = []

    def error(message: str, at: str = path) -> None:
        issues.append(ValidationIssue(at, message))

    if "$ref" in schema:
        target, target_root = _reference(schema["$ref"], root)
        issues.extend(validate_schema(value, target, path=path, root=target_root))
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, kind) for kind in kinds):
            error(f"expected {' or '.join(kinds)}")
            return issues
    if "const" in schema and not _equal(value, schema["const"]):
        error(f"expected constant {schema['const']!r}")
    if "enum" in schema and not any(_equal(value, option) for option in schema["enum"]):
        error(f"expected one of {schema['enum']!r}")
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            count = sum(not validate_schema(value, branch, path=path, root=root) for branch in schema[keyword])
            if (keyword == "anyOf" and count == 0) or (keyword == "oneOf" and count != 1):
                error(f"must match {'at least one' if keyword == 'anyOf' else 'exactly one'} {keyword} branch")
    for branch in schema.get("allOf", []):
        issues.extend(validate_schema(value, branch, path=path, root=root))
    if "if" in schema:
        matches = not validate_schema(value, schema["if"], path=path, root=root)
        branch = schema.get("then" if matches else "else")
        if branch is not None:
            issues.extend(validate_schema(value, branch, path=path, root=root))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                error("required field is missing", f"{path}.{key}")
        for key, item in value.items():
            if key in properties:
                issues.extend(validate_schema(item, properties[key], path=f"{path}.{key}", root=root))
            elif schema.get("additionalProperties") is False:
                error("unknown field", f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            error(f"expected at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            error(f"expected at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            for index, item in enumerate(value):
                if any(_equal(item, other) for other in value[:index]):
                    error("duplicate array item", f"{path}[{index}]")
        if "items" in schema:
            for index, item in enumerate(value):
                issues.extend(validate_schema(item, schema["items"], path=f"{path}[{index}]", root=root))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            error(f"expected at least {schema['minLength']} characters")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            error(f"does not match pattern {schema['pattern']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            error("non-finite number is not allowed")
        if "minimum" in schema and value < schema["minimum"]:
            error(f"must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            error(f"must be at most {schema['maximum']}")
    return issues


def validate_report(report: Any) -> list[ValidationIssue]:
    """Check published structural schema, then CPScore's cross-record rules."""
    issues = validate_schema(report, load_schema())
    if issues:
        return issues

    def error(path: str, message: str) -> None:
        issues.append(ValidationIssue(path, message, "semantic"))

    snapshot = report["snapshot"]
    if snapshot["supersedes"] == snapshot["id"]:
        error("$.snapshot.supersedes", "a snapshot cannot supersede itself")
    if snapshot["revision"] == 1 and snapshot["supersedes"] is not None:
        error("$.snapshot.supersedes", "revision 1 must not supersede another snapshot")
    if snapshot["revision"] > 1 and snapshot["supersedes"] is None:
        error("$.snapshot.supersedes", "a re-review must identify the preceding snapshot")

    def check_evidence(evidence: dict[str, Any], path: str, artifact: dict[str, Any]) -> None:
        if evidence["snapshot_id"] != snapshot["id"]:
            error(f"{path}.snapshot_id", "stale evidence: snapshot does not match current review")
        if evidence["artifact_version"] != artifact["artifact_version"]:
            error(f"{path}.artifact_version", "stale evidence: artifact version does not match current object")

    seen_ids: dict[str, str] = {}
    for obj in OBJECTS:
        artifact = report["objects"][obj]
        path = f"$.objects.{obj}"
        local_roots: dict[str, tuple[str, str]] = {}
        if obj not in report["scope"] and artifact["findings"]:
            error(f"{path}.findings", "an object outside scope cannot contain findings")
        for item, entry in artifact["coverage"].items():
            cp = f"{path}.coverage.{item}"
            if obj not in report["scope"] and entry["status"] != "unchecked":
                error(f"{cp}.status", "an object outside scope must have unchecked coverage")
            for ei, evidence in enumerate(entry["evidence"]):
                check_evidence(evidence, f"{cp}.evidence[{ei}]", artifact)
        for index, finding in enumerate(artifact["findings"]):
            fp = f"{path}.findings[{index}]"
            identifier = finding["id"]
            if identifier in seen_ids:
                error(f"{fp}.id", f"duplicate finding id, first used at {seen_ids[identifier]}")
            else:
                seen_ids[identifier] = fp
            expected_severity = RULE_SEVERITIES[finding["rule_id"]]
            allowed = (expected_severity,) if isinstance(expected_severity, str) else expected_severity
            if allowed is not None and finding["severity"] not in allowed:
                error(f"{fp}.severity", f"rule {finding['rule_id']!r} requires severity in {allowed!r}")
            root = finding["root_cause_id"]
            if root in local_roots and finding["status"] != local_roots[root][0]:
                error(f"{fp}.root_cause_id", f"conflicting local status for root cause {root!r}, first used at {local_roots[root][1]}")
            elif root not in local_roots:
                local_roots[root] = (finding["status"], fp)
            for ei, evidence in enumerate(finding["evidence"]):
                check_evidence(evidence, f"{fp}.evidence[{ei}]", artifact)
            repair = finding["repair"]
            if repair["status"] == "applied" and finding["status"] != "resolved":
                error(f"{fp}.repair.status", "applied repairs require a resolved finding and current verification evidence")
            if repair["status"] == "applied" and not repair["verification"]:
                error(f"{fp}.repair.verification", "applied repairs require verification steps")
    seen_checks: set[str] = set()
    for index, check in enumerate(report["validations"]):
        path = f"$.validations[{index}]"
        if check["id"] in seen_checks:
            error(f"{path}.id", "duplicate validation id")
        seen_checks.add(check["id"])
        if check["object"] not in report["scope"]:
            error(f"{path}.object", "validation object must be in scope")
        if check["status"] == "executed":
            if check["outcome"] is None or not check["evidence"]:
                error(path, "executed checks require an outcome and nonempty evidence")
            if check["reason"] is not None:
                error(f"{path}.reason", "executed checks must set reason to null")
        else:
            if check["outcome"] is not None or check["evidence"]:
                error(path, "unexecuted checks require null outcome and empty evidence")
            if check["reason"] is None:
                error(f"{path}.reason", "unexecuted checks require an explicit reason")
        for ei, evidence in enumerate(check["evidence"]):
            check_evidence(evidence, f"{path}.evidence[{ei}]", report["objects"][check["object"]])
    return issues


def require_valid_report(report: Any) -> None:
    issues = validate_report(report)
    if issues:
        raise ReportValidationError(issues)


def validate_scored_report(scored: Any) -> list[ValidationIssue]:
    issues = validate_schema(scored, load_schema("scored-report"))
    if issues:
        return issues
    issues = validate_report(scored["review"])
    if issues:
        return [ValidationIssue("$.review" + i.path[1:], i.message, i.code) for i in issues]
    from .scoring import score_report
    expected = score_report(scored["review"])
    if scored != expected:
        issues.append(ValidationIssue("$", "scores differ from deterministic recomputation", "semantic"))
    return issues
