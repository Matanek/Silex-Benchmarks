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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--silex", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("Manifest.json"))
    parser.add_argument("--candidate-descriptor", type=Path, default=Path(__file__).with_name("Candidate.json"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--only", action="append", choices=sorted(set(SEMANTIC_COMMANDS) | set(NATIVE_CASES)))
    parser.add_argument("--mode", action="append", choices=("debug", "release"), help="limit executable cases; repeatable")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    silex = args.silex.resolve()
    manifest_path = args.manifest.resolve()
    candidate_path = args.candidate_descriptor.resolve()
    # Keep every compiler/toolchain cache inside the single Spec workspace.
    # In particular, --nocache still asks Zig for temporary link directories.
    os.environ["ZIG_GLOBAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-global")
    os.environ["ZIG_LOCAL_CACHE_DIR"] = str(workspace / ".silex" / "zig-local")
    manifest = Qualification.read_json(manifest_path)
    Qualification.audit_manifest_shape(manifest)
    candidate_descriptor = Qualification.read_json(candidate_path)
    Qualification.audit_workspace(
        manifest,
        manifest_path,
        candidate_descriptor,
        candidate_path,
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
        "candidate_revision": candidate,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": host_identity(workspace, args.runner),
        "semantic_tests": {},
        "executions": {},
        "measurements": {},
        "logs": {},
    }
    if args.output.exists():
        previous = Qualification.read_json(args.output)
        for key in ("semantic_tests", "executions", "measurements", "logs"):
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
        write_report(args.output, report)

    binaries = args.output.parent / "binaries"
    binaries.mkdir(parents=True, exist_ok=True)
    for case_id in manifest["native_matrix_cases"]:
        if case_id not in selected:
            continue
        source, arguments = NATIVE_CASES[case_id]
        runtime_cwd = (workspace / Path(source).parent).resolve()
        report["executions"].setdefault(case_id, {})
        for mode in selected_modes:
            suffix = ".exe" if report["host"]["os"] == "windows" else ""
            executable = binaries / f"{case_id}-{mode}{suffix}"
            print(f"compile {case_id} {mode}", flush=True)
            compile_result = record(
                [str(silex), "compile", source, f"--{mode}", "--nocache", "--output", str(executable)],
                workspace,
                args.timeout,
            )
            print(f"execute {case_id} {mode}", flush=True)
            execute_result = record([str(executable), *arguments], runtime_cwd, args.timeout)
            verify_signature(case_id, execute_result)
            report["executions"][case_id][mode] = public_record(execute_result)
            report["logs"][f"compile/{case_id}/{mode}"] = {
                "stdout": compile_result["stdout"],
                "stderr": compile_result["stderr"],
                "command": compile_result["command"],
                "cwd": compile_result["cwd"],
                "binary_sha256": Qualification.sha256(executable),
                "binary_size": executable.stat().st_size,
            }
            report["logs"][f"execute/{case_id}/{mode}"] = {
                "stdout": execute_result["stdout"],
                "stderr": execute_result["stderr"],
                "command": execute_result["command"],
                "cwd": execute_result["cwd"],
            }
            write_report(args.output, report)

    print(f"native campaign partial report: {args.output}")
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
