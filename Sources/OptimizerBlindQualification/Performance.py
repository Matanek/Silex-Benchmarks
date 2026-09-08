#!/usr/bin/env python3
"""Collect all sealed Part 09 cost dimensions on a quiet physical macOS host."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

import Campaign
import Qualification


PERFORMANCE = {
    "physics-contact": ("Packages/GFX.Physics/Benchmarks/ContactKernel2D.sx", []),
    "physics-integration": ("Packages/GFX.Physics/Benchmarks/IntegrationKernel2D.sx", []),
    "physics-preparation": ("Packages/GFX.Physics/Benchmarks/PreparationKernel2D.sx", []),
    "network-freshness": ("Silex-Benchmarks/Sources/NetworkFreshnessTracking.sx", []),
    "font-retained": ("Silex-Benchmarks/Sources/FontRasterization/Main.sx", ["retained_static"]),
    "boids2d-full": ("Silex-Benchmarks/Sources/Boids2D/Silex.sx", ["4000", "480"]),
    "falling-bodies2d-full": (
        "Silex-Benchmarks/Sources/FallingBodies2D/Main.sx",
        ["--smoke-fast", "--no-panel", "--immediate"],
    ),
    "scene3d-world-full": (
        "Silex-Benchmarks/Sources/WorldRendering3D/Main.sx",
        ["--benchmark", "--benchmark-no-shadows"],
    ),
}


def elapsed_from_output(case_id: str, output: str) -> int:
    if case_id.startswith("physics-"):
        fields = output.split()
        try:
            return round(float(fields[-2]) * 1_000_000)
        except (ValueError, IndexError) as error:
            raise Qualification.QualificationError(f"{case_id}: invalid KERNEL record") from error
    if case_id == "network-freshness":
        values = [float(value) for value in re.findall(r"milliseconds=([0-9]+(?:\.[0-9]+)?)", output)]
        if len(values) != 15:
            raise Qualification.QualificationError(f"{case_id}: expected 15 timing records")
        return round(sum(values) * 1_000_000)
    if case_id == "font-retained":
        measure = re.search(r"measure_ms=([0-9]+(?:\.[0-9]+)?)", output)
        raster = re.search(r"raster_ms=([0-9]+(?:\.[0-9]+)?)", output)
        if not measure or not raster:
            raise Qualification.QualificationError(f"{case_id}: invalid raster timing record")
        return round((float(measure.group(1)) + float(raster.group(1))) * 1_000_000)
    if case_id == "boids2d-full":
        match = re.search(r"fps=([0-9]+(?:\.[0-9]+)?)", output)
        if not match or float(match.group(1)) <= 0:
            raise Qualification.QualificationError(f"{case_id}: invalid FPS record")
        return round(480 / float(match.group(1)) * 1_000_000_000)
    if case_id == "falling-bodies2d-full":
        match = re.search(r"average render FPS: ([0-9]+(?:\.[0-9]+)?)", output)
        if not match or float(match.group(1)) <= 0:
            raise Qualification.QualificationError(f"{case_id}: invalid cadence record")
        return round(20 / float(match.group(1)) * 1_000_000_000)
    if case_id == "scene3d-world-full":
        matches = re.findall(r"SILEX_GFX_WORLD seconds=([0-9]+(?:\.[0-9]+)?)", output)
        if not matches:
            raise Qualification.QualificationError(f"{case_id}: invalid Scene3D record")
        return round(float(matches[-1]) * 1_000_000_000)
    raise AssertionError(case_id)


def run_output(command: list[str], workspace: Path, timeout: float, env: dict[str, str] | None = None) -> str:
    result = Qualification.run_checked(command, workspace, timeout, env)
    return result.stdout


def measure_execution(case_id: str, command: list[str], workspace: Path, timeout: float) -> int:
    return elapsed_from_output(case_id, run_output(command, workspace, timeout))


def build_startup_probe(output: Path, workspace: Path, timeout: float) -> None:
    source = Path(__file__).with_name("StartupStop.c").resolve()
    Qualification.run_checked(["clang", "-dynamiclib", str(source), "-o", str(output)], workspace, timeout)
    if not output.is_file():
        raise Qualification.QualificationError("clang did not produce the startup probe")


def measure_startup(command: list[str], workspace: Path, timeout: float, probe: Path) -> int:
    environment = os.environ.copy()
    environment["DYLD_INSERT_LIBRARIES"] = str(probe)
    started = time.perf_counter_ns()
    result = Qualification.run_checked(command, workspace, timeout, environment)
    elapsed = time.perf_counter_ns() - started
    if result.stdout or result.stderr:
        raise Qualification.QualificationError("startup probe did not exit before application main")
    return elapsed


def measure_rss(command: list[str], workspace: Path, timeout: float) -> int:
    result = Qualification.run_checked(["/usr/bin/time", "-l", *command], workspace, timeout)
    values = [
        int(value)
        for value in re.findall(
            r"^\s*([0-9]+)\s+(?:maximum resident set size|peak memory footprint)\s*$",
            result.stderr,
            re.MULTILINE,
        )
    ]
    if not values:
        raise Qualification.QualificationError("/usr/bin/time -l did not report peak RSS")
    return max(values)


def compile_once(compiler: Path, source: str, output: Path, workspace: Path, cold: bool, timeout: float) -> int:
    if output.exists():
        output.unlink()
    command = [str(compiler), "compile", source, "--release", "--output", str(output)]
    if cold:
        command.insert(-2, "--nocache")
    started = time.perf_counter_ns()
    Qualification.run_checked(command, workspace, timeout)
    elapsed = time.perf_counter_ns() - started
    if not output.is_file():
        raise Qualification.QualificationError(f"compiler did not produce {output}")
    return elapsed


def paired(
    count: int,
    warmups: int,
    left: Callable[[], int],
    right: Callable[[], int],
    label: str,
) -> tuple[list[int], list[int]]:
    for _ in range(warmups):
        left()
        right()
    candidate: list[int] = []
    reference: list[int] = []
    for index in range(count):
        if index % 2 == 0:
            candidate.append(left())
            reference.append(right())
        else:
            reference.append(right())
            candidate.append(left())
        print(f"{label}: pair {index + 1}/{count}", flush=True)
    return candidate, reference


def measurement(candidate: list[int], reference: list[int], reference_kind: str) -> dict[str, Any]:
    return {"candidate": candidate, "reference": reference, "reference_kind": reference_kind}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--candidate-silex", required=True, type=Path)
    parser.add_argument("--baseline-silex", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--physics-oracle-dir", required=True, type=Path)
    parser.add_argument("--boids-cpp", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("Manifest.json"))
    parser.add_argument("--candidate-descriptor", type=Path, default=Path(__file__).with_name("Candidate.json"))
    parser.add_argument("--fixture-correction", type=Path, default=Path(__file__).with_name("FixtureCorrection.json"))
    parser.add_argument("--boundary-scope", type=Path, default=Path(__file__).with_name("BoundaryScope.json"))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--only", action="append", choices=sorted(PERFORMANCE))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    candidate_silex = args.candidate_silex.resolve()
    baseline_silex = args.baseline_silex.resolve()
    manifest_path = args.manifest.resolve()
    candidate_path = args.candidate_descriptor.resolve()
    fixture_path = args.fixture_correction.resolve()
    boundary_scope_path = args.boundary_scope.resolve()
    manifest = Qualification.read_json(manifest_path)
    Qualification.audit_manifest_shape(manifest)
    candidate_descriptor = Qualification.read_json(candidate_path)
    fixture_correction = Qualification.read_json(fixture_path)
    boundary_scope = Qualification.read_json(boundary_scope_path)
    Qualification.audit_workspace(
        manifest,
        manifest_path,
        candidate_descriptor,
        candidate_path,
        fixture_correction,
        fixture_path,
        boundary_scope,
        boundary_scope_path,
        workspace,
        candidate_silex,
    )
    report = Qualification.read_json(args.report.resolve())
    if report.get("manifest_sha256") != Qualification.manifest_sha256(manifest_path):
        raise Qualification.QualificationError("partial report does not match the sealed manifest")
    if report.get("candidate_descriptor_sha256") != Qualification.candidate_sha256(candidate_path):
        raise Qualification.QualificationError("partial report does not match the corrected candidate descriptor")
    if report.get("fixture_correction_sha256") != Qualification.fixture_sha256(fixture_path):
        raise Qualification.QualificationError("partial report does not match the corrected fixture descriptor")
    if report.get("boundary_scope_sha256") != Qualification.boundary_scope_sha256(boundary_scope_path):
        raise Qualification.QualificationError("partial report does not match the boundary scope descriptor")
    if report.get("candidate_revision") != candidate_descriptor["qualified_candidate_revision"]:
        raise Qualification.QualificationError("partial report does not match the corrected candidate revision")
    if report.get("host", {}).get("os") != "macos" or report.get("host", {}).get("target") not in {"macos-arm64", "macos-x64"}:
        raise Qualification.QualificationError("performance evidence requires a native macOS ARM64 or X64 profile")
    os.environ["ZIG_GLOBAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-global")
    os.environ["ZIG_LOCAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-local")

    count = manifest["statistical_contract"]["paired_samples"]
    warmups = manifest["statistical_contract"]["warmups"]
    selected = set(args.only or PERFORMANCE)
    root = args.report.resolve().parent / "performance"
    root.mkdir(parents=True, exist_ok=True)
    startup_probe = root / "startup-stop.dylib"
    build_startup_probe(startup_probe, workspace, args.timeout)
    startup_probe_source = Path(__file__).with_name("StartupStop.c").resolve()
    physics_names = {
        "physics-contact": "gfx_physics_contact_kernel_slots",
        "physics-integration": "gfx_physics_integration_kernel_slots",
        "physics-preparation": "gfx_physics_preparation_kernel_slots",
    }

    for case_id in manifest["performance_cases"]:
        if case_id not in selected:
            continue
        source, arguments = PERFORMANCE[case_id]
        runtime_cwd = (workspace / Path(source).parent).resolve()
        candidate_binary = root / f"{case_id}-candidate"
        baseline_binary = root / f"{case_id}-baseline"
        compile_once(candidate_silex, source, candidate_binary, workspace, False, args.timeout)
        compile_once(baseline_silex, source, baseline_binary, workspace, False, args.timeout)
        candidate_command = [str(candidate_binary), *arguments]
        baseline_command = [str(baseline_binary), *arguments]
        execution_reference = baseline_command
        execution_kind = "Part-07-compiler-baseline"
        if case_id in physics_names:
            execution_reference = [str((args.physics_oracle_dir / physics_names[case_id]).resolve())]
            execution_kind = "clang-same-layout"
        elif case_id == "boids2d-full":
            execution_reference = [str(args.boids_cpp.resolve()), "4000", "480"]
            execution_kind = "cpp-architectural"

        case_measurements: dict[str, Any] = {}
        values = paired(
            count,
            warmups,
            lambda: measure_execution(case_id, candidate_command, runtime_cwd, args.timeout),
            lambda: measure_execution(case_id, execution_reference, runtime_cwd, args.timeout),
            f"{case_id}/execution",
        )
        case_measurements["execution"] = measurement(*values, execution_kind)
        values = paired(
            count,
            warmups,
            lambda: measure_startup(candidate_command, runtime_cwd, args.timeout, startup_probe),
            lambda: measure_startup(baseline_command, runtime_cwd, args.timeout, startup_probe),
            f"{case_id}/startup",
        )
        case_measurements["startup"] = measurement(*values, "Part-07-compiler-baseline")
        case_measurements["startup"]["method"] = "spawn-to-dyld-injected-constructor-exit"
        case_measurements["startup"]["probe_sha256"] = Qualification.sha256(startup_probe_source)

        cold_index = 0
        def cold(compiler: Path, label: str) -> int:
            nonlocal cold_index
            cold_index += 1
            return compile_once(compiler, source, root / f"{case_id}-{label}-cold-{cold_index}", workspace, True, args.timeout)
        values = paired(
            count,
            warmups,
            lambda: cold(candidate_silex, "candidate"),
            lambda: cold(baseline_silex, "baseline"),
            f"{case_id}/cold_compile",
        )
        case_measurements["cold_compile"] = measurement(*values, "Part-07-compiler-baseline")

        warm_candidate = root / f"{case_id}-candidate-warm"
        warm_baseline = root / f"{case_id}-baseline-warm"
        compile_once(candidate_silex, source, warm_candidate, workspace, False, args.timeout)
        compile_once(baseline_silex, source, warm_baseline, workspace, False, args.timeout)
        values = paired(
            count,
            warmups,
            lambda: compile_once(candidate_silex, source, warm_candidate, workspace, False, args.timeout),
            lambda: compile_once(baseline_silex, source, warm_baseline, workspace, False, args.timeout),
            f"{case_id}/warm_compile",
        )
        case_measurements["warm_compile"] = measurement(*values, "Part-07-compiler-baseline")
        values = paired(
            count,
            warmups,
            lambda: measure_rss(candidate_command, runtime_cwd, args.timeout),
            lambda: measure_rss(baseline_command, runtime_cwd, args.timeout),
            f"{case_id}/peak_rss",
        )
        case_measurements["peak_rss"] = measurement(*values, "Part-07-compiler-baseline")
        case_measurements["binary_size"] = measurement(
            [candidate_binary.stat().st_size],
            [baseline_binary.stat().st_size],
            "Part-07-compiler-baseline",
        )
        for metric_id, record in case_measurements.items():
            Qualification.audit_measurement(case_id, metric_id, record, manifest["statistical_contract"])
        report["measurements"][case_id] = case_measurements
        Campaign.write_report(args.report, report)

    print(f"performance campaign partial report: {args.report}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("performance campaign: interrupted; active process group terminated", file=sys.stderr)
        sys.exit(130)
    except Qualification.QualificationError as error:
        print(f"performance campaign: FAIL: {error}", file=sys.stderr)
        sys.exit(1)
