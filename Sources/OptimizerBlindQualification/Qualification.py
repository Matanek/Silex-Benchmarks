#!/usr/bin/env python3
"""Audit the sealed Part 09 corpus and its native qualification reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
from typing import Any


REQUIRED_TARGETS = {
    "macos-arm64",
    "macos-x64",
    "linux-arm64",
    "linux-x64",
    "windows-arm64",
    "windows-x64",
}
REQUIRED_DOMAINS = {
    "physics-contact",
    "physics-integration",
    "physics-preparation",
    "collections-ownership",
    "integer-float",
    "ecs",
    "font-text",
    "scene2d",
    "scene3d",
    "json",
    "multi-package-application",
}
HEX = set("0123456789abcdef")


class QualificationError(ValueError):
    pass


def fail(message: str) -> None:
    raise QualificationError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_sha256(path: Path) -> str:
    return sha256(path)


def require_keys(value: dict[str, Any], keys: set[str], context: str) -> None:
    missing = keys - value.keys()
    if missing:
        fail(f"{context}: missing {', '.join(sorted(missing))}")


def require_hex(value: Any, length: int, context: str) -> str:
    if not isinstance(value, str) or len(value) != length or any(character not in HEX for character in value):
        fail(f"{context}: expected {length} lowercase hexadecimal characters")
    return value


def unique(values: list[Any], context: str) -> None:
    if len(values) != len(set(values)):
        fail(f"{context}: duplicate entries")


def run_checked(command: list[str], cwd: Path, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Run a bounded command and always terminate its complete process group."""
    creationflags = 0
    start_new_session = os.name != "nt"
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=start_new_session,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_process_tree(process)
        stdout, stderr = process.communicate()
        fail(f"command timed out after {timeout:g}s: {' '.join(command)}\n{stderr}")
    if process.returncode:
        fail(f"command failed ({process.returncode}): {' '.join(command)}\n{stderr}")
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def audit_manifest_shape(manifest: dict[str, Any]) -> None:
    require_keys(
        manifest,
        {
            "schema_version",
            "sealed",
            "sealed_before_candidate_observation",
            "owner_repository",
            "candidate",
            "compiler_baseline",
            "statistical_contract",
            "metrics",
            "targets",
            "required_domains",
            "native_matrix_cases",
            "semantic_test_cases",
            "performance_cases",
            "repositories",
            "cases",
        },
        "manifest",
    )
    if manifest["schema_version"] != 1 or manifest["sealed"] is not True:
        fail("manifest: unsupported schema or unsealed corpus")
    if manifest["sealed_before_candidate_observation"] is not True:
        fail("manifest: candidate-observation seal is absent")

    require_hex(manifest["candidate"].get("revision"), 40, "candidate revision")
    require_hex(manifest["compiler_baseline"].get("revision"), 40, "baseline revision")
    if manifest["candidate"]["revision"] == manifest["compiler_baseline"]["revision"]:
        fail("manifest: candidate and baseline revisions must differ")

    domains = manifest["required_domains"]
    if not isinstance(domains, list) or set(domains) != REQUIRED_DOMAINS:
        fail("manifest: required domain catalog differs from the Part 09 contract")
    unique(domains, "required domains")

    targets = manifest["targets"]
    target_ids = [target.get("id") for target in targets]
    if set(target_ids) != REQUIRED_TARGETS:
        fail("manifest: native target catalog differs from the six distributed targets")
    unique(target_ids, "targets")
    performance_architectures: set[str] = set()
    for target in targets:
        require_keys(target, {"id", "runner", "os", "architecture", "native", "performance"}, f"target {target.get('id')}")
        if target["native"] is not True:
            fail(f"target {target['id']}: non-native execution cannot qualify correctness")
        if target["performance"]:
            if target["architecture"] in {"arm64", "aarch64", "ARM64"}:
                performance_architectures.add("arm64")
            elif target["architecture"] in {"x86_64", "AMD64"}:
                performance_architectures.add("x64")
    if performance_architectures != {"arm64", "x64"}:
        fail("manifest: physical native ARM64 and X64 performance profiles are both required")

    contract = manifest["statistical_contract"]
    require_keys(
        contract,
        {
            "paired_samples",
            "warmups",
            "minimum_one_sided_confidence_ppm",
            "maximum_spread_ppm",
            "runtime_upper_bound_ppm",
            "non_runtime_upper_bound_ppm",
            "inconclusive_is_failure",
            "cross_compilation_is_performance_evidence",
            "emulation_is_performance_evidence",
        },
        "statistical contract",
    )
    if contract["paired_samples"] < 21 or contract["paired_samples"] % 2 == 0:
        fail("statistical contract: at least 21 odd paired samples are required")
    if contract["minimum_one_sided_confidence_ppm"] < 950000:
        fail("statistical contract: one-sided confidence is below 95%")
    if contract["maximum_spread_ppm"] != 200000:
        fail("statistical contract: dispersion must match the Part 07 200000 ppm gate")
    if contract["runtime_upper_bound_ppm"] != 1000000:
        fail("statistical contract: runtime must require parity or better")
    if contract["inconclusive_is_failure"] is not True:
        fail("statistical contract: an inconclusive result must fail")
    if contract["cross_compilation_is_performance_evidence"] is not False or contract["emulation_is_performance_evidence"] is not False:
        fail("statistical contract: cross-compilation or emulation cannot qualify performance")

    metric_ids = [metric.get("id") for metric in manifest["metrics"]]
    if set(metric_ids) != {"execution", "startup", "cold_compile", "warm_compile", "peak_rss", "binary_size"}:
        fail("manifest: required cost dimensions are incomplete")
    unique(metric_ids, "metrics")

    repositories = manifest["repositories"]
    names = [repository.get("name") for repository in repositories]
    unique(names, "repositories")
    if manifest["owner_repository"] not in names:
        fail("manifest: owner repository does not resolve to the closure")
    if manifest["candidate"]["repository"] not in names or manifest["compiler_baseline"]["repository"] not in names:
        fail("manifest: compiler revisions do not resolve to the closure")
    for repository in repositories:
        require_keys(repository, {"name", "path", "revision", "role"}, f"repository {repository.get('name')}")
        require_hex(repository["revision"], 40, f"repository {repository['name']} revision")

    cases = manifest["cases"]
    case_ids = [case.get("id") for case in cases]
    unique(case_ids, "cases")
    repository_names = set(names)
    covered_domains: set[str] = set()
    for case in cases:
        require_keys(
            case,
            {"id", "domains", "repository", "source", "sha256", "entry", "workload", "oracle", "signature", "performance_reference"},
            f"case {case.get('id')}",
        )
        if case["repository"] not in repository_names:
            fail(f"case {case['id']}: unknown repository {case['repository']}")
        require_hex(case["sha256"], 64, f"case {case['id']} source hash")
        if not case["domains"] or not set(case["domains"]).issubset(REQUIRED_DOMAINS):
            fail(f"case {case['id']}: empty or unknown domain list")
        covered_domains.update(case["domains"])
    if covered_domains != REQUIRED_DOMAINS:
        fail(f"manifest: uncovered domains: {', '.join(sorted(REQUIRED_DOMAINS - covered_domains))}")
    for catalog in ("native_matrix_cases", "semantic_test_cases", "performance_cases"):
        values = manifest[catalog]
        unique(values, catalog)
        unknown = set(values) - set(case_ids)
        if unknown:
            fail(f"manifest: {catalog} contains unknown cases: {', '.join(sorted(unknown))}")
    matrix_cases = set(manifest["native_matrix_cases"])
    semantic_cases = set(manifest["semantic_test_cases"])
    if matrix_cases & semantic_cases or matrix_cases | semantic_cases != set(case_ids):
        fail("manifest: native and test case catalogs must be a disjoint cover of the corpus")
    for sentinel in ("boids2d-full", "falling-bodies2d-full"):
        if sentinel not in manifest["native_matrix_cases"] or sentinel not in manifest["performance_cases"]:
            fail(f"manifest: full sentinel {sentinel} is not blocking")


