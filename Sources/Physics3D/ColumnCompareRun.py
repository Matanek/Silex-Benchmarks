#!/usr/bin/env python3
"""Compare two prebuilt Release WorldScale binaries on the same column loads.

Run from the workspace root. Build both binaries with the same WorldScale
source and compiler, retaining the first before changing the physics module.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

from WorldScaleRun import MEASURES, ROOT, SOURCE, parse, run, summarize

CASES = (("column", 256, 60), ("topple", 256, 240))


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--silex", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        parser.error(f"run from the workspace root: {ROOT}")
    binaries = {"before": args.before.resolve(), "after": args.after.resolve()}
    record = {
        "schema": 1, "build": "Release", "host": platform.platform(),
        "architecture": platform.machine(), "step_seconds": 1.0 / 60.0,
        "repetitions": 7, "source": str(SOURCE),
        "source_sha256": checksum(ROOT / SOURCE),
        "compiler_sha256": checksum(args.silex),
        "silex": run([str(args.silex), "version"]).strip(),
        "binaries": {name: {"path": str(path), "sha256": checksum(path)}
                     for name, path in binaries.items()},
        "cases": {},
    }
    for mode, count, steps in CASES:
        case = {"bodies": count, "steps": steps, "mode": mode}
        for name, binary in binaries.items():
            case[name] = {"warmup": parse(
                run([str(binary), mode, str(count), str(steps)]),
                mode, count, steps), "samples": []}
        record["cases"][mode] = case
    for repetition in range(7):
        cases = CASES if repetition % 2 == 0 else reversed(CASES)
        order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
        for mode, count, steps in cases:
            case = record["cases"][mode]
            reference = case["before"]["warmup"]
            for name in order:
                sample = parse(run([str(binaries[name]), mode, str(count), str(steps)]),
                               mode, count, steps)
                for key, expected in reference.items():
                    if key not in MEASURES and sample[key] != expected:
                        raise ValueError(f"changed {key} in {mode}/{name}: "
                                         f"{sample[key]} != {expected}")
                case[name]["samples"].append(sample)
                print(f"{repetition + 1}/7 {mode}/{name}: "
                      f"{sample['step_ms'] / steps:.3f} ms/step", flush=True)
    for mode, case in record["cases"].items():
        for name in binaries:
            case[name]["summary"] = summarize(case[name]["samples"])
        before = case["before"]["summary"]["step_ms"]["median"]
        after = case["after"]["summary"]["step_ms"]["median"]
        case["speedup"] = before / after
        print(f"{mode}: {before / case['steps']:.3f} -> "
              f"{after / case['steps']:.3f} ms/step ({before / after:.2f}x)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    if any(not case[name]["summary"]["stable_step_timing"]
           for case in record["cases"].values() for name in binaries):
        raise ValueError("MAD exceeds 5%; raw results saved, rerun in a quiet session")
    print(f"raw results: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ColumnCompareRun: {error}", file=sys.stderr)
        sys.exit(1)
