"""Evaluate candidate programs on an immutable, already supplied batch suite.

Execution is evidence only. Whether a candidate is wrong and which points it
should earn remain review decisions, never inferred from its filename or AC.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .runner import DEFAULT_IMAGE, Limits, SandboxRunner
from .schema import loads_json
from .validation import CheckConfig, Comparison, _read_bounded, check_candidate


def _fields(value: Any, required: set[str], optional: set[str], label: str) -> None:
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        raise ValueError(f"{label}: required fields {sorted(required)}, optional fields {sorted(optional)}")


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IDs and mechanism descriptions must be nonempty strings")
    return value


def load_suite(path: Path) -> dict[str, Any]:
    suite = loads_json(path.read_text(encoding="utf-8"))
    _fields(suite, {"version", "cases", "candidates", "reference", "validator"},
            {"groups", "comparison"}, "suite")
    if suite["version"] != "1.0":
        raise ValueError("suite version must be 1.0")
    for key in ("cases", "candidates"):
        if not isinstance(suite[key], list) or not suite[key]:
            raise ValueError(f"{key} must be a nonempty array")
    base = path.resolve().parent

    def source(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("file paths must be nonempty strings")
        resolved = (base / value).resolve()
        if not resolved.is_file():
            raise ValueError(f"file not found: {resolved}")
        return str(resolved)

    case_ids = set()
    for case in suite["cases"]:
        _fields(case, {"id", "input", "answer"}, set(), "case")
        identifier = _identifier(case["id"])
        if identifier in case_ids:
            raise ValueError(f"duplicate case id: {identifier}")
        case_ids.add(identifier)
        for key in ("input", "answer"):
            case[key] = source(case[key])
    if "groups" not in suite:
        suite["groups"] = [{"id": c["id"], "points": 1, "cases": [c["id"]], "depends_on": []}
                           for c in suite["cases"]]
    if not isinstance(suite["groups"], list) or not suite["groups"]:
        raise ValueError("groups must be a nonempty array")
    groups = {}
    covered = set()
    for group in suite["groups"]:
        _fields(group, {"id", "points", "cases"}, {"depends_on"}, "group")
        identifier = _identifier(group["id"])
        if identifier in groups:
            raise ValueError(f"duplicate group id: {identifier}")
        if type(group["points"]) is not int or group["points"] <= 0:
            raise ValueError("group points must be positive integers")
        group.setdefault("depends_on", [])
        for key in ("cases", "depends_on"):
            entries = group[key]
            if not isinstance(entries, list) or any(not isinstance(x, str) for x in entries) or len(entries) != len(set(entries)):
                raise ValueError(f"group {key} must be an array of unique IDs")
        if not group["cases"] or not set(group["cases"]) <= case_ids:
            raise ValueError("group must name existing cases")
        covered.update(group["cases"])
        groups[identifier] = group
    if covered != case_ids:
        raise ValueError("every case must belong to a scoring group")
    visiting, visited = set(), set()

    def visit(identifier):
        if identifier not in groups or identifier in visiting:
            raise ValueError("unknown or cyclic group dependency")
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in groups[identifier]["depends_on"]:
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in groups:
        visit(identifier)
    candidate_ids = set()
    for candidate in suite["candidates"]:
        _fields(candidate, {"id", "source", "mechanism", "allowed_groups"}, set(), "candidate")
        identifier = _identifier(candidate["id"])
        _identifier(candidate["mechanism"])
        if identifier in candidate_ids:
            raise ValueError(f"duplicate candidate id: {identifier}")
        candidate_ids.add(identifier)
        allowed = candidate["allowed_groups"]
        if not isinstance(allowed, list) or any(not isinstance(x, str) for x in allowed) or len(allowed) != len(set(allowed)) or not set(allowed) <= groups.keys():
            raise ValueError("allowed_groups must explicitly list unique existing group IDs (or [])")
        candidate["source"] = source(candidate["source"])
    for key in ("reference", "validator"):
        suite[key] = source(suite[key])
    policy = suite.setdefault("comparison", {"mode": "exact"})
    _fields(policy, {"mode"}, {"abs_tolerance", "rel_tolerance"}, "comparison")
    try:
        Comparison(**policy)
    except (TypeError, OverflowError) as exc:
        raise ValueError("comparison tolerances must be finite numeric values") from exc
    return suite


def summarize_candidate(suite: dict[str, Any], candidate: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    observed = {"match", "sample_mismatch", "candidate_mismatch", "candidate_execution_failure"}
    cases = report.get("cases", [])
    complete = report["status"] == "completed" and len(cases) == len(suite["cases"]) and all(c["status"] in observed for c in cases)
    states = {c["id"]: (r["status"] == "match" if r["status"] in observed else None)
              for c, r in zip(suite["cases"], cases)}
    groups = {g["id"]: g for g in suite["groups"]}
    results = {}

    def group_state(identifier):
        if identifier not in results:
            group = groups[identifier]
            values = [states.get(case) for case in group["cases"]] + [group_state(d) for d in group["depends_on"]]
            results[identifier] = False if False in values else None if None in values else True
        return results[identifier]

    for identifier in groups:
        group_state(identifier)
    earned = [g for g in groups if results[g] is True]
    unexpected = [g for g in earned if g not in candidate["allowed_groups"]]
    total = sum(g["points"] for g in groups.values())
    matched = sum(value is True for value in states.values())
    return {
        "id": candidate["id"], "mechanism": candidate["mechanism"],
        "execution_status": report["status"], "complete": complete,
        "case_counts": report.get("counts", {}), "matched_cases": matched,
        "total_cases": len(suite["cases"]),
        "pass_fraction": matched / len(suite["cases"]) if complete else None,
        "all_cases_passed": matched == len(suite["cases"]) if complete else None,
        "group_states": results, "earned_groups": earned,
        "allowed_groups": candidate["allowed_groups"], "unexpected_groups": unexpected,
        "observed_points": sum(groups[g]["points"] for g in earned) if complete else None,
        "unexpected_points": sum(groups[g]["points"] for g in unexpected) if complete else None,
        "total_points": total,
        "review_required": "Confirm wrongness independently, allowed partial credit, mechanism severity and judge/resource fidelity before any deduction.",
    }


def evaluate_suite(path: Path, output_dir: Path, *, engine: str = "auto", image: str = DEFAULT_IMAGE,
                   limits: Limits | None = None, compile_seconds: float = 30.0, runner=None) -> dict[str, Any]:
    """Snapshot every file before execution; never generate or replace suite data."""
    suite = load_suite(path)
    if not math.isfinite(compile_seconds) or compile_seconds <= 0:
        raise ValueError("compile_seconds must be finite and positive")
    # Read everything before creating output; duplicate content/source paths are preserved once.
    paths = {suite["reference"], suite["validator"]}
    paths.update(c["source"] for c in suite["candidates"])
    paths.update(c[k] for c in suite["cases"] for k in ("input", "answer"))
    raw = {p: _read_bounded(Path(p)) for p in sorted(paths)}
    output_dir.mkdir(parents=True, exist_ok=False)
    frozen = output_dir / "frozen"
    frozen.mkdir()
    records, copies = [], {}
    for index, (original, data) in enumerate(raw.items()):
        name = f"{index:04d}{Path(original).suffix}"
        target = frozen / name
        target.write_bytes(data)
        copies[original] = str(target.resolve())
        records.append({"original": original, "frozen": "frozen/" + name,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    for key in ("reference", "validator"):
        suite[key] = copies[suite[key]]
    for candidate in suite["candidates"]:
        candidate["source"] = copies[candidate["source"]]
    for case in suite["cases"]:
        for key in ("input", "answer"):
            case[key] = copies[case[key]]
    limits = limits or Limits()
    frozen_suite = json.loads(json.dumps(suite))
    # The saved manifest relocates with the output directory.
    for key in ("reference", "validator"):
        frozen_suite[key] = str(Path(frozen_suite[key]).relative_to(output_dir.resolve()))
    for candidate in frozen_suite["candidates"]:
        candidate["source"] = str(Path(candidate["source"]).relative_to(output_dir.resolve()))
    for case in frozen_suite["cases"]:
        for key in ("input", "answer"):
            case[key] = str(Path(case[key]).relative_to(output_dir.resolve()))

    def save(name, value):
        (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save("suite.json", frozen_suite)
    save("files.json", records)

    def run(source, evidence_name):
        return check_candidate(CheckConfig(
            candidate=Path(source), inputs=[Path(c["input"]) for c in suite["cases"]],
            expected=[Path(c["answer"]) for c in suite["cases"]], validator=Path(suite["validator"]),
            comparison=Comparison(**suite["comparison"]), save_dir=output_dir / evidence_name,
            engine=engine, image=image, limits=limits, compile_seconds=compile_seconds), runner=runner)

    owned = runner is None
    runner = runner or SandboxRunner(engine=engine, image=image, limits=limits, compile_seconds=compile_seconds)
    result = {"status": "inconclusive", "kind": "data_strength_execution",
              "suite": "suite.json", "files": "files.json", "reference": "reference.json",
              "reference_control_passed": False, "limits": asdict(limits),
              "engine": engine, "image": image, "compile_seconds": compile_seconds,
              "candidates": [], "score_effect": "none",
              "interpretation": "Frozen batch-suite observations only. Reference/validator semantics, candidate wrongness and allowed_groups require independent review. No automatic strength score or correctness guarantee."}
    try:
        reference = run(suite["reference"], "reference-evidence")
        save("reference.json", reference)
        reliable = reference.get("all_cases_matched", False) and all(
            c.get("input_legality") == "validator_accepted" for c in reference.get("cases", []))
        result["reference_control_passed"] = reliable
        if reliable:
            for index, candidate in enumerate(suite["candidates"]):
                report = run(candidate["source"], f"candidate-{index:04d}-evidence")
                name = f"candidate-{index:04d}.json"
                save(name, report)
                row = summarize_candidate(suite, candidate, report)
                row["report"] = name
                result["candidates"].append(row)
            if all(c["complete"] for c in result["candidates"]):
                result["status"] = "completed"
    finally:
        if owned:
            runner.close()
    save("summary.json", result)
    return result


def register_cli(subparsers):
    parser = subparsers.add_parser("test-data", help="test candidates on a frozen batch suite; no automatic deductions")
    parser.add_argument("suite", type=Path, help="suite JSON; relative paths resolve from this file")
    parser.add_argument("--output-dir", type=Path, required=True, help="new evidence directory; refuses overwrite")
    parser.add_argument("--engine", choices=("auto", "docker", "podman"), default="auto")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--memory-mib", type=int, default=256)
    parser.add_argument("--compile-timeout", type=float, default=30.0)
    parser.add_argument("--output-limit-kib", type=int, default=1024)
    parser.set_defaults(func=_command)


def _command(args):
    result = evaluate_suite(args.suite, args.output_dir, engine=args.engine, image=args.image,
                            limits=Limits(wall_seconds=args.timeout, memory_mib=args.memory_mib,
                                          output_bytes=args.output_limit_kib * 1024),
                            compile_seconds=args.compile_timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 3