def audit_workspace(manifest: dict[str, Any], workspace: Path, silex: Path | None) -> None:
    workspace = workspace.resolve()
    repositories = {repository["name"]: repository for repository in manifest["repositories"]}
    for repository in repositories.values():
        root = (workspace / repository["path"]).resolve()
        if not root.is_relative_to(workspace) or not root.is_dir():
            fail(f"repository {repository['name']}: missing or outside workspace: {root}")
        actual = run_checked(["git", "rev-parse", "HEAD"], root).stdout.strip()
        if repository["name"] == manifest["owner_repository"]:
            # The manifest and runner necessarily live in a descendant commit
            # of the pre-existing consumer sources they seal. Source hashes
            # below forbid that descendant from changing any selected input.
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", repository["revision"], actual],
                cwd=root,
                check=False,
            )
            if result.returncode:
                fail(f"repository {repository['name']}: sealed source revision is not an ancestor of HEAD {actual}")
        elif actual != repository["revision"]:
            fail(f"repository {repository['name']}: HEAD {actual} != sealed {repository['revision']}")

    for case in manifest["cases"]:
        repository = repositories[case["repository"]]
        source = (workspace / repository["path"] / case["source"]).resolve()
        repository_root = (workspace / repository["path"]).resolve()
        if not source.is_relative_to(repository_root) or not source.is_file():
            fail(f"case {case['id']}: missing or escaping source {source}")
        actual = sha256(source)
        if actual != case["sha256"]:
            fail(f"case {case['id']}: source hash {actual} != sealed {case['sha256']}")

    if silex is None:
        return
    executable = silex.resolve()
    if not executable.is_file():
        fail(f"silex executable does not exist: {executable}")
    result = run_checked([str(executable), "packages", "resolve", "Silex-Benchmarks"], workspace, timeout=120)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        fail("package resolution produced no dependencies")
    for line in lines:
        fields = line.split(maxsplit=3)
        if len(fields) != 4 or fields[2] != "workspace-link":
            fail(f"non-isolated dependency resolution: {line}")
        resolved = Path(fields[3]).resolve()
        if not resolved.is_relative_to(workspace):
            fail(f"workspace link escapes the sealed workspace: {line}")


