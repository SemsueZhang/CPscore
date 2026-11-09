"""Command-line entry points; optional harness/runner code loads lazily."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from . import __version__
from .reporting import render_json, render_markdown
from .schema import ReportValidationError, load_schema, loads_json, validate_report, validate_scored_report
from .scoring import make_report, score_report


def _write(content: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(content)
    else:
        Path(output).write_text(content, encoding="utf-8")


def _read(path: str) -> Any:
    return loads_json(sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8"))


def _init(args: argparse.Namespace) -> int:
    report = make_report(args.scope.split(","), review_id=args.review_id, snapshot_id=args.snapshot_id)
    _write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", args.output)
    return 0


def _score(args: argparse.Namespace) -> int:
    scored = score_report(_read(args.report))
    _write(render_json(scored) if args.format == "json" else render_markdown(scored), args.output)
    return 0


def _validate(args: argparse.Namespace) -> int:
    value = _read(args.report)
    issues = validate_scored_report(value) if args.scored else validate_report(value)
    print(json.dumps({"valid": not issues, "errors": [issue.as_dict() for issue in issues]}, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if issues else 0


def _schema(args: argparse.Namespace) -> int:
    _write(json.dumps(load_schema(args.kind), ensure_ascii=False, indent=2) + "\n", args.output)
    return 0


def build_parser(*, extensions: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpscore", description="Evidence-based artifact review with deterministic, root-cause-deduplicated scores.")
    parser.add_argument("--version", action="version", version=f"cpscore {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-report", help="create an explicit, unreviewed report snapshot")
    init.add_argument("--scope", default="statement,solution,editorial", help="comma-separated requested objects")
    init.add_argument("--review-id", default="review-1")
    init.add_argument("--snapshot-id", default="snapshot-1")
    init.add_argument("--output", "-o", default="-", help="destination; '-' means stdout")
    init.set_defaults(func=_init)
    score = commands.add_parser("score", help="validate input and generate deterministic scores and report")
    score.add_argument("report", help="input review JSON; '-' means stdin")
    score.add_argument("--format", choices=("markdown", "json"), default="markdown")
    score.add_argument("--output", "-o", default="-")
    score.set_defaults(func=_score)
    validate = commands.add_parser("validate", help="check JSON Schema structure and cross-record semantics")
    validate.add_argument("report", help="input JSON; '-' means stdin")
    validate.add_argument("--scored", action="store_true", help="validate generated output and recompute its scores")
    validate.set_defaults(func=_validate)
    schema = commands.add_parser("schema", help="print a bundled structural JSON Schema")
    schema.add_argument("--kind", choices=("report", "scored-report"), default="report")
    schema.add_argument("--output", "-o", default="-")
    schema.set_defaults(func=_schema)
    if extensions:
        for module_name in ("cpscore.harness", "cpscore.validation", "cpscore.novelty_evidence"):
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                if exc.name != module_name:
                    raise
                continue
            register = getattr(module, "register_cli", None)
            if register is not None:
                register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Import optional integrations only for their commands or complete help.
    arguments = list(sys.argv[1:] if argv is None else argv)
    core_commands = {"init-report", "score", "validate", "schema"}
    command = next((argument for argument in arguments if not argument.startswith("-")), None)
    parser = build_parser(extensions=command not in core_commands)
    args = parser.parse_args(arguments)
    try:
        return int(args.func(args) or 0)
    except ReportValidationError as exc:
        print(json.dumps({"valid": False, "errors": [issue.as_dict() for issue in exc.issues]}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"valid": False, "errors": [{"path": "$", "message": str(exc), "code": "input"}]}, ensure_ascii=False), file=sys.stderr)
        return 2
