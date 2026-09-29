#!/usr/bin/env python3
"""Compare a freely oscillating 3D distance spring with pinned Jolt."""

import argparse
import json
from pathlib import Path
import sys

from Run import BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked, fail, parse_result, verified_source


FIELDS = ("length_12", "length_30", "length_60", "length_120")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "distance-spring-free-oscillation-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    modes = ("Debug", "Release") if options.mode == "both" else (options.mode,)
    for mode in modes:
        oracle = build_oracle(source, mode, HERE / "DistanceSpringOracle.cpp", "distance-spring-oracle")
        candidate = build_silex(mode, "DistanceSpring.sx", "distance-spring-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        for point in FIELDS:
            tolerance = 0.1 if point == "length_12" else 0.05
            if abs(jolt[point] - silex[point]) > tolerance:
                fail(f"{mode} {point}: Jolt {jolt[point]} versus Silex {silex[point]}")
        if not (jolt["length_12"] < 2.0 and silex["length_12"] < 2.0):
            fail("spring did not overshoot the target")
        for name, values in (("Jolt", jolt), ("Silex", silex)):
            if not (values["length_30"] > 2.0 and
                    values["length_120"] > 2.0 and
                    abs(values["length_120"] - 2.0) < 0.01 and
                    abs(values["length_120"] - 2.0) <
                    abs(values["length_60"] - 2.0)):
                fail(f"{name} spring did not decay toward the target")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                  "oracle": jolt, "silex": silex}
        print(f"physics3d distance spring {mode}: four oscillation samples remain within the declared tolerance")
    (BUILD / "distance-spring-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d distance spring qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