def percentile(sorted_values: list[int], value: int) -> int:
    index = ((len(sorted_values) - 1) * value + 50) // 100
    return sorted_values[index]


def sample_summary(values: list[int]) -> dict[str, int]:
    if not values or any(not isinstance(value, int) or value <= 0 for value in values):
        fail("measurement samples must be positive integer base units")
    ordered = sorted(values)
    median = percentile(ordered, 50)
    deviations = sorted(abs(value - median) for value in ordered)
    return {
        "samples": len(values),
        "minimum": ordered[0],
        "p10": percentile(ordered, 10),
        "median": median,
        "p90": percentile(ordered, 90),
        "maximum": ordered[-1],
        "mad": percentile(deviations, 50),
        "spread_ppm": (percentile(ordered, 90) - percentile(ordered, 10)) * 1_000_000 // median,
    }


def one_sided_median_bound(samples: int) -> tuple[int, int]:
    if samples < 5 or samples > 63:
        fail("paired interval requires 5..63 samples")
    total = 1 << samples
    combination = 1
    cumulative = 0
    for index in range(samples):
        cumulative += combination
        if cumulative * 1_000_000 >= total * 950_000:
            return index, cumulative * 1_000_000 // total
        combination = combination * (samples - index) // (index + 1)
    raise AssertionError("unreachable median interval")


