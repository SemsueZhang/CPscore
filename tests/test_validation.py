"""Mock unit tests and explicitly opt-in real container integration tests.

No candidate fixture is run on the host. Mock tests exercise classification and
evidence plumbing; only SandboxIntegrationTests provide real isolation evidence.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from cpscore.runner import ExecutionResult, Limits, PreparedProgram, SandboxRunner, _bounded_process
from cpscore.validation import CheckConfig, Comparison, benchmark, check_candidate, compare_outputs


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "validation"


class FakeRunner:
    """Simulated tool results only; does not compile or execute source code."""

    def __init__(self, root: Path, *, failures=None, results=None):
        self.root = root
        self.failures = failures or {}
        self.results = results or {}
        self.calls = []

    def availability(self):
        return ExecutionResult("ok")

    def prepare(self, path, language=None, *, role="candidate"):
        self.calls.append(("prepare", role))
        if role in self.failures:
            return None, self.failures[role]
        path = Path(path).resolve()
        language = language or ("cpp" if path.suffix == ".cpp" else "python")
        directory = self.root / role
        directory.mkdir(exist_ok=True)
        data = path.read_bytes()
        (directory / ("program.cpp" if language == "cpp" else "program.py")).write_bytes(data)
        compilation = ExecutionResult("ok")
        return PreparedProgram(path, language, hashlib.sha256(data).hexdigest(), directory,
                               ["simulated"], role, compilation), compilation

    def run(self, program, stdin, *, arguments=None, limits=None):
        self.calls.append(("run", program.role, stdin, arguments))
        result = self.results.get(program.role)
        if callable(result):
            return result(program, stdin, arguments)
        if isinstance(result, list):
            return result.pop(0)
        if result is not None:
            return result
        if program.role == "validator":
            return ExecutionResult("ok", wall_seconds=0.01)
        if program.role == "generator":
            return ExecutionResult("ok", stdout=(FIXTURES / "sample.in").read_bytes(), wall_seconds=0.01)
        return ExecutionResult("ok", stdout=b"-4\n", wall_seconds=0.01)

    def environment(self):
        return {"engine": "docker", "image_id": "sha256:mock", "mock": True, "limits": {}}

    def close(self):
        pass


class ComparisonTests(unittest.TestCase):
    def test_exact_is_byte_exact_by_default(self):
        self.assertEqual(compare_outputs(b"1\n", b"1\n")["status"], "match")
        self.assertEqual(compare_outputs(b"1 ", b"1\n")["status"], "mismatch")
        self.assertEqual(compare_outputs(b"\xff", b"\xfe")["status"], "mismatch")

    def test_tokens_require_explicit_policy(self):
        self.assertEqual(compare_outputs(b"1  \n2", b"1\t2\n", Comparison("tokens"))["status"], "match")
        self.assertEqual(compare_outputs(b"01", b"1", Comparison("tokens"))["status"], "mismatch")

    def test_float_requires_finite_explicit_tolerances(self):
        for args in (("float",), ("float", -1, 0), ("float", 0, float("inf")), ("exact", 0, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Comparison(*args)
        policy = Comparison("float", 0.01, 0)
        self.assertEqual(compare_outputs(b"1.005", b"1", policy)["status"], "match")
        self.assertEqual(compare_outputs(b"1.02", b"1", policy)["status"], "mismatch")
        self.assertEqual(compare_outputs(b"nan", b"1", policy)["status"], "mismatch")
        self.assertEqual(compare_outputs(b"1_0", b"10", policy)["status"], "mismatch")
        self.assertEqual(compare_outputs(b"+1.0e+1", b"10", policy)["status"], "match")
        for expected in (b"nan", b"inf", b"answer=1", b"1_0"):
            self.assertEqual(compare_outputs(b"1", expected, policy)["status"], "reference_error")


class ValidationUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = CheckConfig(candidate=FIXTURES / "correct.py", inputs=[FIXTURES / "sample.in"],
                                  oracle=FIXTURES / "oracle.py", validator=FIXTURES / "validator.py",
                                  save_dir=self.root / "evidence")

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, **kwargs):
        return FakeRunner(self.root, **kwargs)

    def test_match_is_finite_evidence_with_no_score_effect(self):
        result = check_candidate(self.config, runner=self.fake())
        self.assertEqual(result["counts"], {"match": 1})
        self.assertTrue(result["all_cases_matched"])
        self.assertEqual(result["score_effect"], "none")
        self.assertFalse(self.config.save_dir.exists())

    def test_verified_mismatch_saves_hashes_sources_outputs_and_replay(self):
        fake = self.fake(results={"candidate": ExecutionResult("ok", stdout=b"-3\n")})
        report = check_candidate(self.config, runner=fake)
        case = report["cases"][0]
        self.assertEqual(case["status"], "candidate_mismatch")
        manifest_path = Path(case["manifest"])
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue(manifest["validated_differential_mismatch"])
        self.assertEqual(manifest["oracle_correctness"], "assumed_requires_review")
        self.assertEqual(manifest["input"]["sha256"], hashlib.sha256((FIXTURES / "sample.in").read_bytes()).hexdigest())
        for role, source in manifest["sources"].items():
            copied = manifest_path.parent / source["saved_path"]
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), source["sha256"])
        self.assertEqual(manifest["replay_script"], "replay.py")
        replay_source = (manifest_path.parent / "replay.py").read_text()
        self.assertIn("--validator", replay_source)
        self.assertIn("--oracle", replay_source)
        self.assertEqual((manifest_path.parent / "candidate.stdout").read_bytes(), b"-3\n")

    def test_input_legality_and_successful_oracle_are_required_for_candidate_mismatch(self):
        config = replace(self.config, validator=None)
        report = check_candidate(config, runner=self.fake(results={"candidate": ExecutionResult("ok", stdout=b"wrong")}))
        self.assertEqual(report["cases"][0]["status"], "unverified_mismatch")
        self.assertFalse(json.loads(Path(report["cases"][0]["manifest"]).read_text())["validated_differential_mismatch"])

    def test_expected_file_mismatch_is_only_sample_evidence(self):
        config = replace(self.config, oracle=None, expected=[FIXTURES / "sample.out"])
        report = check_candidate(config, runner=self.fake(results={"candidate": ExecutionResult("ok", stdout=b"wrong")}))
        self.assertEqual(report["cases"][0]["status"], "sample_mismatch")

    def test_invalid_input_never_runs_candidate_or_oracle(self):
        fake = self.fake(results={"validator": ExecutionResult("nonzero_exit", exit_code=1)})
        report = check_candidate(self.config, runner=fake)
        self.assertEqual(report["cases"][0]["status"], "invalid_input")
        self.assertEqual([call[1] for call in fake.calls if call[0] == "run"], ["validator"])

    def test_tool_failures_never_become_algorithm_errors(self):
        for role in ("validator", "oracle", "generator"):
            with self.subTest(role=role):
                config = self.config
                if role == "generator":
                    config = replace(config, inputs=[], generator=FIXTURES / "generator.py", cases=1)
                fake = self.fake(results={role: ExecutionResult("timeout", detail="simulated failure")})
                result = check_candidate(config, runner=fake)
                self.assertEqual(result["cases"][0]["status"], "tool_error")
                self.assertNotIn("candidate", [call[1] for call in fake.calls if call[0] == "run"])

    def test_comparator_reference_failure_never_becomes_algorithm_error(self):
        config = replace(self.config, comparison=Comparison("float", 0, 0))
        result = check_candidate(config, runner=self.fake(results={"oracle": ExecutionResult("ok", stdout=b"nan")}))
        self.assertEqual(result["cases"][0]["status"], "tool_error")
        self.assertEqual(result["cases"][0]["role"], "comparator/reference")

    def test_candidate_engine_failure_is_infrastructure_failure(self):
        result = check_candidate(self.config, runner=self.fake(results={"candidate": ExecutionResult("sandbox_error")}))
        self.assertEqual(result["cases"][0]["status"], "tool_error")

    def test_candidate_timeout_is_observation_not_a_tle_or_score_change(self):
        result = check_candidate(self.config, runner=self.fake(results={"candidate": ExecutionResult("timeout")}))
        self.assertEqual(result["cases"][0]["status"], "candidate_execution_failure")
        self.assertEqual(result["score_effect"], "none")

    def test_tool_compilation_failure_and_candidate_compilation_failure_differ(self):
        for role in ("oracle", "candidate"):
            with self.subTest(role=role):
                result = check_candidate(self.config, runner=self.fake(failures={role: ExecutionResult("nonzero_exit", exit_code=1)}))
                self.assertEqual(result["status"], "candidate_compile_error" if role == "candidate" else "tool_error")

    def test_fixed_seed_and_case_index_are_passed_as_argv(self):
        config = replace(self.config, inputs=[], generator=FIXTURES / "generator.py", cases=2, seed=738, start_case=5)
        fake = self.fake()
        report = check_candidate(config, runner=fake)
        args = [call[3] for call in fake.calls if call[:2] == ("run", "generator")]
        self.assertEqual(args, [["738", "5"], ["738", "6"]])
        self.assertEqual(report["counts"], {"match": 2})

    def test_generated_inputs_require_validator_and_oracle(self):
        for config in (replace(self.config, generator=FIXTURES / "generator.py", validator=None),
                       replace(self.config, oracle=None, expected=[FIXTURES / "sample.out"], generator=FIXTURES / "generator.py")):
            fake = self.fake()
            self.assertEqual(check_candidate(config, runner=fake)["status"], "config_error")
            self.assertEqual(fake.calls, [])

    def test_unavailable_stops_before_preparation(self):
        fake = self.fake()
        fake.availability = lambda: ExecutionResult("unavailable", detail="simulated missing daemon")
        result = check_candidate(self.config, runner=fake)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(fake.calls, [])

    def test_benchmark_records_environment_samples_and_timing_scope(self):
        fake = self.fake(results={"candidate": [ExecutionResult("ok", wall_seconds=value) for value in (0.9, 0.3, 0.1, 0.2)]})
        result = benchmark(self.config.candidate, self.config.inputs, repetitions=3, warmups=1,
                           validator=self.config.validator, runner=fake)
        record = result["inputs"][0]
        self.assertEqual(record["status"], "measured")
        self.assertEqual(record["median_wall_seconds"], 0.2)
        self.assertEqual(len(record["warmup_runs"]), 1)
        self.assertTrue(result["environment"]["mock"])
        self.assertIn("startup", result["timing_scope"])

    def test_replay_imports_bootstrap_runtime_without_pip_after_evidence_move(self):
        # Simulate a skill bootstrap whose runtime is injected into sys.path,
        # rather than installed in the interpreter's site-packages.
        runtime_root = self.root / "installed runtime with spaces"
        runtime_root.mkdir()
        shutil.copytree(Path(__file__).resolve().parents[1] / "cpscore", runtime_root / "cpscore",
                        ignore=shutil.ignore_patterns("__pycache__"))
        fake_module = runtime_root / "cpscore" / "validation.py"
        with mock.patch("cpscore.validation.__file__", str(fake_module)):
            report = check_candidate(self.config, runner=self.fake(results={"candidate": ExecutionResult("ok", stdout=b"wrong")}))
        manifest_path = Path(report["cases"][0]["manifest"])
        moved = self.root / "relocated evidence"
        shutil.move(str(manifest_path.parent), moved)
        elsewhere = self.root / "unrelated-cwd"
        elsewhere.mkdir()
        result = subprocess.run([sys.executable, "-I", str(moved / "replay.py"), "--help"],
                                cwd=elsewhere, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"check-candidate", result.stdout)
        self.assertIn("@EVIDENCE@/input.bin", (moved / "replay.py").read_text())


class RunnerUnitTests(unittest.TestCase):
    def test_invalid_limits_fail_closed(self):
        for values in ({"wall_seconds": 0}, {"wall_seconds": float("nan")}, {"cpus": float("inf")},
                       {"pids": 0}, {"memory_mib": -1}, {"output_bytes": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Limits(**values)

    def test_no_engine_means_unavailable_without_launch(self):
        with SandboxRunner() as runner, mock.patch("cpscore.runner.shutil.which", return_value=None), \
                mock.patch("cpscore.runner._bounded_process") as process:
            self.assertEqual(runner.availability().status, "unavailable")
            program, result = runner.prepare(FIXTURES / "correct.py")
            self.assertIsNone(program)
            self.assertEqual(result.status, "unavailable")
            process.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX trusted-pipe unit test")
    def test_host_capture_of_trusted_constant_commands_is_bounded(self):
        # These are trusted, fixed pipe-test commands, not user submissions.
        flood = _bounded_process([sys.executable, "-c", "import os;os.write(1,b'x'*200000)"],
                                 timeout=3, output_bytes=1000)
        self.assertEqual(flood.status, "output_limit")
        self.assertLessEqual(len(flood.stdout) + len(flood.stderr), 1000)
        self.assertTrue(flood.output_truncated)
        sleeping = _bounded_process([sys.executable, "-c", "import time;time.sleep(2)"],
                                    timeout=0.1, output_bytes=1000)
        self.assertEqual(sleeping.status, "timeout")

    def execute_with_engine_results(self, results):
        runner = SandboxRunner()
        runner.engine = "/mock/docker"
        runner.image_id = "sha256:mock"
        with mock.patch("cpscore.runner._bounded_process", side_effect=results) as process:
            result = runner._execute(["python3", "-V"], b"", None, Limits())
        runner.close()
        return result, process

    def test_restrictions_are_not_relaxed_and_client_failure_is_not_program_success(self):
        state = ExecutionResult("ok", stdout=json.dumps({"Status": "exited", "Running": False,
                                                         "ExitCode": 0, "OOMKilled": False, "Error": ""}).encode())
        result, process = self.execute_with_engine_results([
            ExecutionResult("ok", stdout=b"id"), ExecutionResult("nonzero_exit", exit_code=125), state,
            ExecutionResult("ok")])
        self.assertEqual(result.status, "sandbox_error")
        create = process.call_args_list[0].args[0]
        for flag in ("--network", "--read-only", "--user", "--cap-drop", "--pids-limit", "--memory", "--cpus", "--pull=never"):
            self.assertIn(flag, create)
        self.assertNotIn("--privileged", create)
        work_tmpfs = next(value for value in create if value.startswith("/work:"))
        self.assertIn("exec", work_tmpfs.split(":", 1)[1].split(","))
        self.assertEqual(process.call_args_list[-1].args[0][1:3], ["rm", "--force"])

    def test_timeout_still_force_removes_container(self):
        result, process = self.execute_with_engine_results([ExecutionResult("ok"), ExecutionResult("timeout"), ExecutionResult("ok")])
        self.assertEqual(result.status, "timeout")
        self.assertEqual(process.call_args_list[-1].args[0][1:3], ["rm", "--force"])

    def test_cleanup_failure_prevents_success(self):
        runner = SandboxRunner()
        runner.engine = "/mock/docker"
        runner.image_id = "sha256:mock"
        state = ExecutionResult("ok", stdout=b'{"Status":"exited","ExitCode":0}')
        with mock.patch("cpscore.runner._bounded_process", side_effect=[ExecutionResult("ok"), ExecutionResult("ok", exit_code=0), state, ExecutionResult("timeout")]):
            result = runner._execute(["python3", "-V"], b"", None, Limits())
        self.assertEqual(result.status, "sandbox_error")
        self.assertIn("cleanup_failed", result.metadata)
        with mock.patch.object(runner, "_remove", return_value=True):
            runner.close()


@unittest.skipUnless(os.environ.get("CPSCORE_RUN_SANDBOX_TESTS") == "1",
                     "real sandbox integration is opt-in; mocks are not integration evidence")
class SandboxIntegrationTests(unittest.TestCase):
    """Never skip unavailable isolation after the user explicitly opts in."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.runner = SandboxRunner(engine=os.environ.get("CPSCORE_SANDBOX_ENGINE", "auto"),
                                   image=os.environ.get("CPSCORE_SANDBOX_IMAGE", "cpscore-runner:local"),
                                   limits=Limits(wall_seconds=5))
        availability = cls.runner.availability()
        if availability.status != "ok":
            cls.runner.close()
            cls.temp.cleanup()
            raise AssertionError("Opt-in real integration requires available isolation: " + availability.detail)

    @classmethod
    def tearDownClass(cls):
        cls.runner.close()
        cls.temp.cleanup()

    def config(self, candidate="correct.py", **kwargs):
        return CheckConfig(candidate=FIXTURES / candidate, inputs=[FIXTURES / "sample.in"],
                           oracle=FIXTURES / "oracle.py", validator=FIXTURES / "validator.py",
                           save_dir=self.root / "counterexamples", limits=self.runner.limits,
                           image=self.runner.image, engine=self.runner.requested_engine, **kwargs)

    def test_real_correct_and_wrong_cpp_and_python_and_manifest_replay(self):
        for language in ("py", "cpp"):
            with self.subTest(language=language):
                correct = check_candidate(self.config("correct." + language), runner=self.runner)
                self.assertEqual(correct.get("counts"), {"match": 1}, correct)
                wrong = check_candidate(self.config("wrong." + language), runner=self.runner)
                self.assertEqual(wrong.get("counts"), {"candidate_mismatch": 1}, wrong)
                manifest = json.loads(Path(wrong["cases"][0]["manifest"]).read_text())
                self.assertTrue(manifest["validated_differential_mismatch"])
                replay = subprocess.run(manifest["replay_argv"], capture_output=True, timeout=120)
                self.assertEqual(replay.returncode, 1, replay.stderr.decode())
                self.assertEqual(json.loads(replay.stdout)["counts"], {"candidate_mismatch": 1})

    def test_real_seeded_generation_and_legal_differential_cases(self):
        config = replace(self.config(), inputs=[], generator=FIXTURES / "generator.py", seed=20261109, cases=2)
        first = check_candidate(config, runner=self.runner)
        second = check_candidate(config, runner=self.runner)
        self.assertEqual(first.get("counts"), {"match": 2}, first)
        self.assertEqual(second.get("counts"), {"match": 2}, second)
        self.assertEqual([case["input_sha256"] for case in first["cases"]],
                         [case["input_sha256"] for case in second["cases"]])

    def test_real_invalid_input_and_oracle_failure_are_not_candidate_errors(self):
        invalid = check_candidate(replace(self.config(), inputs=[FIXTURES / "invalid.in"]), runner=self.runner)
        self.assertEqual(invalid.get("counts"), {"invalid_input": 1}, invalid)
        broken = check_candidate(replace(self.config(), oracle=FIXTURES / "tool_failure.py"), runner=self.runner)
        self.assertEqual(broken.get("counts"), {"tool_error": 1}, broken)
        self.assertEqual(broken["cases"][0]["role"], "oracle")

    def test_real_compilation_timeout_output_limits_and_cleanup(self):
        broken = check_candidate(self.config("compile_error.cpp"), runner=self.runner)
        self.assertEqual(broken["status"], "candidate_compile_error", broken)
        for source, limits, expected in (("timeout.py", Limits(wall_seconds=1), "timeout"),
                                         ("output_flood.py", Limits(wall_seconds=5, output_bytes=4096), "output_limit")):
            program, compilation = self.runner.prepare(FIXTURES / source)
            self.assertEqual(compilation.status, "ok", compilation.to_dict())
            result = self.runner.run(program, b"", limits=limits)
            self.assertEqual(result.status, expected, result.to_dict())
            self.assertLessEqual(len(result.stdout) + len(result.stderr), limits.output_bytes)
        self.assertEqual(self.runner._containers, set(), "all containers must be removed")

    def test_real_effective_isolation_and_performance_observations(self):
        effective = self.runner.environment()["container"]["effective_isolation"]
        self.assertEqual(effective["uid"], 65534)
        self.assertTrue(effective["root_readonly"])
        self.assertLessEqual(effective["memory_bytes"], self.runner.limits.memory_mib * 1024 * 1024)
        self.assertEqual(effective["network_interfaces"], ["lo"])
        sentinel = self.root / "host-only-sentinel"
        sentinel.write_text("must not be readable inside the container")
        probe, compiled = self.runner.prepare(FIXTURES / "isolation_check.py")
        self.assertEqual(compiled.status, "ok")
        isolated = self.runner.run(probe, b"", arguments=[str(sentinel)])
        self.assertEqual(isolated.status, "ok", isolated.to_dict())
        self.assertEqual(isolated.stdout, b"isolated\n")
        report = benchmark(FIXTURES / "correct.cpp", [FIXTURES / "sample.in"], repetitions=2,
                           warmups=1, validator=FIXTURES / "validator.py", runner=self.runner)
        self.assertEqual(report["inputs"][0]["status"], "measured", report)
        self.assertIn("kernel", report["environment"]["container"])
        self.assertEqual(report["score_effect"], "none")


if __name__ == "__main__":
    unittest.main()
