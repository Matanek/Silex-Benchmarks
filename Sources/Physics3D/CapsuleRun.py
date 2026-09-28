#!/usr/bin/env python3
"""Compare rotated capsule/box witnesses with pinned Jolt and geometry."""

import argparse
import json
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, compare, fail, parse_result, self_test, verified_source)


CENTERS = (1600, 1500, 1400)
FIELDS = ("separation", "first_x", "first_y", "second_x", "second_y", "normal_x")
TOLERANCE = 0.0001


def expected(center):
    gap = center / 1000 - 1.5
    return {"separation": gap, "first_x": 1.0 + gap,
            "first_y": 0.4330127019, "second_x": 1.0,
            "second_y": 0.4330127019, "normal_x": -1.0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "rotated-capsule-box-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest,
              "absolute_tolerance": TOLERANCE, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "CapsuleOracle.cpp", "capsule-oracle")
        candidate = build_silex(mode, "Capsule.sx", "capsule-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        candidate_fields = tuple(f"{field}_{center}" for center in CENTERS for field in FIELDS)
        candidate_values = parse_result(checked([str(candidate)]), candidate_fields)
        results = {}
        for center in CENTERS:
            reference = expected(center)
            jolt = parse_result(checked([str(oracle), str(center)]), FIELDS)
            silex = {field: candidate_values[f"{field}_{center}"] for field in FIELDS}
            compare(jolt, reference, TOLERANCE, FIELDS)
            compare(silex, reference, TOLERANCE, FIELDS)
            compare(silex, jolt, TOLERANCE, FIELDS)
            results[str(center)] = {"analytical": reference, "oracle": jolt,
                                    "silex": silex}
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "cases": results}
        print(f"physics3d capsule {mode}: {len(CENTERS)} separation and witness cases agree")
    (BUILD / "capsule-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d capsule qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