def relative_summary(candidate: list[int], reference: list[int]) -> dict[str, int]:
    if len(candidate) != len(reference):
        fail("paired candidate/reference sample counts differ")
    ratios = sorted(left * 1_000_000 // right for left, right in zip(candidate, reference, strict=True))
    index, confidence = one_sided_median_bound(len(ratios))
    return {
        "samples": len(ratios),
        "lower_bound_ppm": ratios[len(ratios) - 1 - index],
        "median_ppm": percentile(ratios, 50),
        "upper_bound_ppm": ratios[index],
        "confidence_ppm": confidence,
    }


def audit_measurement(case_id: str, metric_id: str, measurement: dict[str, Any], contract: dict[str, Any]) -> None:
    require_keys(measurement, {"candidate", "reference", "reference_kind"}, f"{case_id}/{metric_id}")
    candidate = measurement["candidate"]
    reference = measurement["reference"]
    if metric_id == "binary_size":
        if len(candidate) != 1 or len(reference) != 1 or reference[0] <= 0:
            fail(f"{case_id}/{metric_id}: exactly one positive candidate/reference value is required")
        ratio = candidate[0] * 1_000_000 // reference[0]
        if ratio > contract["non_runtime_upper_bound_ppm"]:
            fail(f"{case_id}/{metric_id}: {ratio} ppm exceeds the sealed budget")
        return

    expected_samples = contract["paired_samples"]
    if len(candidate) != expected_samples or len(reference) != expected_samples:
        fail(f"{case_id}/{metric_id}: expected {expected_samples} paired samples")
    left = sample_summary(candidate)
    right = sample_summary(reference)
    if left["spread_ppm"] > contract["maximum_spread_ppm"] or right["spread_ppm"] > contract["maximum_spread_ppm"]:
        fail(f"{case_id}/{metric_id}: excessive timing dispersion")
    relative = relative_summary(candidate, reference)
    if relative["confidence_ppm"] < contract["minimum_one_sided_confidence_ppm"]:
        fail(f"{case_id}/{metric_id}: insufficient one-sided confidence")
    limit = contract["runtime_upper_bound_ppm"] if metric_id == "execution" else contract["non_runtime_upper_bound_ppm"]
    if relative["upper_bound_ppm"] <= limit:
        return
    if relative["lower_bound_ppm"] > limit:
        fail(f"{case_id}/{metric_id}: regression ({relative['lower_bound_ppm']}..{relative['upper_bound_ppm']} ppm)")
    fail(f"{case_id}/{metric_id}: inconclusive ({relative['lower_bound_ppm']}..{relative['upper_bound_ppm']} ppm)")


def audit_reports(manifest: dict[str, Any], manifest_path: Path, report_paths: list[Path]) -> None:
    expected_hash = manifest_sha256(manifest_path)
    reports = [read_json(path) for path in report_paths]
    by_target: dict[str, dict[str, Any]] = {}
    for report in reports:
        require_keys(report, {"schema_version", "manifest_sha256", "candidate_revision", "host", "semantic_tests", "executions", "measurements"}, "report")
        if report["schema_version"] != 1 or report["manifest_sha256"] != expected_hash:
            fail("report: schema or sealed manifest hash mismatch")
        if report["candidate_revision"] != manifest["candidate"]["revision"]:
            fail("report: candidate revision mismatch")
        host = report["host"]
        require_keys(host, {"target", "runner", "os", "architecture", "cpu", "features", "native", "emulated", "cross_compiled"}, "report host")
        target = host["target"]
        if target in by_target:
            fail(f"duplicate report for {target}")
        by_target[target] = report

    if set(by_target) != REQUIRED_TARGETS:
        missing = REQUIRED_TARGETS - set(by_target)
        extra = set(by_target) - REQUIRED_TARGETS
        fail(f"report matrix mismatch; missing={sorted(missing)} extra={sorted(extra)}")

    target_contracts = {target["id"]: target for target in manifest["targets"]}
    matrix_cases = set(manifest["native_matrix_cases"])
    metric_ids = [metric["id"] for metric in manifest["metrics"]]
    for target, report in by_target.items():
        host = report["host"]
        expected = target_contracts[target]
        if host["runner"] != expected["runner"] or host["os"] != expected["os"] or host["architecture"] != expected["architecture"]:
            fail(f"{target}: runner/OS/architecture differs from the sealed profile")
        if not host["cpu"] or not host["features"]:
            fail(f"{target}: exact CPU and features were not recorded")
        if host["native"] is not True or host["emulated"] is not False or host["cross_compiled"] is not False:
            fail(f"{target}: native execution proof is invalid")
        executions = report["executions"]
        if set(executions) != matrix_cases:
            fail(f"{target}: native case catalog is incomplete")
        for case_id, modes in executions.items():
            if set(modes) != {"debug", "release"}:
                fail(f"{target}/{case_id}: Debug and Release are both required")
            for mode, execution in modes.items():
                require_keys(execution, {"status", "exit_code", "output_sha256"}, f"{target}/{case_id}/{mode}")
                if execution["status"] != "passed" or execution["exit_code"] != 0:
                    fail(f"{target}/{case_id}/{mode}: native execution failed")
                require_hex(execution["output_sha256"], 64, f"{target}/{case_id}/{mode} output hash")

        semantic_tests = report["semantic_tests"]
        if set(semantic_tests) != set(manifest["semantic_test_cases"]):
            fail(f"{target}: package/test semantic case catalog is incomplete")
        for case_id, execution in semantic_tests.items():
            require_keys(execution, {"status", "exit_code", "output_sha256"}, f"{target}/{case_id}/test")
            if execution["status"] != "passed" or execution["exit_code"] != 0:
                fail(f"{target}/{case_id}/test: semantic test failed")
            require_hex(execution["output_sha256"], 64, f"{target}/{case_id}/test output hash")

        if expected["performance"]:
            if set(report["measurements"]) != set(manifest["performance_cases"]):
                fail(f"{target}: physical performance workload catalog is incomplete")
            for case_id, measurements in report["measurements"].items():
                if set(measurements) != set(metric_ids):
                    fail(f"{target}/{case_id}: cost dimensions are incomplete")
                for metric_id, measurement in measurements.items():
                    audit_measurement(case_id, metric_id, measurement, manifest["statistical_contract"])
        elif report["measurements"]:
            fail(f"{target}: non-performance target must not imply physical timing evidence")


def self_test() -> None:
    candidate = list(range(80, 101, 2))
    reference = [100] * len(candidate)
    relative = relative_summary(candidate, reference)
    assert relative == {
        "samples": 11,
        "lower_bound_ppm": 840000,
        "median_ppm": 900000,
        "upper_bound_ppm": 960000,
        "confidence_ppm": 967285,
    }
    stable_candidate = [90 + index % 3 for index in range(21)]
    stable_reference = [100 + index % 3 for index in range(21)]
    contract = {
        "paired_samples": 21,
        "maximum_spread_ppm": 200000,
        "minimum_one_sided_confidence_ppm": 950000,
        "runtime_upper_bound_ppm": 1000000,
        "non_runtime_upper_bound_ppm": 1250000,
    }
    audit_measurement("self-test", "execution", {"candidate": stable_candidate, "reference": stable_reference, "reference_kind": "fixture"}, contract)
    try:
        audit_measurement("self-test", "execution", {"candidate": [110] * 21, "reference": [100] * 21, "reference_kind": "fixture"}, contract)
    except QualificationError as error:
        assert "regression" in str(error)
    else:
        raise AssertionError("slower measurement was accepted")
    try:
        audit_measurement(
            "self-test",
            "execution",
            {"candidate": [80] * 10 + [100] + [120] * 10, "reference": [100] * 21, "reference_kind": "fixture"},
            contract,
        )
    except QualificationError as error:
        assert "dispersion" in str(error) or "inconclusive" in str(error)
    else:
        raise AssertionError("noisy or inconclusive measurement was accepted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("Manifest.json"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="audit the sealed manifest and exact local closure")
    verify.add_argument("--workspace", type=Path, required=True)
    verify.add_argument("--silex", type=Path)
    gate = subparsers.add_parser("gate", help="apply the blocking six-target report gate")
    gate.add_argument("reports", nargs="+", type=Path)
    subparsers.add_parser("self-test", help="exercise gate mutations without running workloads")
    args = parser.parse_args()

    try:
        if args.command == "self-test":
            self_test()
            print("blind qualification self-test: PASS")
            return 0
        manifest = read_json(args.manifest)
        audit_manifest_shape(manifest)
        if args.command == "verify":
            audit_workspace(manifest, args.workspace, args.silex)
            print(f"sealed blind corpus: PASS ({len(manifest['cases'])} cases, {len(manifest['repositories'])} repositories)")
            return 0
        audit_reports(manifest, args.manifest, args.reports)
        print("blind qualification gate: PASS (six native targets, physical ARM64 and X64 performance)")
        return 0
    except QualificationError as error:
        print(f"blind qualification: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
