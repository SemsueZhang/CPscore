"""Project-scoped Agent Skills adapters with conservative file ownership."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

SKILLS = ("cp-statement-review", "cp-solution-review", "cp-editorial-review")
HARNESSES = {
    "codex": {"directory": ".agents/skills", "cli": "codex"},
    "claude-code": {"directory": ".claude/skills", "cli": "claude"},
    "opencode-deepseek": {"directory": ".opencode/skills", "cli": "opencode"},
}
MANIFEST = ".cpscore/manifest.json"
OWNER = "cpscore-project-skills"


class InstallationError(ValueError):
    """Refuse operations that could change unowned or edited files."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _project(value: str | Path) -> Path:
    # Resolve the user-selected project itself (e.g. macOS /tmp -> /private/tmp),
    # but never follow symlinks within the managed installation below it.
    root = Path(os.path.abspath(os.path.expanduser(str(value)))).resolve()
    if not root.is_dir():
        raise InstallationError(f"Project directory does not exist: {root}")
    return root


def _select(names: list[str] | tuple[str, ...] | None) -> list[str]:
    result: list[str] = []
    for name in names or ["all"]:
        if name == "deepseek":
            raise InstallationError("unsupported: DeepSeek is a model/API, not a skill-loading harness; use opencode-deepseek")
        if name == "all":
            result.extend(HARNESSES)
        elif name in HARNESSES:
            result.append(name)
        else:
            raise InstallationError(f"Unsupported harness: {name}")
    return list(dict.fromkeys(result))


def _allowed(relative: str) -> bool:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or str(path) != relative or "\\" in relative:
        return False
    if relative == ".cpscore/protocol.md":
        return True
    if re.fullmatch(r"\.cpscore/runtime/cpscore/[a-z_][a-z0-9_]*\.py", relative):
        return True
    if relative in (".cpscore/runtime/cpscore/schemas/report.schema.json", ".cpscore/runtime/cpscore/schemas/scored-report.schema.json"):
        return True
    return any(
        relative == f"{h['directory']}/{skill}/{suffix}"
        for h in HARNESSES.values()
        for skill in SKILLS
        for suffix in ("SKILL.md", "scripts/cpscore.py")
    )


def _safe_path(root: Path, relative: str, *, manifest: bool = False) -> Path:
    if not (relative == MANIFEST and manifest) and not _allowed(relative):
        raise InstallationError(f"Unsafe or unmanaged manifest path: {relative!r}")
    path = root / relative
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise InstallationError(f"Refusing symlink: {item}")
        if item != path and item.exists() and not item.is_dir():
            raise InstallationError(f"Parent is not a directory: {item}")
    return path


