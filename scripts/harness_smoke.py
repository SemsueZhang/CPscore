#!/usr/bin/env python3
"""Opt-in real harness invocation, never a mocked installation success.

Outputs remain in the chosen new directory for independent inspection. A valid
report establishes only execution/protocol compliance, not review accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpscore.harness import HARNESSES, MANIFEST, install
from cpscore.schema import loads_json, validate_report
from cpscore.scoring import score_report
from cpscore.rubric import SCHEMA_VERSION


def _write_json_new(path, value):
    # A model may have created this name, including as a symlink to an external
    # file. Exclusive creation refuses both cases without following the link.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _plain_file(project, relative):
    path = project / relative
    for item in (path, *path.parents):
        if item == project:
            break
        if item.is_symlink():
            raise ValueError(f"Harness replaced a protected path with a symlink: {relative}")
    if not path.is_file():
        raise ValueError(f"Harness removed or replaced a protected file: {relative}")
    return path


def _invoke(command, project, timeout):
    """Capture actual CLI output and stop its process group on timeout."""
    with (project / "events.jsonl").open("xb") as out, (project / "stderr.log").open("xb") as err:
        process = subprocess.Popen(command, cwd=project, stdout=out, stderr=err,
                                   start_new_session=(os.name == "posix"))
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            # Also clean up when the user interrupts this controller.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
            raise


def _cli_version(cli):
    try:
        version = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=10)
        return {"status": "recorded" if version.returncode == 0 else "unavailable",
                "exit_code": version.returncode, "stdout": version.stdout.strip(),
                "stderr": version.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "detail": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=HARNESSES, required=True)
    parser.add_argument("--skill", choices=("statement", "solution", "editorial", "data"), required=True)
    parser.add_argument("--material", type=Path, required=True)
    parser.add_argument("--context", type=Path, action="append", default=[])
    parser.add_argument("--model", required=True, help="Explicit available model; for OpenCode use provider/model")
    parser.add_argument("--output-dir", type=Path, required=True, help="Must not exist")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("timeout must be positive")
    sources = [args.material, *args.context]
    # Read all inputs before making a project, without executing their contents.
    materials = [(path.name, path.read_bytes()) for path in sources]
    requested_project = args.output_dir.expanduser().absolute()
    if requested_project.is_symlink():
        raise ValueError("output directory must not be a symlink")
    project = requested_project.resolve()
    project.mkdir(parents=True, exist_ok=False)
    identity = (project.stat().st_dev, project.stat().st_ino)
    metadata = {"harness": args.harness, "skill": args.skill, "model": args.model,
                "status": "not_invoked", "ai_accuracy": "not_established", "materials": []}

    def verify_project():
        stat = project.stat()
        if project.is_symlink() or not project.is_dir() or (stat.st_dev, stat.st_ino) != identity:
            raise ValueError("Harness moved or replaced the output directory")

    def finish(status, detail, code):
        metadata.update(status=status, detail=detail)
        try:
            verify_project()
            _write_json_new(project / "run.json", metadata)
        except (OSError, ValueError) as exc:
            # Never overwrite a harness-created record or follow its symlink.
            # stdout still retains the controller's independently observed result.
            metadata["record_error"] = str(exc)
            if code == 0:
                metadata.update(status="invalid_output", detail="Harness occupied or replaced the controller record path")
                code = 2
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return code

    cli = shutil.which(HARNESSES[args.harness]["cli"])
    if cli is None:
        return finish("unavailable", "Harness CLI is not on PATH; no model invocation occurred", 2)
    metadata["cli_version"] = _cli_version(cli)
    install(project, [args.harness])
    manifest_bytes = (project / MANIFEST).read_bytes()
    protected = dict(loads_json(manifest_bytes.decode("utf-8"))["files"])
    protected[MANIFEST] = hashlib.sha256(manifest_bytes).hexdigest()
    for i, (name, data) in enumerate(materials):
        destination = f"material-{i}-{name}"
        with (project / destination).open("xb") as stream:
            stream.write(data)
        digest = hashlib.sha256(data).hexdigest()
        metadata["materials"].append({"file": destination, "sha256": digest})
        protected[destination] = digest
    skill = f"cp-{args.skill}-review"
    prompt = (f"Use the installed {skill} Skill. Read its SKILL.md and shared protocol. "
              f"Review material-0-{materials[0][0]} as {args.skill}; other material-* files are context only. "
              f"Write protocol {SCHEMA_VERSION} input to review.json with scope [{args.skill!r}], actual category-specific "
              "coverage evidence, findings and unexecuted checks where applicable. Use the installed deterministic "
              "CLI to validate and score to scored.json. Do not edit the supplied materials or installed tools, "
              "schemas, protocol, skills or manifest. Do not create run.json or verified-scored.json; the "
              "controller reserves these paths. Do not execute candidate programs outside the CPScore isolation "
              "tool; manual reasoning is allowed. Report evidence gaps honestly. Do not change the tool or "
              "schema to make your result pass.")
    prompt_bytes = (prompt + "\n").encode("utf-8")
    (project / "prompt.txt").write_bytes(prompt_bytes)
    protected["prompt.txt"] = hashlib.sha256(prompt_bytes).hexdigest()
    metadata["protected_files"] = protected
    if args.harness == "codex":
        command = [cli, "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
                   "--sandbox", "workspace-write", "-m", args.model,
                   "-c", 'model_reasoning_effort="xhigh"', "-C", str(project),
                   "--json", "-o", str(project / "answer.txt"), prompt]
    elif args.harness == "claude-code":
        command = [cli, "--print", "--model", args.model, "--output-format", "json", prompt]
    else:
        command = [cli, "run", "--model", args.model, "--format", "json", prompt]
    metadata["command"] = command
    started = time.monotonic()
    try:
        # Files avoid unbounded capture in memory; the harness owns its own sandbox.
        exit_code = _invoke(command, project, args.timeout)
        metadata.update(exit_code=exit_code, elapsed_seconds=round(time.monotonic() - started, 2))
    except (OSError, subprocess.TimeoutExpired) as exc:
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 2)
        return finish("invocation_failed", str(exc), 2)
    if exit_code:
        return finish("invocation_failed", "See stderr.log and events.jsonl; no success inferred from installation", 2)
    try:
        verify_project()
        for relative, digest in protected.items():
            if hashlib.sha256(_plain_file(project, relative).read_bytes()).hexdigest() != digest:
                return finish("invalid_output", f"Harness altered protected file: {relative}", 2)
        report = loads_json(_plain_file(project, "review.json").read_text(encoding="utf-8"))
        issues = validate_report(report)
        if issues:
            return finish("invalid_output", str([i.as_dict() for i in issues]), 2)
        if report["scope"] != [args.skill]:
            return finish("invalid_output", "Review scope differs from the requested skill", 2)
        scored = score_report(report)
        _write_json_new(project / "verified-scored.json", scored)
        metadata["assessment"] = {k: scored["overall"][k] for k in ("score", "tier", "recommendable", "qualification", "completion")}
    except (ValueError, OSError) as exc:
        return finish("invalid_output", str(exc), 2)
    return finish("invoked_and_validated", "Real CLI returned a structurally valid report, independently rescored; accuracy requires human adjudication", 0)


if __name__ == "__main__":
    raise SystemExit(main())
