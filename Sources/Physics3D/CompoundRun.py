#!/usr/bin/env python3
"""Compare an oriented compound's gap, ray and child IDs with pinned Jolt."""

import argparse
import json
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, compare, fail, parse_result, self_test, verified_source)


FIELDS = ("separation", "collision_child", "ray_fraction", "ray_child")
EXPECTED = {"separation": 0.25, "collision_child": 22.0,
            "ray_fraction": 0.5, "ray_child": 22.0}
TOLERANCE = 0.00001


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "rotated-static-compound-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest,
              "absolute_tolerance": TOLERANCE, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "CompoundOracle.cpp", "compound-oracle")
        candidate = build_silex(mode, "Compound.sx", "compound-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        compare(jolt, EXPECTED, TOLERANCE, FIELDS)
        compare(silex, EXPECTED, TOLERANCE, FIELDS)
        compare(silex, jolt, TOLERANCE, FIELDS)
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "analytical": EXPECTED, "oracle": jolt,
                                 "silex": silex}
        print(f"physics3d compound {mode}: gap, ray and child IDs agree")
    (BUILD / "compound-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d compound qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
