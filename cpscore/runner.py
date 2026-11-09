"""Bounded, non-root container execution. There is deliberately no host fallback.

Only the container CLI runs on the host. Source parsing, compilation, and all
submitted programs run in a networkless container with no writable host mount.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import errno
import json
import math
import os
from pathlib import Path
import platform
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from typing import Any
import uuid


DEFAULT_IMAGE = "cpscore-runner:local"
SOURCE_LIMIT = 16 * 1024 * 1024
ARTIFACT_LIMIT = 64 * 1024 * 1024

# Verify effective kernel restrictions, not merely the requested CLI flags.
# Unsupported/unreadable cgroups are a failed probe, never an invitation to run
# without a memory, process or CPU bound. cgroup v1 and v2 are both supported.
ISOLATION_PROBE = r'''
import errno, json, os, pathlib, platform, subprocess, sys
limits = json.loads(sys.argv[1])
assert os.getuid() == 65534 and os.getgid() == 65534, 'non-root UID/GID missing'
status = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert status.get('NoNewPrivs', '').strip() == '1', 'no_new_privileges missing'
for field in ('CapEff', 'CapPrm', 'CapBnd'):
    assert int(status[field].strip(), 16) == 0, 'capabilities remain: ' + field
mounts = [line.split() for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines()]
assert any(row[4] == '/' and 'ro' in row[5].split(',') for row in mounts), 'root mount is not read-only'
interfaces = sorted(os.listdir('/sys/class/net'))
assert all(name == 'lo' for name in interfaces), 'external network interface present'
cgroups = {}
for line in pathlib.Path('/proc/self/cgroup').read_text().splitlines():
    _, controllers, path = line.split(':', 2)
    for controller in controllers.split(','):
        cgroups[controller] = path.lstrip('/')
root = pathlib.Path('/sys/fs/cgroup')
def read_limit(controller, filename):
    base = root if controller == '' else root / controller
    paths = [base / cgroups.get(controller, '') / filename, base / filename]
    for path in paths:
        if path.is_file():
            return path.read_text().strip(), str(path)
    raise AssertionError('cannot verify cgroup bound: ' + filename)
if (root / 'cgroup.controllers').exists():
    memory, memory_path = read_limit('', 'memory.max')
    pids, pids_path = read_limit('', 'pids.max')
    cpu, cpu_path = read_limit('', 'cpu.max')
    quota, period = cpu.split()
    swap, swap_path = read_limit('', 'memory.swap.max')
    assert swap != 'max' and int(swap) == 0, 'swap is not disabled'
    version = 2
else:
    memory, memory_path = read_limit('memory', 'memory.limit_in_bytes')
    pids, pids_path = read_limit('pids', 'pids.max')
    quota, cpu_path = read_limit('cpu', 'cpu.cfs_quota_us')
    period, _ = read_limit('cpu', 'cpu.cfs_period_us')
    swaps = pathlib.Path('/proc/swaps').read_text().splitlines()[1:]
    if swaps:
        memsw, _ = read_limit('memory', 'memory.memsw.limit_in_bytes')
        assert int(memsw) <= limits['memory_mib'] * 1024 * 1024, 'memory+swap bound missing'
    version = 1
assert memory != 'max' and 0 < int(memory) <= limits['memory_mib'] * 1024 * 1024, 'memory bound missing or too high'
assert pids != 'max' and 0 < int(pids) <= limits['pids'], 'pids bound missing or too high'
assert quota != 'max' and 0 < int(quota) <= limits['cpus'] * int(period) + 1, 'CPU quota missing or too high'
subprocess.run(['g++', '-std=c++17', '-O2', '-x', 'c++', '-', '-o', '/work/compiler-probe'],
    input=b'int main(){return 0;}\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
subprocess.run(['/work/compiler-probe'], check=True)
print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
    'machine': platform.machine(), 'kernel': platform.release(),
    'cpu_model': next((line.split(':',1)[1].strip() for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if line.startswith(('model name','Hardware'))), 'unknown'),
    'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
    'effective_isolation': {'uid': os.getuid(), 'no_new_privileges': True, 'root_readonly': True,
        'network_interfaces': interfaces, 'capabilities': 0, 'cgroup_version': version,
        'memory_bytes': int(memory), 'pids': int(pids), 'cpu_quota': int(quota), 'cpu_period': int(period),
        'memory_path': memory_path, 'pids_path': pids_path, 'cpu_path': cpu_path}}))
'''


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 2.0
    memory_mib: int = 256
    cpus: float = 1.0
    pids: int = 64
    output_bytes: int = 1024 * 1024
    scratch_mib: int = 128

    def __post_init__(self) -> None:
        if not math.isfinite(self.wall_seconds) or self.wall_seconds <= 0:
            raise ValueError("wall_seconds must be finite and positive")
        if not math.isfinite(self.cpus) or self.cpus <= 0:
            raise ValueError("cpus must be finite and positive")
        for name in ("memory_mib", "pids", "output_bytes", "scratch_mib"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass
class ExecutionResult:
    status: str
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    wall_seconds: float = 0.0
    detail: str = ""
    output_truncated: bool = False
    # Attach/start timing includes container startup and collection overhead.
    timing_scope: str = "container attach wall time, including startup overhead"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_output: bool = True) -> dict[str, Any]:
        result = {
            "status": self.status,
            "exit_code": self.exit_code,
            "wall_seconds": round(self.wall_seconds, 6),
            "timing_scope": self.timing_scope,
            "detail": self.detail,
            "output_truncated": self.output_truncated,
            "stdout_bytes": len(self.stdout),
            "stderr_bytes": len(self.stderr),
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest(),
            "metadata": self.metadata,
        }
        if include_output:
            result["stdout"] = self.stdout.decode("utf-8", "replace")
            result["stderr"] = self.stderr.decode("utf-8", "replace")
        return result


@dataclass
class PreparedProgram:
    source: Path
    language: str
    source_sha256: str
    mount_directory: Path
    command: list[str]
    role: str
    compilation: ExecutionResult


def _bounded_process(command: list[str], *, stdin: bytes = b"", timeout: float,
                     output_bytes: int) -> ExecutionResult:
    """Capture both pipes without communicate()'s unbounded output buffering.

    This executes trusted container-engine commands only. Killing an attach
    client is insufficient to kill a container: SandboxRunner also force-removes
    the named container in its finally block.
    """
    started = time.monotonic()
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError as exc:
        return ExecutionResult("sandbox_error", detail=f"Cannot launch container engine: {exc}")
    stdout = bytearray()
    stderr = bytearray()
    selector = selectors.DefaultSelector()
    assert process.stdin and process.stdout and process.stderr
    streams = [process.stdin, process.stdout, process.stderr]
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
    selector.register(process.stdout, selectors.EVENT_READ, stdout)
    selector.register(process.stderr, selectors.EVENT_READ, stderr)
    if stdin:
        selector.register(process.stdin, selectors.EVENT_WRITE, None)
    else:
        process.stdin.close()
    offset = 0
    status = "ok"
    detail = ""
    truncated = False
    try:
        while selector.get_map():
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                status = "timeout"
                break
            for key, _ in selector.select(min(remaining, 0.1)):
                stream = key.fileobj
                if key.events == selectors.EVENT_WRITE:
                    try:
                        offset += os.write(stream.fileno(), stdin[offset:offset + 65536])
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        if exc.errno == errno.EPIPE:
                            offset = len(stdin)
                        else:
                            status = "sandbox_error"
                            detail = f"Cannot deliver container stdin: {exc}"
                            break
                    if offset == len(stdin):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        block = os.read(stream.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    except OSError as exc:
                        status = "sandbox_error"
                        detail = f"Cannot collect container output: {exc}"
                        break
                    if not block:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    capacity = output_bytes - len(stdout) - len(stderr)
                    key.data.extend(block[:max(0, capacity)])
                    if len(block) > capacity:
                        status = "output_limit"
                        truncated = True
                        break
            if status != "ok":
                break
        if status == "ok":
            try:
                process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                status = "timeout"
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        selector.close()
        for stream in streams:
            if not stream.closed:
                stream.close()
    if status == "ok" and process.returncode:
        status = "nonzero_exit"
    return ExecutionResult(status, bytes(stdout), bytes(stderr), process.returncode,
                           time.monotonic() - started, detail=detail, output_truncated=truncated,
                           timing_scope="host container-engine command wall time")


class SandboxRunner:
    """Manage disposable Docker/Podman containers and immutable program mounts.

    Images must already exist locally. A pinned image ID is used after discovery,
    so checking or running a program never implicitly pulls an image.
    """

    def __init__(self, *, engine: str = "auto", image: str = DEFAULT_IMAGE,
                 limits: Limits | None = None, compile_seconds: float = 30.0) -> None:
        if engine not in ("auto", "docker", "podman"):
            raise ValueError("engine must be auto, docker, or podman")
        if not math.isfinite(compile_seconds) or compile_seconds <= 0:
            raise ValueError("compile_seconds must be finite and positive")
        self.requested_engine = engine
        self.image = image
        self.limits = limits or Limits()
        self.compile_seconds = compile_seconds
        self.engine: str | None = None
        self.image_id: str | None = None
        self._availability: ExecutionResult | None = None
        self._environment: dict[str, Any] = {}
        self._temporary = tempfile.TemporaryDirectory(prefix="cpscore-")
        self._root = Path(self._temporary.name)
        self._containers: set[str] = set()

    def __enter__(self) -> "SandboxRunner":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        for name in list(self._containers):
            self._remove(name)
        self._temporary.cleanup()

    def _engine_command(self, arguments: list[str], *, timeout: float = 5.0,
                        output_bytes: int = 1024 * 1024) -> ExecutionResult:
        if not self.engine:
            return ExecutionResult("unavailable", detail="No container engine selected")
        return _bounded_process([self.engine, *arguments], timeout=timeout,
                                output_bytes=output_bytes)

    def availability(self) -> ExecutionResult:
        if self._availability is not None:
            return self._availability
        if os.name != "posix":
            self._availability = ExecutionResult("unavailable", detail="Native Windows pipe/process isolation is unsupported; use Linux or WSL2. No host fallback.")
            return self._availability
        reasons = []
        engines = ("docker", "podman") if self.requested_engine == "auto" else (self.requested_engine,)
        for name in engines:
            executable = shutil.which(name)
            if not executable:
                reasons.append(f"{name}: executable not found")
                continue
            self.engine = executable
            info = self._engine_command(["info", "--format", "{{json .}}"])
            if info.status != "ok":
                reasons.append(f"{name}: daemon unavailable ({info.status}): "
                               + info.stderr.decode("utf-8", "replace")[:1000])
                continue
            try:
                engine_info = json.loads(info.stdout)
                host_info = engine_info.get("host", {})
                os_type = engine_info.get("OSType", host_info.get("os", ""))
                if os_type.lower() != "linux":
                    raise ValueError("A Linux container engine is required")
            except (ValueError, TypeError, AttributeError) as exc:
                reasons.append(f"{name}: cannot verify Linux engine: {exc}")
                continue
            inspected = self._engine_command(["image", "inspect", "--format", "{{.Id}}", self.image])
            image_id = inspected.stdout.decode("utf-8", "replace").strip()
            if inspected.status != "ok" or not image_id or "\n" in image_id:
                reasons.append(f"{name}: local image {self.image!r} unavailable; build Dockerfile.runner explicitly")
                continue
            self.image_id = image_id
            self._environment = {
                "host": {"system": platform.system(), "release": platform.release(),
                         "machine": platform.machine(), "python": platform.python_version(),
                         "logical_cpus": os.cpu_count(),
                         "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None},
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "engine": name,
                "engine_version": engine_info.get("ServerVersion", engine_info.get("version")),
                "engine_security_options": engine_info.get("SecurityOptions", host_info.get("security")),
                "image": self.image,
                "image_id": image_id,
                "limits": asdict(self.limits),
                "compile_seconds": self.compile_seconds,
                "isolation": {"network": "none", "read_only_root": True, "uid": 65534,
                              "gid": 65534, "capabilities": "dropped", "no_new_privileges": True,
                              "writable_host_mounts": False},
            }
            # An actual container must start successfully under every requested
            # restriction. Missing cgroup/security support is never downgraded.
            probe = self._execute(["python3", "-I", "-c", ISOLATION_PROBE, json.dumps(asdict(self.limits))], b"", None,
                                  Limits(wall_seconds=10, memory_mib=self.limits.memory_mib,
                                         cpus=self.limits.cpus, pids=self.limits.pids,
                                         output_bytes=65536, scratch_mib=self.limits.scratch_mib))
            if probe.status != "ok":
                reasons.append(f"{name}: restricted container probe failed ({probe.status}): "
                               + (probe.detail or probe.stderr.decode("utf-8", "replace"))[:1000])
                continue
            try:
                self._environment["container"] = json.loads(probe.stdout)
            except (ValueError, TypeError):
                reasons.append(f"{name}: runner image did not produce valid probe output")
                continue
            self._availability = ExecutionResult("ok", detail="Restricted container probe succeeded",
                                                 metadata=self._environment)
            return self._availability
        self.engine = None
        self.image_id = None
        self._availability = ExecutionResult("unavailable", detail="; ".join(reasons),
                                             metadata={"host_system": platform.system(),
                                                       "host_execution_fallback": False})
        return self._availability

    def environment(self) -> dict[str, Any]:
        available = self.availability()
        return dict(self._environment) if available.status == "ok" else available.to_dict(include_output=False)

    def _remove(self, name: str) -> bool:
        removed = self._engine_command(["rm", "--force", name])
        diagnostic = removed.stderr.decode("utf-8", "replace").lower()
        absent = "no such container" in diagnostic or "no container with name or id" in diagnostic
        if removed.status == "ok" or absent:
            self._containers.discard(name)
            return True
        return False

    def _execute(self, command: list[str], stdin: bytes, mount: Path | None,
                 limits: Limits) -> ExecutionResult:
        if not self.engine or not self.image_id:
            return ExecutionResult("unavailable", detail="No verified container engine/image")
        if mount is not None and "," in str(mount):
            return ExecutionResult("sandbox_error", detail="A comma in the temporary mount path is unsupported; choose another TMPDIR")
        name = "cpscore-" + uuid.uuid4().hex
        args = ["create", "--pull=never", "--name", name, "--label", "org.cpscore.managed=true",
                "--network", "none", "--read-only",
                "--user", "65534:65534", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", str(limits.pids), "--cpus", str(limits.cpus),
                "--memory", f"{limits.memory_mib}m", "--memory-swap", f"{limits.memory_mib}m",
                "--ulimit", "nofile=128:128", "--ulimit", f"fsize={ARTIFACT_LIMIT}:{ARTIFACT_LIMIT}",
                "--tmpfs", f"/work:rw,exec,nosuid,nodev,size={limits.scratch_mib}m,mode=1777",
                "--tmpfs", f"/tmp:rw,nosuid,nodev,noexec,size={limits.scratch_mib}m,mode=1777",
                "--workdir", "/work", "--env", "HOME=/work", "--env", "TMPDIR=/tmp",
                "--env", "LC_ALL=C", "--interactive"]
        if mount:
            args += ["--mount", f"type=bind,source={mount},target=/source,readonly"]
        # Ignore image ENTRYPOINT; only the explicit argv below may execute.
        args += ["--entrypoint", command[0], self.image_id, *command[1:]]
        self._containers.add(name)
        result: ExecutionResult | None = None
        try:
            created = self._engine_command(args, timeout=10)
            if created.status != "ok":
                result = ExecutionResult("sandbox_error", stderr=created.stderr,
                                         detail="Container creation failed; requested restrictions were not relaxed")
                if created.status == "timeout":
                    # A daemon may finish a create request after its client was
                    # killed. No program is started, but report the unique name
                    # rather than claiming this remote race is fully resolved.
                    result.metadata["creation_completion_uncertain"] = name
                    result.detail = "Container creation timed out; forced removal was attempted, but late daemon completion is possible. Check " + name
                return result
            attached = _bounded_process([self.engine, "start", "--attach", "--interactive", name],
                                        stdin=stdin, timeout=limits.wall_seconds,
                                        output_bytes=limits.output_bytes)
            attached.timing_scope = "container attach wall time, including startup overhead"
            result = attached
            if attached.status in ("timeout", "output_limit"):
                # This is the killed attach client's exit code, not an observed
                # program exit. Forced removal below terminates the container.
                attached.metadata["engine_client_exit_code"] = attached.exit_code
                attached.metadata["container_exit_observed"] = False
                attached.exit_code = None
                attached.detail = "Wall limit reached" if attached.status == "timeout" else "Combined stdout/stderr limit reached"
                return attached
            state_result = self._engine_command(["inspect", "--format", "{{json .State}}", name])
            try:
                if state_result.status != "ok":
                    raise ValueError("container state inspection failed")
                state = json.loads(state_result.stdout)
                if state.get("Error") or state.get("Running") or state.get("Status") not in ("exited", "stopped"):
                    raise ValueError(str(state.get("Error") or "container did not exit normally"))
                code = state["ExitCode"]
                if not isinstance(code, int):
                    raise ValueError("missing integer container exit code")
                client_exit_code = attached.exit_code
                attached.exit_code = code
                if attached.status == "sandbox_error" or client_exit_code != code:
                    attached.metadata["client_exit_code"] = client_exit_code
                    raise ValueError("attach client exit status does not agree with container exit status")
                if state.get("OOMKilled"):
                    attached.status = "memory_limit"
                    attached.detail = "Container memory limit reached"
                else:
                    attached.status = "ok" if code == 0 else "nonzero_exit"
            except (ValueError, TypeError, KeyError) as exc:
                attached.status = "sandbox_error"
                attached.detail = f"Cannot establish program exit status: {exc}"
            return attached
        finally:
            if result is not None:
                result.metadata["limits"] = asdict(limits)
            if not self._remove(name) and result is not None:
                # Never silently report a successful check while cleanup failed.
                result.metadata["cleanup_failed"] = name
                result.status = "sandbox_error"
                result.detail = "Could not confirm forced container removal; check the engine and remove " + name

    def prepare(self, source: str | Path, language: str | None = None,
                *, role: str = "candidate") -> tuple[PreparedProgram | None, ExecutionResult]:
        available = self.availability()
        if available.status != "ok":
            return None, available
        path = Path(source).resolve()
        language = language or ({".py": "python", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp"}.get(path.suffix.lower()))
        if language not in ("cpp", "python"):
            return None, ExecutionResult("config_error", detail=f"Unsupported language for {path}; choose cpp or python")
        try:
            with path.open("rb") as handle:
                data = handle.read(SOURCE_LIMIT + 1)
            if len(data) > SOURCE_LIMIT:
                raise ValueError(f"Source exceeds {SOURCE_LIMIT} bytes")
        except (OSError, ValueError) as exc:
            return None, ExecutionResult("config_error", detail=f"Cannot read {role} source: {exc}")
        directory = self._root / uuid.uuid4().hex
        directory.mkdir(mode=0o755)
        name = "program.cpp" if language == "cpp" else "program.py"
        source_copy = directory / name
        source_copy.write_bytes(data)
        source_copy.chmod(0o444)
        compile_limits = Limits(wall_seconds=self.compile_seconds, memory_mib=max(1024, self.limits.memory_mib),
                                cpus=self.limits.cpus, pids=max(64, self.limits.pids),
                                output_bytes=ARTIFACT_LIMIT + 131072, scratch_mib=max(256, self.limits.scratch_mib))
        if language == "cpp":
            # Return a bounded executable through stdout. Compilation never gets
            # a writable host mount or executes the newly compiled program.
            command = ["/bin/sh", "-c", "g++ -std=c++17 -O2 -pipe /source/program.cpp -o /work/program && cat /work/program"]
        else:
            command = ["python3", "-I", "-c", "compile(open('/source/program.py','rb').read(), '/source/program.py', 'exec')"]
        compiled = self._execute(command, b"", directory, compile_limits)
        if compiled.status != "ok":
            return None, compiled
        if language == "cpp":
            binary = compiled.stdout
            if not binary.startswith(b"\x7fELF") or len(binary) > ARTIFACT_LIMIT:
                return None, ExecutionResult("sandbox_error", stderr=compiled.stderr,
                                              detail="Compiler did not return a bounded Linux ELF executable")
            executable = directory / "program"
            executable.write_bytes(binary)
            executable.chmod(0o555)
            compiled.metadata["artifact_sha256"] = hashlib.sha256(binary).hexdigest()
            compiled.metadata["artifact_bytes"] = len(binary)
            compiled.stdout = b""
            run_command = ["/source/program"]
        else:
            run_command = ["python3", "-I", "-B", "/source/program.py"]
        compiled.metadata["limits"] = asdict(compile_limits)
        program = PreparedProgram(path, language, hashlib.sha256(data).hexdigest(), directory,
                                  run_command, role, compiled)
        return program, compiled

    def run(self, program: PreparedProgram, stdin: bytes, *, arguments: list[str] | None = None,
            limits: Limits | None = None) -> ExecutionResult:
        available = self.availability()
        if available.status != "ok":
            return available
        return self._execute([*program.command, *(arguments or [])], stdin,
                             program.mount_directory, limits or self.limits)
