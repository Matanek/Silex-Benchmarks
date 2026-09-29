#!/usr/bin/env python3
"""Record Jolt's missed one-step sensor crossing and Silex's transient events."""

import argparse
import json
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, parse_result, self_test, verified_source)


FIELDS = ("added", "persisted", "removed", "final_x", "final_vx")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "fast-one-step-sensor-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "FastSensorOracle.cpp", "fast-sensor-oracle")
        candidate = build_silex(mode, "FastSensor.sx", "fast-sensor-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        if tuple(jolt[field] for field in FIELDS[:3]) != (0.0, 0.0, 0.0):
            fail(f"Jolt sensor behavior changed: {jolt}")
        if tuple(silex[field] for field in FIELDS[:3]) != (1.0, 0.0, 1.0):
            fail(f"Silex transient sensor events changed: {silex}")
        for name, observed in (("Jolt", jolt), ("Silex", silex)):
            if abs(observed["final_x"] - 1.0) > 0.001 or \
                    abs(observed["final_vx"] - 120.0) > 0.001:
                fail(f"{name} sensor changed motion: {observed}")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                  "oracle": jolt, "silex": silex}
        print(f"physics3d fast sensor {mode}: recorded event-policy difference")
    (BUILD / "fast-sensor-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d fast sensor qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
