"""Sample checks, seeded differential evidence, and bounded timing observations.

These results are evidence for a reviewer. They do not change a score and a
finite set of matches does not establish correctness.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import sys
from typing import Any
import uuid

from .runner import DEFAULT_IMAGE, ExecutionResult, Limits, PreparedProgram, SandboxRunner, SOURCE_LIMIT


_FLOAT_TOKEN = re.compile(rb"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


@dataclass(frozen=True)
class Comparison:
    mode: str = "exact"
    abs_tolerance: float | None = None
    rel_tolerance: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("exact", "tokens", "float"):
            raise ValueError("comparison mode must be exact, tokens, or float")
        if self.mode == "float":
            for name in ("abs_tolerance", "rel_tolerance"):
                value = getattr(self, name)
                if value is None or not math.isfinite(value) or value < 0:
                    raise ValueError("float comparison requires explicit finite, nonnegative abs and rel tolerances")
        elif self.abs_tolerance is not None or self.rel_tolerance is not None:
            raise ValueError("tolerances may only be set with --compare float")


def compare_outputs(candidate: bytes, expected: bytes,
                    policy: Comparison | None = None) -> dict[str, Any]:
    """Do not interpret malformed reference output as a candidate failure."""
    policy = policy or Comparison()
    if policy.mode == "exact":
        return {"status": "match" if candidate == expected else "mismatch", "mode": "exact"}
    expected_tokens = expected.split()
    candidate_tokens = candidate.split()
    if policy.mode == "tokens":
        return {"status": "match" if candidate_tokens == expected_tokens else "mismatch", "mode": "tokens"}
    # The float policy is numeric-only. Arbitrary mixed text or NaN/Inf in the
    # reference is a comparator/reference contract error, never a wrong answer.
    try:
        if any(_FLOAT_TOKEN.fullmatch(token) is None for token in expected_tokens):
            raise ValueError("invalid expected numeric token syntax")
        expected_values = [float(token) for token in expected_tokens]
        if any(not math.isfinite(value) for value in expected_values):
            raise ValueError("nonfinite expected value")
    except (ValueError, OverflowError):
        return {"status": "reference_error", "detail": "Float policy requires finite numeric reference tokens", "mode": "float"}
    if len(candidate_tokens) != len(expected_tokens):
        return {"status": "mismatch", "detail": "Token count differs", "mode": "float"}
    try:
        if any(_FLOAT_TOKEN.fullmatch(token) is None for token in candidate_tokens):
            raise ValueError("invalid candidate numeric token syntax")
        values = [float(token) for token in candidate_tokens]
        matches = all(math.isfinite(value) and math.isclose(value, reference,
                      abs_tol=policy.abs_tolerance, rel_tol=policy.rel_tolerance)
                      for value, reference in zip(values, expected_values))
    except (ValueError, OverflowError):
        matches = False
    return {"status": "match" if matches else "mismatch", "mode": "float",
            "abs_tolerance": policy.abs_tolerance, "rel_tolerance": policy.rel_tolerance}


@dataclass
class CheckConfig:
    candidate: Path
    language: str | None = None
    inputs: list[Path] = field(default_factory=list)
    expected: list[Path] = field(default_factory=list)
    oracle: Path | None = None
    oracle_language: str | None = None
    validator: Path | None = None
    validator_language: str | None = None
    generator: Path | None = None
    generator_language: str | None = None
    seed: int = 0
    cases: int = 20
    start_case: int = 0
    comparison: Comparison = field(default_factory=Comparison)
    save_dir: Path = field(default_factory=lambda: Path(".cpscore/counterexamples"))
    engine: str = "auto"
    image: str = DEFAULT_IMAGE
    limits: Limits = field(default_factory=Limits)
    compile_seconds: float = 30.0

    def validate(self) -> None:
        if not self.inputs and self.generator is None:
            raise ValueError("Provide --input or --generator")
        if self.oracle is None and not self.expected:
            raise ValueError("Provide --oracle or one --expected file per input")
        if self.oracle is not None and self.expected:
            raise ValueError("--oracle and --expected are mutually exclusive")
        if self.expected and len(self.expected) != len(self.inputs):
            raise ValueError("Each --input requires one --expected in the same order")
        if self.generator is not None and (self.oracle is None or self.validator is None):
            raise ValueError("Generated cases require both --oracle and --validator")
        if self.generator is not None and self.cases <= 0:
            raise ValueError("--cases must be positive")
        if self.start_case < 0:
            raise ValueError("--start-case must be nonnegative")


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(SOURCE_LIMIT + 1)
    if len(data) > SOURCE_LIMIT:
        raise ValueError(f"{path} exceeds the {SOURCE_LIMIT}-byte input/reference file limit")
    return data


def _tool_failure(role: str, result: ExecutionResult) -> dict[str, Any]:
    return {"status": "unavailable" if result.status == "unavailable" else "tool_error",
            "role": role, "execution": result.to_dict(),
            "detail": f"{role} did not complete successfully; no algorithm-error conclusion is supported"}


def _source_metadata(program: PreparedProgram) -> dict[str, Any]:
    return {"path": str(program.source), "language": program.language,
            "sha256": program.source_sha256, "compilation": program.compilation.to_dict()}


def _save_evidence(config: CheckConfig, programs: dict[str, PreparedProgram],
                   case: dict[str, Any], stdin: bytes, expected: bytes | None,
                   executions: dict[str, ExecutionResult], environment: dict[str, Any]) -> str:
    digest = hashlib.sha256(stdin).hexdigest()
    directory = config.save_dir.resolve() / (f"{case['index']:04d}-{digest[:12]}-{uuid.uuid4().hex[:8]}")
    directory.mkdir(parents=True)
    (directory / "input.bin").write_bytes(stdin)
    if expected is not None:
        (directory / "expected.bin").write_bytes(expected)
    sources = directory / "sources"
    sources.mkdir()
    source_records = {}
    saved = {}
    for role, program in programs.items():
        suffix = ".cpp" if program.language == "cpp" else ".py"
        destination = sources / (role + suffix)
        # Copy the exact immutable snapshot compiled, not a potentially changed
        # file at the original user path.
        destination.write_bytes((program.mount_directory / ("program.cpp" if program.language == "cpp" else "program.py")).read_bytes())
        source_records[role] = {**_source_metadata(program), "saved_path": str(destination.relative_to(directory))}
        saved[role] = destination
    output_records = {}
    for role, execution in executions.items():
        (directory / f"{role}.stdout").write_bytes(execution.stdout)
        (directory / f"{role}.stderr").write_bytes(execution.stderr)
        output_records[role] = {**execution.to_dict(include_output=False),
                                "stdout_file": f"{role}.stdout", "stderr_file": f"{role}.stderr"}
    def evidence_path(path: Path) -> str:
        return "@EVIDENCE@/" + str(path.relative_to(directory))

    replay_arguments = ["check-candidate", "--candidate", evidence_path(saved["candidate"]),
              "--input", "@EVIDENCE@/input.bin", "--image", environment.get("image_id", config.image),
              "--engine", environment.get("engine", config.engine), "--compare", config.comparison.mode,
              "--timeout", str(config.limits.wall_seconds), "--memory-mib", str(config.limits.memory_mib),
              "--cpus", str(config.limits.cpus), "--pids", str(config.limits.pids),
              "--output-limit-bytes", str(config.limits.output_bytes),
              "--scratch-mib", str(config.limits.scratch_mib),
              "--compile-timeout", str(config.compile_seconds), "--save-dir", "@EVIDENCE@/replayed-evidence"]
    if "oracle" in saved:
        replay_arguments += ["--oracle", evidence_path(saved["oracle"])]
    elif expected is not None:
        replay_arguments += ["--expected", "@EVIDENCE@/expected.bin"]
    if "validator" in saved:
        replay_arguments += ["--validator", evidence_path(saved["validator"])]
    if config.comparison.mode == "float":
        replay_arguments += ["--abs-tol", str(config.comparison.abs_tolerance), "--rel-tol", str(config.comparison.rel_tolerance)]
    runtime_root = Path(__file__).resolve().parents[1]
    # A skill bootstrap may only have injected its bundled runtime into sys.path.
    # A fresh `python -m cpscore` would then fail outside that process. The helper
    # explicitly locates the same runtime, also under `python -I`, and relocates
    # every evidence file relative to its own directory when the bundle moves.
    replay_script = (
        '"""Replay saved evidence; use --runtime PATH if CPScore was relocated."""\n'
        "import argparse\nfrom pathlib import Path\nimport sys\n\n"
        "parser = argparse.ArgumentParser(add_help=False)\n"
        f"parser.add_argument('--runtime', type=Path, default=Path({str(runtime_root)!r}))\n"
        "options, extra = parser.parse_known_args()\n"
        "runtime = options.runtime.resolve()\n"
        "if not (runtime / 'cpscore' / '__init__.py').is_file():\n"
        "    print('Recorded CPScore runtime is missing; supply --runtime PATH', file=sys.stderr)\n"
        "    raise SystemExit(2)\n"
        "sys.path.insert(0, str(runtime))\n"
        "from cpscore.cli import main\n"
        "if extra == ['--help']:\n"
        "    raise SystemExit(main(['check-candidate', '--help']))\n"
        "if extra:\n"
        "    parser.error('only --runtime PATH or --help may override the saved replay')\n"
        "evidence = Path(__file__).resolve().parent\n"
        f"arguments = {replay_arguments!r}\n"
        "arguments = [str(evidence / value[len('@EVIDENCE@/'):]) if value.startswith('@EVIDENCE@/') else value for value in arguments]\n"
        "raise SystemExit(main(arguments))\n"
    )
    (directory / "replay.py").write_text(replay_script, encoding="utf-8")
    replay = [sys.executable, str(directory / "replay.py")]
    manifest = {
        "manifest_version": 1,
        "kind": "validation_evidence",
        "validated_differential_mismatch": case["status"] == "candidate_mismatch",
        "oracle_correctness": "assumed_requires_review" if "oracle" in programs else "no_oracle_executed",
        "case": case,
        "input": {"file": "input.bin", "bytes": len(stdin), "sha256": digest},
        "expected": None if expected is None else {"file": "expected.bin", "bytes": len(expected),
                                                   "sha256": hashlib.sha256(expected).hexdigest()},
        "sources": source_records,
        "executions": output_records,
        "comparison": asdict(config.comparison),
        "environment": environment,
        "generation": {"seed": config.seed, "case_index": case.get("generator_case_index"),
                       "argv_contract": "generator receives decimal SEED CASE_INDEX as two positional arguments"}
                      if config.generator else None,
        "replay_argv": replay,
        "replay_shell": shlex.join(replay),
        "replay_script": "replay.py",
        "runtime_root": str(runtime_root),
        "runtime_relocation": "python3 replay.py --runtime /path/containing/cpscore; saved source/input paths relocate automatically",
        "interpretation": "Finite validation evidence only; no score is changed automatically.",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(directory / "manifest.json")


def check_candidate(config: CheckConfig, *, runner: SandboxRunner | None = None) -> dict[str, Any]:
    """Return explicit infrastructure, input, oracle, and candidate outcomes."""
    try:
        config.validate()
    except ValueError as exc:
        return {"status": "config_error", "detail": str(exc), "cases": []}
    owned = runner is None
    runner = runner or SandboxRunner(engine=config.engine, image=config.image, limits=config.limits,
                                     compile_seconds=config.compile_seconds)
    try:
        available = runner.availability()
        if available.status != "ok":
            return {"status": "unavailable", "detail": available.detail, "sandbox": available.to_dict(), "cases": []}
        programs = {}
        for role in ("validator", "generator", "oracle", "candidate"):
            path = getattr(config, role)
            if path is None:
                continue
            language = config.language if role == "candidate" else getattr(config, role + "_language")
            program, compilation = runner.prepare(path, language, role=role)
            if program is None:
                if role == "candidate" and compilation.status in ("nonzero_exit", "timeout", "memory_limit", "output_limit"):
                    return {"status": "candidate_compile_error", "role": role,
                            "compilation": compilation.to_dict(), "cases": [], "environment": runner.environment(),
                            "score_effect": "none"}
                return {**_tool_failure(role + " compilation", compilation), "cases": []}
            programs[role] = program
        environment = runner.environment()
        report: dict[str, Any] = {
            "status": "completed", "mode": "differential" if config.oracle else "samples",
            "seed": config.seed if config.generator else None, "comparison": asdict(config.comparison),
            "environment": environment,
            "programs": {role: _source_metadata(program) for role, program in programs.items()},
            "cases": [], "score_effect": "none",
            "oracle_correctness": "assumed_requires_review" if config.oracle else "no_oracle_executed",
            "interpretation": "Finite evidence only. Oracle correctness requires review. Matches do not prove correctness; timeouts are observations under recorded limits.",
        }
        total = len(config.inputs) + (config.cases if config.generator else 0)
        for index in range(total):
            executions = {}
            expected = None
            case: dict[str, Any] = {"index": index, "status": "pending", "input_legality": "unverified"}
            generated = index >= len(config.inputs)
            if generated:
                generator_index = config.start_case + index - len(config.inputs)
                case.update({"origin": "generated", "generator_case_index": generator_index, "seed": config.seed})
                generation = runner.run(programs["generator"], b"", arguments=[str(config.seed), str(generator_index)])
                executions["generator"] = generation
                if generation.status != "ok":
                    case.update(_tool_failure("generator", generation))
                    report["cases"].append(case)
                    # There is no valid input or counterexample to save.
                    continue
                stdin = generation.stdout
            else:
                case.update({"origin": "file", "input_path": str(config.inputs[index].resolve())})
                try:
                    stdin = _read_bounded(config.inputs[index])
                    if config.expected:
                        expected = _read_bounded(config.expected[index])
                except (OSError, ValueError) as exc:
                    case.update({"status": "config_error", "detail": str(exc)})
                    report["cases"].append(case)
                    continue
            case["input_sha256"] = hashlib.sha256(stdin).hexdigest()
            if "validator" in programs:
                validation = runner.run(programs["validator"], stdin)
                executions["validator"] = validation
                if validation.status != "ok":
                    if validation.status == "nonzero_exit" and validation.exit_code in (1, 2):
                        case.update({"status": "invalid_input", "role": "validator",
                                     "detail": "Validator rejected input; no candidate verdict was made"})
                    else:
                        case.update(_tool_failure("validator", validation))
                    case["input_legality"] = "rejected_or_unknown"
                else:
                    case["input_legality"] = "validator_accepted"
            if case["status"] == "pending" and "oracle" in programs:
                oracle = runner.run(programs["oracle"], stdin)
                executions["oracle"] = oracle
                if oracle.status != "ok":
                    case.update(_tool_failure("oracle", oracle))
                else:
                    expected = oracle.stdout
            if case["status"] == "pending":
                execution = runner.run(programs["candidate"], stdin)
                executions["candidate"] = execution
                if execution.status != "ok":
                    if execution.status in ("sandbox_error", "unavailable", "config_error"):
                        case.update(_tool_failure("candidate execution infrastructure", execution))
                    else:
                        case.update({"status": "candidate_execution_failure", "execution_status": execution.status,
                                     "detail": "Observed candidate failure under the recorded limits; no automatic TLE or score deduction"})
                else:
                    assert expected is not None
                    comparison = compare_outputs(execution.stdout, expected, config.comparison)
                    case["comparison"] = comparison
                    if comparison["status"] == "reference_error":
                        case.update({"status": "tool_error", "role": "comparator/reference",
                                     "detail": comparison["detail"]})
                    elif comparison["status"] == "match":
                        case["status"] = "match"
                    elif case["input_legality"] == "validator_accepted" and "oracle" in executions and executions["oracle"].status == "ok":
                        case["status"] = "candidate_mismatch"
                    elif "oracle" not in programs:
                        case.update({"status": "sample_mismatch", "detail": "Differs from a supplied expected output; no successful oracle execution established"})
                    else:
                        case.update({"status": "unverified_mismatch", "detail": "Differs from the oracle but input legality was not established by a validator"})
            case["executions"] = {role: execution.to_dict() for role, execution in executions.items()}
            if case["status"] != "match":
                try:
                    case["manifest"] = _save_evidence(config, programs, case, stdin, expected, executions, environment)
                except OSError as exc:
                    case["evidence_save_error"] = str(exc)
                    report["evidence_save_failed"] = True
            report["cases"].append(case)
        counts: dict[str, int] = {}
        for case in report["cases"]:
            counts[case["status"]] = counts.get(case["status"], 0) + 1
        report["counts"] = counts
        report["all_cases_matched"] = bool(report["cases"]) and counts.get("match", 0) == len(report["cases"])
        return report
    finally:
        if owned:
            runner.close()


def benchmark(candidate: Path, inputs: list[Path], *, language: str | None = None,
              repetitions: int = 3, warmups: int = 1, validator: Path | None = None,
              validator_language: str | None = None, engine: str = "auto", image: str = DEFAULT_IMAGE,
              limits: Limits | None = None, compile_seconds: float = 30.0,
              runner: SandboxRunner | None = None) -> dict[str, Any]:
    if not inputs or repetitions <= 0 or warmups < 0:
        return {"status": "config_error", "detail": "Provide inputs, positive repetitions, and nonnegative warmups"}
    owned = runner is None
    runner = runner or SandboxRunner(engine=engine, image=image, limits=limits, compile_seconds=compile_seconds)
    try:
        availability = runner.availability()
        if availability.status != "ok":
            return {"status": "unavailable", "detail": availability.detail, "runs": []}
        program, compilation = runner.prepare(candidate, language, role="candidate")
        if program is None:
            if compilation.status in ("nonzero_exit", "timeout", "memory_limit", "output_limit"):
                return {"status": "candidate_compile_error", "compilation": compilation.to_dict()}
            return _tool_failure("candidate compilation infrastructure", compilation)
        validator_program = None
        if validator:
            validator_program, result = runner.prepare(validator, validator_language, role="validator")
            if validator_program is None:
                return _tool_failure("validator compilation", result)
        report: dict[str, Any] = {
            "status": "completed", "kind": "performance_observations", "environment": runner.environment(),
            "program": _source_metadata(program), "warmups": warmups, "repetitions": repetitions,
            "timing_scope": "container attach wall time, including startup overhead; not algorithm CPU time",
            "interpretation": "Measurements are specific to this machine, image, limits and load. No automatic TLE, asymptotic claim, or score deduction.",
            "score_effect": "none", "inputs": [],
        }
        for input_path in inputs:
            record: dict[str, Any] = {"path": str(input_path.resolve()), "runs": []}
            try:
                stdin = _read_bounded(input_path)
            except (OSError, ValueError) as exc:
                record.update({"status": "config_error", "detail": str(exc)})
                report["inputs"].append(record)
                continue
            record.update({"sha256": hashlib.sha256(stdin).hexdigest(), "bytes": len(stdin),
                           "input_legality": "unverified"})
            if validator_program:
                validated = runner.run(validator_program, stdin)
                record["validation"] = validated.to_dict()
                if validated.status != "ok":
                    record.update(_tool_failure("validator", validated))
                    report["inputs"].append(record)
                    continue
                record["input_legality"] = "validator_accepted"
            record["warmup_runs"] = []
            for index in range(warmups + repetitions):
                result = runner.run(program, stdin)
                (record["warmup_runs"] if index < warmups else record["runs"]).append(result.to_dict(include_output=False))
                if result.status != "ok":
                    record["status"] = "tool_error" if result.status in ("sandbox_error", "unavailable") else "candidate_execution_failure"
                    break
            times = [run["wall_seconds"] for run in record["runs"] if run["status"] == "ok"]
            if len(times) == repetitions:
                record.update({"status": "measured", "min_wall_seconds": min(times),
                               "median_wall_seconds": statistics.median(times), "max_wall_seconds": max(times)})
            report["inputs"].append(record)
        return report
    finally:
        if owned:
            runner.close()


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--language", choices=("cpp", "python"))
    parser.add_argument("--input", action="append", default=[], type=Path, dest="inputs")
    parser.add_argument("--validator", type=Path)
    parser.add_argument("--validator-language", choices=("cpp", "python"))
    parser.add_argument("--engine", choices=("auto", "docker", "podman"), default="auto")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="prebuilt local image; never pulled automatically")
    parser.add_argument("--timeout", type=float, default=2.0, help="attach wall seconds, including startup overhead")
    parser.add_argument("--compile-timeout", type=float, default=30.0)
    parser.add_argument("--memory-mib", type=int, default=256)
    parser.add_argument("--cpus", type=float, default=1.0)
    parser.add_argument("--pids", type=int, default=64)
    output_limits = parser.add_mutually_exclusive_group()
    output_limits.add_argument("--output-limit-kib", type=int, default=1024, help="combined stdout/stderr per process")
    output_limits.add_argument("--output-limit-bytes", type=int, help="exact combined stdout/stderr byte limit")
    parser.add_argument("--scratch-mib", type=int, default=128)
    parser.add_argument("--output", type=Path, help="also save the JSON report here")


def _limits(args: argparse.Namespace) -> Limits:
    return Limits(wall_seconds=args.timeout, memory_mib=args.memory_mib, cpus=args.cpus,
                  pids=args.pids, output_bytes=args.output_limit_bytes if args.output_limit_bytes is not None else args.output_limit_kib * 1024,
                  scratch_mib=args.scratch_mib)


def _emit(report: dict[str, Any], output: Path | None) -> int:
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if report["status"] == "unavailable":
        return 3
    if report["status"] in ("config_error", "tool_error") or report.get("evidence_save_failed"):
        return 2
    if report["status"] != "completed":
        return 1
    if "all_cases_matched" in report:
        if any(case["status"] in ("tool_error", "config_error", "unavailable", "invalid_input") for case in report["cases"]):
            return 2
        return 0 if report["all_cases_matched"] else 1
    observations = report.get("inputs", [])
    if any(record.get("status") in ("tool_error", "config_error", "unavailable") for record in observations):
        return 2
    return 0 if observations and all(record.get("status") == "measured" for record in observations) else 1


def _check_command(args: argparse.Namespace) -> int:
    try:
        comparison = Comparison(args.compare, args.abs_tol, args.rel_tol)
        config = CheckConfig(candidate=args.candidate, language=args.language, inputs=args.inputs,
                             expected=args.expected, oracle=args.oracle, oracle_language=args.oracle_language,
                             validator=args.validator, validator_language=args.validator_language,
                             generator=args.generator, generator_language=args.generator_language,
                             seed=args.seed, cases=args.cases, start_case=args.start_case,
                             comparison=comparison, save_dir=args.save_dir, engine=args.engine, image=args.image,
                             limits=_limits(args), compile_seconds=args.compile_timeout)
        result = check_candidate(config)
    except (ValueError, OSError) as exc:
        result = {"status": "config_error", "detail": str(exc), "cases": []}
    return _emit(result, args.output)


def _bench_command(args: argparse.Namespace) -> int:
    try:
        report = benchmark(args.candidate, args.inputs, language=args.language,
                           repetitions=args.repetitions, warmups=args.warmups, validator=args.validator,
                           validator_language=args.validator_language, engine=args.engine, image=args.image,
                           limits=_limits(args), compile_seconds=args.compile_timeout)
    except (ValueError, OSError) as exc:
        report = {"status": "config_error", "detail": str(exc)}
    return _emit(report, args.output)


def register_cli(subparsers: Any) -> None:
    check = subparsers.add_parser("check-candidate", help="isolated sample and seeded differential evidence")
    _common_arguments(check)
    check.add_argument("--expected", action="append", default=[], type=Path)
    check.add_argument("--oracle", type=Path)
    check.add_argument("--oracle-language", choices=("cpp", "python"))
    check.add_argument("--generator", type=Path)
    check.add_argument("--generator-language", choices=("cpp", "python"))
    check.add_argument("--seed", type=int, default=0)
    check.add_argument("--cases", type=int, default=20)
    check.add_argument("--start-case", type=int, default=0)
    check.add_argument("--compare", choices=("exact", "tokens", "float"), default="exact")
    check.add_argument("--abs-tol", type=float)
    check.add_argument("--rel-tol", type=float)
    check.add_argument("--save-dir", type=Path, default=Path(".cpscore/counterexamples"))
    check.set_defaults(func=_check_command)
    bench = subparsers.add_parser("bench", help="isolated performance observations with environment metadata")
    _common_arguments(bench)
    bench.add_argument("--repetitions", type=int, default=3)
    bench.add_argument("--warmups", type=int, default=1)
    bench.set_defaults(func=_bench_command)
