#!/usr/bin/env python3
"""Run the sealed Part 09 semantic and Debug/Release native corpus safely."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import Qualification


SEMANTIC_COMMANDS = {
    "collections-ownership": ["test", "Packages/STD/Tests/Collections.sx"],
    "ecs": ["test", "Packages/GFX.ECS/Tests/ECS.sx"],
    "json": ["test", "Packages/JSON/Tests/JSON.sx"],
    "webview-round-trips": ["test", "Silex-Benchmarks/Sources/WebViewBridgeRoundTrips/Main.sx"],
    "regex-streaming": ["test", "Silex-Benchmarks/Sources/RegexStreamingSearch.sx"],
}

NATIVE_CASES = {
    "physics-contact": ("Packages/GFX.Physics/Benchmarks/ContactKernel2D.sx", ["--check"]),
    "physics-integration": ("Packages/GFX.Physics/Benchmarks/IntegrationKernel2D.sx", ["--check-full"]),
    "physics-preparation": ("Packages/GFX.Physics/Benchmarks/PreparationKernel2D.sx", ["--check-full"]),
    "network-freshness": ("Silex-Benchmarks/Sources/NetworkFreshnessTracking.sx", []),
    "font-retained": ("Silex-Benchmarks/Sources/FontRasterization/Main.sx", ["retained_static"]),
    "font-direct": ("Silex-Benchmarks/Sources/FontRasterization/Direct.sx", []),
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

SIGNATURE_PREFIXES = {
    "physics-contact": "STATE ",
    "physics-integration": "STATE ",
    "physics-preparation": "STATE ",
    "network-freshness": "comparison repetition=1 observations=1000000",
    "font-retained": "SILEX_FONT_RASTER case=retained_static",
    "font-direct": "SILEX_FONT_DIRECT ",
    "boids2d-full": "SILEX_GFX_BOIDS count=4000 frames=480",
    "falling-bodies2d-full": "FallingBody smoke:",
    "scene3d-world-full": "SILEX_GFX_WORLD ",
}


# The direct-font Debug witness hashes the complete 596 KiB embedded font with
# the intentionally portable Silex SHA-256 implementation. It already takes
# 313-374 seconds on the qualified Windows/Linux X64 hosts, so the older Intel
# macOS host needs a wider liveness guard. This changes neither the workload nor
# its oracle; every other command keeps the sealed default timeout.
NATIVE_EXECUTION_TIMEOUT_FLOORS = {
    ("font-direct", "debug"): 1_200.0,
}


def output_sha256(stdout: str, stderr: str) -> str:
    return hashlib.sha256((stdout + "\0" + stderr).encode()).hexdigest()


def local_target() -> tuple[str, str, str]:
    system = platform.system().lower()
    machine = platform.machine()
    normalized = machine.lower()
    if normalized in {"arm64", "aarch64"}:
        architecture = "arm64" if system == "darwin" else "aarch64"
        family = "arm64"
    elif normalized in {"x86_64", "amd64"}:
        architecture = "AMD64" if system == "windows" else "x86_64"
        family = "x64"
    else:
        raise Qualification.QualificationError(f"unsupported native architecture: {machine}")
    os_name = {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(system)
    if os_name is None:
        raise Qualification.QualificationError(f"unsupported native system: {system}")
    return f"{os_name}-{family}", os_name, architecture


def host_identity(workspace: Path, runner: str) -> dict[str, Any]:
    target, os_name, architecture = local_target()
    cpu = platform.processor() or platform.machine()
    features = platform.platform()
    if os_name == "macos":
        for key in ("machdep.cpu.brand_string", "hw.model"):
            result = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip():
                cpu = result.stdout.strip()
                break
        result = subprocess.run(["sysctl", "-a"], capture_output=True, text=True, check=False)
        selected = [line for line in result.stdout.splitlines() if line.startswith("hw.optional.") and line.endswith(": 1")]
        if selected:
            features = ",".join(line.split(":", 1)[0] for line in selected)
    elif os_name == "linux":
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.is_file():
            lines = cpuinfo.read_text(errors="replace").splitlines()
            for label in ("model name", "Hardware", "Processor"):
                match = next((line.split(":", 1)[1].strip() for line in lines if line.startswith(label + "\t") or line.startswith(label + " :")), None)
                if match:
                    cpu = match
                    break
            feature_line = next((line for line in lines if line.startswith("flags") or line.startswith("Features")), "")
            if ":" in feature_line:
                features = feature_line.split(":", 1)[1].strip()
    elif os_name == "windows":
        cpu = os.environ.get("PROCESSOR_IDENTIFIER", cpu)
        features = os.environ.get("PROCESSOR_ARCHITEW6432", architecture)
    return {
        "target": target,
        "runner": runner,
        "os": os_name,
        "architecture": architecture,
        "cpu": cpu,
        "features": features,
        "native": True,
        "emulated": False,
        "cross_compiled": False,
        "platform": platform.platform(),
        "workspace": str(workspace.resolve()),
    }


def record(command: list[str], cwd: Path, timeout: float) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    result = Qualification.run_checked(command, cwd, timeout)
    return {
        "status": "passed",
        "exit_code": result.returncode,
        "output_sha256": output_sha256(result.stdout, result.stderr),
        "started_at": started,
        "command": command,
        "cwd": str(cwd.resolve()),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def verify_signature(case_id: str, result: dict[str, Any]) -> None:
    prefix = SIGNATURE_PREFIXES[case_id]
    if prefix not in result["stdout"]:
        raise Qualification.QualificationError(f"{case_id}: missing semantic signature {prefix!r}")


def public_record(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("status", "exit_code", "output_sha256")}


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def native_execution_timeout(case_id: str, mode: str, default: float) -> float:
    return max(default, NATIVE_EXECUTION_TIMEOUT_FLOORS.get((case_id, mode), 0.0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--silex", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("Manifest.json"))
    parser.add_argument("--candidate-descriptor", type=Path, default=Path(__file__).with_name("Candidate.json"))
    parser.add_argument("--fixture-correction", type=Path, default=Path(__file__).with_name("FixtureCorrection.json"))
    parser.add_argument("--boundary-scope", type=Path, default=Path(__file__).with_name("BoundaryScope.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--only", action="append", choices=sorted(set(SEMANTIC_COMMANDS) | set(NATIVE_CASES)))
    parser.add_argument("--mode", action="append", choices=("debug", "release"), help="limit executable cases; repeatable")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    silex = args.silex.resolve()
    output = args.output.resolve()
    manifest_path = args.manifest.resolve()
    candidate_path = args.candidate_descriptor.resolve()
    fixture_path = args.fixture_correction.resolve()
    boundary_scope_path = args.boundary_scope.resolve()
    # Keep every compiler/toolchain cache inside the single Spec workspace.
    # In particular, --nocache still asks Zig for temporary link directories.
    os.environ["ZIG_GLOBAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-global")
    os.environ["ZIG_LOCAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-local")
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
        silex,
    )
    selected = set(args.only or (set(SEMANTIC_COMMANDS) | set(NATIVE_CASES)))
    selected_modes = tuple(args.mode or ("debug", "release"))
    candidate = Qualification.run_checked(["git", "rev-parse", "HEAD"], workspace / "Silex").stdout.strip()
    report: dict[str, Any] = {
        "schema_version": 1,
        "manifest_sha256": Qualification.manifest_sha256(manifest_path),
        "candidate_descriptor_sha256": Qualification.candidate_sha256(candidate_path),
        "fixture_correction_sha256": Qualification.fixture_sha256(fixture_path),
        "boundary_scope_sha256": Qualification.boundary_scope_sha256(boundary_scope_path),
        "candidate_revision": candidate,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": host_identity(workspace, args.runner),
        "semantic_tests": {},
        "executions": {},
        "compile_only": {},
        "measurements": {},
        "logs": {},
    }
    if output.exists():
        previous = Qualification.read_json(output)
        for key in ("semantic_tests", "executions", "compile_only", "measurements", "logs"):
            report[key].update(previous.get(key, {}))

    for case_id in manifest["semantic_test_cases"]:
        if case_id not in selected:
            continue
        print(f"semantic {case_id}", flush=True)
        command = [str(silex), *SEMANTIC_COMMANDS[case_id], "--nocache"]
        result = record(command, workspace, args.timeout)
        report["semantic_tests"][case_id] = public_record(result)
        report["logs"][f"semantic/{case_id}"] = {
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "command": result["command"],
            "cwd": result["cwd"],
        }
        write_report(output, report)

    binaries = output.parent / "binaries"
    binaries.mkdir(parents=True, exist_ok=True)
    compile_only_cases = set(boundary_scope["compile_only_cases"].get(report["host"]["target"], []))
    for case_id in manifest["native_matrix_cases"]:
        if case_id not in selected:
            continue
        source, arguments = NATIVE_CASES[case_id]
        runtime_cwd = (workspace / Path(source).parent).resolve()
        destination = "compile_only" if case_id in compile_only_cases else "executions"
        report[destination].setdefault(case_id, {})
        for mode in selected_modes:
            suffix = ".exe" if report["host"]["os"] == "windows" else ""
            executable = binaries / f"{case_id}-{mode}{suffix}"
            print(f"compile {case_id} {mode}", flush=True)
            compile_result = record(
                [str(silex), "compile", source, f"--{mode}", "--nocache", "--output", str(executable)],
                workspace,
                args.timeout,
            )
            binary_sha256 = Qualification.sha256(executable)
            binary_size = executable.stat().st_size
            report["logs"][f"compile/{case_id}/{mode}"] = {
                "stdout": compile_result["stdout"],
                "stderr": compile_result["stderr"],
                "command": compile_result["command"],
                "cwd": compile_result["cwd"],
                "binary_sha256": binary_sha256,
                "binary_size": binary_size,
            }
            if case_id in compile_only_cases:
                report["compile_only"][case_id][mode] = {
                    **public_record(compile_result),
                    "binary_sha256": binary_sha256,
                    "binary_size": binary_size,
                }
                write_report(output, report)
                continue
            print(f"execute {case_id} {mode}", flush=True)
            execution_timeout = native_execution_timeout(case_id, mode, args.timeout)
            execute_result = record([str(executable), *arguments], runtime_cwd, execution_timeout)
            verify_signature(case_id, execute_result)
            report["executions"][case_id][mode] = public_record(execute_result)
            report["logs"][f"execute/{case_id}/{mode}"] = {
                "stdout": execute_result["stdout"],
                "stderr": execute_result["stderr"],
                "command": execute_result["command"],
                "cwd": execute_result["cwd"],
                "timeout_seconds": execution_timeout,
            }
            write_report(output, report)

    print(f"native campaign partial report: {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("native campaign: interrupted; active process group terminated", file=sys.stderr)
        sys.exit(130)
    except Qualification.QualificationError as error:
        print(f"native campaign: FAIL: {error}", file=sys.stderr)
        sys.exit(1)
