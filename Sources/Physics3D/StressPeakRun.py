#!/usr/bin/env python3
"""Compare deterministic column/jet physics with warm-up and seven fresh process pairs."""

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = {"column": ("ColumnPeak.sx", 600, 256), "jet": ("JetPeak.sx", 900, 1024)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def host_detail(key):
    if platform.system() != "Darwin":
        return None
    result = subprocess.run(["sysctl", "-n", key], text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def repository_state(relative):
    directory = ROOT / relative
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=directory, text=True).strip()
    diff = subprocess.check_output(["git", "diff", "HEAD", "--"], cwd=directory)
    return {"head": head, "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
            "has_tracked_changes": bool(diff)}


def execute(binary, scenario, foreground):
    source, steps, bodies = SCENARIOS[scenario]
    command = [str(binary)]
    if foreground:
        command = ["taskpolicy", "-a", *command]
    process = subprocess.Popen(command, cwd=ROOT, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if foreground:
        policy = subprocess.run(["taskpolicy", "-B", "-p", str(process.pid)],
                                text=True, capture_output=True)
        if policy.returncode:
            process.terminate()
            process.communicate()
            raise RuntimeError(f"cannot set own child priority: {policy.stderr}")
    output, error = process.communicate()
    if process.returncode:
        raise RuntimeError(f"{binary} exited {process.returncode}:\n{error}")
    rows = list(csv.reader(io.StringIO(output)))
    if len(rows) != steps or any(len(row) != 6 for row in rows):
        raise ValueError(f"expected {steps} step,ms,awake,contacts,checksum,minimum_y rows")
    parsed = [[float(value) for value in row] for row in rows]
    for step, row in enumerate(parsed):
        if row[0] != step or not all(math.isfinite(value) for value in row):
            raise ValueError(f"invalid step data: {row}")
        if row[1] < 0 or not 0 <= row[2] <= bodies or row[3] < 0 or row[5] < 0:
            raise ValueError(f"invalid timing, counters or floor escape: {row}")
    if scenario == "column" and parsed[-1][5] < 0.14:
        raise ValueError("column failed its final floor guard")
    times = [row[1] for row in parsed]
    ordered = sorted(times)
    windows = [statistics.mean(times[start:start + 60]) for start in range(steps - 59)]
    return {"rows": parsed, "mean_ms": statistics.mean(times),
            "p95_ms": ordered[math.ceil(len(times) * .95) - 1],
            "max_ms": max(times), "worst_60_steps_ms": max(windows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--silex", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before-silex", type=Path, help="frozen compiler used for the baseline; defaults to --silex")
    parser.add_argument("--observables", choices=("exact", "deterministic"), default="exact",
                        help="exact across versions, or reproducible per version when floating rounding changes")
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), required=True)
    parser.add_argument("--foreground-child", action="store_true",
                        help="macOS: clear inherited background priority on this runner's children only")
    args = parser.parse_args()
    if args.foreground_child and platform.system() != "Darwin":
        parser.error("--foreground-child requires macOS")
    source_name, steps, bodies = SCENARIOS[args.scenario]
    source = ROOT / "Silex-Benchmarks/Sources/Physics3D" / source_name
    if Path.cwd().resolve() != ROOT:
        parser.error(f"run from {ROOT}")
    binaries = {"before": args.before.resolve(), "after": args.after.resolve()}
    record = {"schema": 2, "host": platform.platform(), "architecture": platform.machine(),
              "cpu": host_detail("machdep.cpu.brand_string"),
              "physical_memory_bytes": host_detail("hw.memsize"),
              "build": "Release", "backend": "native", "scenario": args.scenario, "bodies": bodies, "steps": steps, "allow_sleep": True,
              "step_seconds": 1 / 60, "repetitions": 7, "warmup_processes_per_configuration": 1,
              "foreground_child": args.foreground_child, "observable_comparison": args.observables,
              "source_sha256": digest(source),
              "runner_sha256": digest(Path(__file__)),
              "candidate_repositories": {name: repository_state(name) for name in
                                         ("Silex", "Packages/GFX.Physics", "Silex-Benchmarks")},
              "compiler_sha256": {"before": digest(args.before_silex or args.silex), "after": digest(args.silex)},
              "columns": ["step", "ms", "awake", "contacts", "checksum", "minimum_y"],
              "binaries": {name: {"sha256": digest(path), "path": str(path)}
                           for name, path in binaries.items()},
              "samples": {"before": [], "after": []}}
    references = {}
    for name in binaries:
        execute(binaries[name], args.scenario, args.foreground_child)
    # Fresh processes include initial settlement as well as the late contact peak.
    for repetition in range(7):
        order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
        for name in order:
            sample = execute(binaries[name], args.scenario, args.foreground_child)
            observables = [row[2:] for row in sample["rows"]]
            key = "shared" if args.observables == "exact" else name
            if key not in references:
                references[key] = observables
            if observables != references[key]:
                raise ValueError(f"changed per-step observables in {name}")
            record["samples"][name].append(sample)
            print(f"{repetition + 1}/7 {name}: mean {sample['mean_ms']:.3f}, "
                  f"p95 {sample['p95_ms']:.3f}, max {sample['max_ms']:.3f} ms", flush=True)
    record["summary"] = {}
    for name, samples in record["samples"].items():
        summary = {}
        for metric in ("mean_ms", "p95_ms", "max_ms", "worst_60_steps_ms"):
            values = [sample[metric] for sample in samples]
            median = statistics.median(values)
            mad = statistics.median(abs(value - median) for value in values)
            summary[metric] = {"median": median, "mad_percent": 100 * mad / median,
                               "min": min(values), "max": max(values)}
        record["summary"][name] = summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, separators=(",", ":")) + "\n")
    for name, summary in record["summary"].items():
        print(name, json.dumps(summary))
    if any(record["summary"][name][metric]["mad_percent"] > 5
           for name in binaries for metric in ("mean_ms", "p95_ms", "worst_60_steps_ms")):
        raise ValueError("unstable campaign (MAD > 5%); raw results saved")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
