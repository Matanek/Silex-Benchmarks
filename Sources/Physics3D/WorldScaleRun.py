#!/usr/bin/env python3
"""Measure fixed-work Physics3D stress scenes without rendering.

Run from the workspace root (or the Spec's Worktree root). The script builds
the Release source, warms each case, alternates case order across seven runs,
and writes raw timings with median and median absolute deviation.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = Path("Silex-Benchmarks/Sources/Physics3D/WorldScale.sx")
DEFAULT_CASES = (("sparse", 1024), ("bin", 256), ("bin", 512),
                 ("bin", 1024), ("column", 128), ("column", 256))
FIELDS = frozenset(("bodies", "steps", "mode", "contacts_total",
                    "contacts_last", "outside", "low", "minimum_y",
                    "checksum", "create_ms", "first_step_ms",
                    "maximum_step_ms", "step_ms"))
MEASURES = ("create_ms", "first_step_ms", "maximum_step_ms", "step_ms")


def run(command, *, environment=None):
    completed = subprocess.run(command, cwd=ROOT, env=environment,
                               text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"{' '.join(map(str, command))} exited "
                           f"{completed.returncode}:\n"
                           f"{completed.stdout}{completed.stderr}")
    return completed.stdout


def parse(output, mode, bodies, steps):
    result = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator != "=" or key not in FIELDS or key in result:
            raise ValueError(f"invalid or duplicate field: {line}")
        result[key] = value if key == "mode" else float(value)
    if result.keys() != FIELDS:
        raise ValueError(f"unexpected fields: {sorted(result.keys())}")
    if result["mode"] != mode or result["bodies"] != bodies or \
            result["steps"] != steps or result["outside"] != 0 or \
            result["low"] != 0:
        raise ValueError(f"incorrect workload or escaping body: {result}")
    if any(not math.isfinite(result[key]) for key in FIELDS - {"mode"}):
        raise ValueError(f"non-finite result: {result}")
    if mode == "sparse" and result["contacts_total"] != 0:
        raise ValueError("sparse workload unexpectedly collided")
    if mode != "sparse" and result["contacts_total"] <= 0:
        raise ValueError("contact workload did not collide")
    if any(result[key] < 0 for key in MEASURES):
        raise ValueError("negative elapsed time")
    return result


def summarize(samples):
    result = {}
    for key in MEASURES:
        values = [sample[key] for sample in samples]
        median = statistics.median(values)
        mad = statistics.median(abs(value - median) for value in values)
        result[key] = {"median": median, "min": min(values),
                       "max": max(values), "mad": mad,
                       "mad_percent": 100.0 * mad / median if median else 0.0}
    result["stable_step_timing"] = result["step_ms"]["mad_percent"] <= 5.0
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, choices=(30, 60, 120, 240),
                        default=60)
    parser.add_argument("--output", type=Path,
                        default=ROOT / ".silex/physics3d-world-scale-campaign.json")
    parser.add_argument("--silex", default="silex",
                        help="compiler executable (default: silex on PATH)")
    options = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        parser.error(f"run from the workspace root: {ROOT}")
    compiler_path = Path(shutil.which(options.silex) or options.silex).resolve()
    binary = ROOT / ".silex/physics3d-world-scale-release"
    binary.parent.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(ROOT / ".silex/zig")
    run([options.silex, "compile", str(SOURCE), "--release", "-o", str(binary)],
        environment=environment)
    cases = {f"{mode}-{count}": {"mode": mode, "bodies": count,
                                  "warmup": None, "samples": []}
             for mode, count in DEFAULT_CASES}
    for mode, count in DEFAULT_CASES:
        key = f"{mode}-{count}"
        cases[key]["warmup"] = parse(
            run([str(binary), mode, str(count), str(options.steps)]),
            mode, count, options.steps)
    for repetition in range(7):
        order = DEFAULT_CASES if repetition % 2 == 0 else reversed(DEFAULT_CASES)
        for mode, count in order:
            key = f"{mode}-{count}"
            sample = parse(run([str(binary), mode, str(count),
                                str(options.steps)]),
                           mode, count, options.steps)
            cases[key]["samples"].append(sample)
            print(f"{repetition + 1}/7 {key}: "
                  f"{sample['step_ms'] / options.steps:.3f} ms/step",
                  flush=True)
    for case in cases.values():
        reference = {key: case["warmup"][key] for key in
                     ("contacts_total", "contacts_last", "checksum")}
        for sample in case["samples"]:
            for key, expected in reference.items():
                if not math.isclose(sample[key], expected,
                                    rel_tol=1e-6, abs_tol=1e-5):
                    raise ValueError(f"non-deterministic {key} in "
                                     f"{case['mode']}-{case['bodies']}")
        case["summary"] = summarize(case["samples"])
    record = {
        "schema": 1, "source": str(SOURCE), "build": "Release",
        "step_seconds": 1.0 / 60.0, "steps": options.steps,
        "repetitions": 7, "host": platform.platform(),
        "architecture": platform.machine(),
        "silex": run([options.silex, "version"]).strip(),
        "compiler_executable": str(compiler_path),
        "compiler_sha256": hashlib.sha256(compiler_path.read_bytes()).hexdigest(),
        "cases": cases,
    }
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(record, indent=2) + "\n",
                              encoding="utf-8")
    print(f"raw results: {options.output}")
    for key, case in cases.items():
        summary = case["summary"]
        print(f"{key}: {summary['step_ms']['median'] / options.steps:.3f} "
              f"ms/step, MAD {summary['step_ms']['mad_percent']:.2f}%")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"WorldScaleRun: {error}", file=sys.stderr)
        sys.exit(1)
