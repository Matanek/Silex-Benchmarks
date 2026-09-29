#!/usr/bin/env python3
"""Compare per-step peaks over ten simulated seconds with scene sleep settings."""

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
SOURCE = ROOT / "Silex-Benchmarks/Sources/Physics3D/ColumnPeak.sx"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(binary):
    process = subprocess.run([str(binary)], cwd=ROOT, text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(f"{binary} exited {process.returncode}:\n{process.stderr}")
    rows = list(csv.reader(io.StringIO(process.stdout)))
    if len(rows) != 600 or any(len(row) != 6 for row in rows):
        raise ValueError("expected 600 step,ms,awake,contacts,checksum,minimum_y rows")
    parsed = [[float(value) for value in row] for row in rows]
    for step, row in enumerate(parsed):
        if row[0] != step or not all(math.isfinite(value) for value in row):
            raise ValueError(f"invalid step data: {row}")
        if row[1] < 0 or not 0 <= row[2] <= 256 or row[3] < 0 or row[5] < 0:
            raise ValueError(f"invalid timing, counters or floor escape: {row}")
    if parsed[-1][5] < 0.14:
        raise ValueError("column failed its final floor guard")
    times = [row[1] for row in parsed]
    ordered = sorted(times)
    windows = [statistics.mean(times[start:start + 60]) for start in range(541)]
    return {"rows": parsed, "mean_ms": statistics.mean(times),
            "p95_ms": ordered[math.ceil(len(times) * .95) - 1],
            "max_ms": max(times), "worst_60_steps_ms": max(windows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--silex", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observables", choices=("exact", "deterministic"), default="exact",
                        help="exact across versions, or reproducible per version when floating rounding changes")
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        parser.error(f"run from {ROOT}")
    binaries = {"before": args.before.resolve(), "after": args.after.resolve()}
    record = {"schema": 1, "host": platform.platform(), "architecture": platform.machine(),
              "build": "Release", "bodies": 256, "steps": 600, "allow_sleep": True,
              "step_seconds": 1 / 60, "repetitions": 3, "observable_comparison": args.observables,
              "source_sha256": digest(SOURCE), "compiler_sha256": digest(args.silex),
              "columns": ["step", "ms", "awake", "contacts", "checksum", "minimum_y"],
              "binaries": {name: {"sha256": digest(path), "path": str(path)}
                           for name, path in binaries.items()},
              "samples": {"before": [], "after": []}}
    references = {}
    # Fresh processes include initial settlement as well as the late contact peak.
    for repetition in range(3):
        order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
        for name in order:
            sample = execute(binaries[name])
            observables = [row[2:] for row in sample["rows"]]
            key = "shared" if args.observables == "exact" else name
            if key not in references:
                references[key] = observables
            if observables != references[key]:
                raise ValueError(f"changed per-step observables in {name}")
            record["samples"][name].append(sample)
            print(f"{repetition + 1}/3 {name}: mean {sample['mean_ms']:.3f}, "
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