def _load(root: Path) -> dict[str, Any] | None:
    path = _safe_path(root, MANIFEST, manifest=True)
    if not path.exists():
        if (root / ".cpscore").exists():
            raise InstallationError("Existing .cpscore has no CPscore manifest; preserve it and choose another project or resolve the collision")
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallationError(f"Cannot read installation manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("owner") != OWNER or manifest.get("format") != 1:
        raise InstallationError("Unrecognized installation manifest; refusing to claim ownership")
    files = manifest.get("files")
    harnesses = manifest.get("harnesses")
    if not isinstance(files, dict) or not isinstance(harnesses, list) or not harnesses or any(h not in HARNESSES for h in harnesses):
        raise InstallationError("Invalid installation manifest")
    if len(harnesses) != len(set(harnesses)):
        raise InstallationError("Duplicate harness in manifest")
    for relative, digest in files.items():
        if not isinstance(relative, str) or not _allowed(relative):
            raise InstallationError(f"Unsafe manifest path: {relative!r}")
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            raise InstallationError(f"Invalid manifest hash: {relative}")
        if not relative.startswith(".cpscore/") and not any(relative.startswith(HARNESSES[h]["directory"] + "/") for h in harnesses):
            raise InstallationError("Manifest claims files for an unregistered harness")
    expected = {f"{HARNESSES[h]['directory']}/{skill}/{suffix}" for h in harnesses for skill in SKILLS for suffix in ("SKILL.md", "scripts/cpscore.py")}
    if not expected.issubset(files) or not {".cpscore/protocol.md", ".cpscore/runtime/cpscore/__main__.py", ".cpscore/runtime/cpscore/schemas/report.schema.json", ".cpscore/runtime/cpscore/schemas/scored-report.schema.json"}.issubset(files):
        raise InstallationError("Manifest omits required installed files")
    return manifest


def _state(root: Path, relative: str, digest: str) -> str:
    path = _safe_path(root, relative)
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "not_a_file"
    return "verified" if _digest(path.read_bytes()) == digest else "modified"


def _source_payload(source: Path, names: list[str]) -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    runtime = source / "cpscore"
    if not (runtime / "__main__.py").is_file():
        raise InstallationError("Install from the CPscore source checkout, not an installed runtime")
    for path in sorted(runtime.glob("*.py")):
        if path.is_symlink() or not path.is_file():
            raise InstallationError(f"Unsafe source file: {path}")
        payload[f".cpscore/runtime/cpscore/{path.name}"] = path.read_bytes()
    try:
        for filename in ("report.schema.json", "scored-report.schema.json"):
            schema = runtime / "schemas" / filename
            if schema.is_symlink():
                raise InstallationError(f"Unsafe source file: {schema}")
            payload[f".cpscore/runtime/cpscore/schemas/{filename}"] = schema.read_bytes()
        payload[".cpscore/protocol.md"] = (source / "docs/protocol.md").read_bytes()
        adapter = (source / "scripts/skill_entry.py").read_bytes()
        for name in names:
            for skill in SKILLS:
                prefix = f"{HARNESSES[name]['directory']}/{skill}"
                payload[f"{prefix}/SKILL.md"] = (source / "skills" / skill / "SKILL.md").read_bytes()
                payload[f"{prefix}/scripts/cpscore.py"] = adapter
    except OSError as exc:
        raise InstallationError(f"Skill source assets unavailable; install from a complete CPscore source checkout: {exc}") from exc
    return payload


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    path = _safe_path(root, MANIFEST, manifest=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".manifest-", delete=False) as stream:
            temporary = stream.name
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def install(project: str | Path, harnesses: list[str] | None = None, *, source: str | Path | None = None) -> dict[str, Any]:
    root, names = _project(project), _select(harnesses)
    old = _load(root)
    selected = list(dict.fromkeys((old["harnesses"] if old else []) + names))
    payload = _source_payload(Path(source) if source else Path(__file__).resolve().parents[1], selected)
    old_files = old["files"] if old else {}
    # Preflight every managed file before creating or overwriting anything.
    for relative, digest in old_files.items():
        state = _state(root, relative, digest)
        if state not in ("verified", "missing"):
            raise InstallationError(f"Managed file is {state}; preserve/reconcile it before reinstalling: {relative}")
    for name in selected:
        for skill in SKILLS:
            prefix = f"{HARNESSES[name]['directory']}/{skill}"
            directory = _safe_path(root, f"{prefix}/SKILL.md").parent
            if directory.exists() and not any(p.startswith(prefix + "/") for p in old_files):
                raise InstallationError(f"Unowned skill directory already exists: {directory}")
    for relative in payload:
        path = _safe_path(root, relative)
        if path.exists() and relative not in old_files:
            raise InstallationError(f"Refusing to overwrite unowned file: {relative}")
    for relative, data in payload.items():
        path = _safe_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.write_bytes(data)
        else:
            with path.open("xb") as stream:
                stream.write(data)
    # Removed upstream files are deleted only when unchanged and already owned.
    for relative in set(old_files) - set(payload):
        _safe_path(root, relative).unlink(missing_ok=True)
    manifest = {"owner": OWNER, "format": 1, "harnesses": selected, "files": {p: _digest(data) for p, data in sorted(payload.items())}}
    _write_manifest(root, manifest)
    return {"action": "install", "project": str(root), "harnesses": selected, "managed_files": len(payload), "runtime_copies": 1, "invocation": "not_verified"}


def check(project: str | Path, harnesses: list[str] | None = None) -> dict[str, Any]:
    root, names = _project(project), _select(harnesses)
    manifest = _load(root)
    files = manifest["files"] if manifest else {}
    shared = {p: _state(root, p, digest) for p, digest in files.items() if p.startswith(".cpscore/")}
    results: dict[str, Any] = {}
    for name in names:
        entry = HARNESSES[name]
        states = {p: _state(root, p, digest) for p, digest in files.items() if p.startswith(entry["directory"] + "/")}
        registered = bool(manifest and name in manifest["harnesses"])
        verified = registered and bool(states) and bool(shared) and all(s == "verified" for s in (*states.values(), *shared.values()))
        cli = shutil.which(entry["cli"])
        results[name] = {"file_installation": "verified" if verified else "incomplete" if registered else "not_installed", "files": states, "cli": {"command": entry["cli"], "on_path": cli is not None, "path": cli, "execution": "not_tested"}, "invocation": "not_verified"}
    return {"action": "check", "project": str(root), "shared_files": shared, "harnesses": results, "ok": all(h["file_installation"] == "verified" for h in results.values())}


def uninstall(project: str | Path, harnesses: list[str] | None = None) -> dict[str, Any]:
    root, names = _project(project), _select(harnesses)
    manifest = _load(root)
    if manifest is None:
        return {"action": "uninstall", "project": str(root), "removed_files": 0, "remaining_harnesses": []}
    remaining = [h for h in manifest["harnesses"] if h not in names]
    remove = {p: digest for p, digest in manifest["files"].items() if not remaining or any(p.startswith(HARNESSES[h]["directory"] + "/") for h in names)}
    for relative, digest in remove.items():
        state = _state(root, relative, digest)
        if state not in ("verified", "missing"):
            raise InstallationError(f"Managed file is {state}; preserve/reconcile it before uninstalling: {relative}")
    parents: set[Path] = set()
    for relative in remove:
        path = _safe_path(root, relative)
        path.unlink(missing_ok=True)
        parents.update(p for p in path.parents if p != root and root in p.parents)
    if remaining:
        manifest["harnesses"] = remaining
        manifest["files"] = {p: digest for p, digest in manifest["files"].items() if p not in remove}
        _write_manifest(root, manifest)
    else:
        _safe_path(root, MANIFEST, manifest=True).unlink()
    for path in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass  # Unknown user files are deliberately preserved.
    return {"action": "uninstall", "project": str(root), "removed_files": len(remove), "remaining_harnesses": remaining}


def _command(args: argparse.Namespace) -> int:
    try:
        fn = {"install": install, "reinstall": install, "check": check, "uninstall": uninstall}[args.command]
        result = fn(args.project, args.harness)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok", True) else 2
    except (InstallationError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


def register_cli(subparsers: Any) -> None:
    for action in ("install", "reinstall", "check", "uninstall"):
        parser = subparsers.add_parser(action, help=f"{action} project Agent Skills")
        parser.add_argument("--project", required=True, help="Existing project directory")
        parser.add_argument("--harness", action="append", choices=[*HARNESSES, "all", "deepseek"], help="Repeat to select harnesses; default: all")
        parser.set_defaults(func=_command, handler=_command)
