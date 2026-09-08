#!/usr/bin/env python3
"""Attribute the sealed Regex test timeout without changing its source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import Qualification


SEALED_SOURCE_SHA256 = "246ecb85c36e0b3f13f1e40bcffc78cfe89bba2871021b019b956ae0ac191779"
FIRST_LABEL = 'test "streaming search over one million scalars"'
SECOND_LABEL = 'test "large finite repetition stays compact"'


def derived_entries(source: str) -> dict[str, str]:
    prefix, tests = source.split(FIRST_LABEL, 1)
    first, second = tests.split(SECOND_LABEL, 1)
    return {
        "streaming-search": prefix + "func main()" + first,
        "finite-repetition": prefix + "func main()" + second,
    }


def run(command: list[str], cwd: Path, timeout: float) -> dict[str, Any]:
    started = time.monotonic_ns()
    try:
        result = Qualification.run_checked(command, cwd, timeout)
    except Qualification.QualificationError as error:
        elapsed = time.monotonic_ns() - started
        message = str(error)
        return {
            "status": "timeout" if "command timed out" in message else "failed",
            "elapsed_ns": elapsed,
            "diagnostic": message,
        }
    elapsed = time.monotonic_ns() - started
    return {
        "status": "passed",
        "elapsed_ns": elapsed,
        "exit_code": result.returncode,
        "output_sha256": hashlib.sha256((result.stdout + "\0" + result.stderr).encode()).hexdigest(),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--silex", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    silex = args.silex.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != SEALED_SOURCE_SHA256:
        raise Qualification.QualificationError(
            f"sealed Regex source hash mismatch: {source_sha256}"
        )

    diagnostic_root = workspace / ".silex" / "diagnostics" / "regex"
    diagnostic_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "non-qualifying timeout attribution",
        "sealed_source": str(source.relative_to(workspace)),
        "sealed_source_sha256": source_sha256,
        "timeout_seconds": args.timeout,
        "entries": {},
    }

    for entry, derived_source in derived_entries(source_bytes.decode()).items():
        entry_source = diagnostic_root / f"{entry}.sx"
        entry_source.write_text(derived_source)
        entry_report: dict[str, Any] = {
            "derived_source_sha256": Qualification.sha256(entry_source),
            "modes": {},
        }
        report["entries"][entry] = entry_report
        for mode in ("release", "debug"):
            executable = diagnostic_root / f"{entry}-{mode}"
            compile_result = run(
                [
                    str(silex),
                    "compile",
                    str(entry_source.relative_to(workspace)),
                    f"--{mode}",
                    "--nocache",
                    "--output",
                    str(executable),
                ],
                workspace,
                args.timeout,
            )
            mode_report: dict[str, Any] = {"compile": compile_result}
            entry_report["modes"][mode] = mode_report
            print(f"{entry} {mode} compile: {compile_result['status']}", flush=True)
            if compile_result["status"] != "passed":
                continue
            execute_result = run([str(executable)], diagnostic_root, args.timeout)
            mode_report["execute"] = execute_result
            print(f"{entry} {mode} execute: {execute_result['status']}", flush=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    release_green = all(
        entry["modes"]["release"]["compile"]["status"] == "passed"
        and entry["modes"]["release"].get("execute", {}).get("status") == "passed"
        for entry in report["entries"].values()
    )
    return 0 if release_green else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Qualification.QualificationError as error:
        print(f"regex diagnostic: FAIL: {error}")
        raise SystemExit(1)
