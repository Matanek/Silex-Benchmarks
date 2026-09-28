#!/usr/bin/env python3
"""Compare a suspended rigid point constraint with pinned Jolt."""

import argparse
import json
import math
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, parse_result, self_test, verified_source)


FIELDS = ("anchor_error", "height", "reaction_weight_ratio",
          "pendulum_error", "pendulum_x")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "point-gravity-pendulum-v2",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "PointOracle.cpp", "point-oracle")
        candidate = build_silex(mode, "Point.sx", "point-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        for name, observed in (("Jolt", jolt), ("Silex", silex)):
            if observed["anchor_error"] > 0.005:
                fail(f"{name} point anchor drifted: {observed}")
            if not math.isclose(observed["height"], 1.0, abs_tol=0.005):
                fail(f"{name} body height drifted: {observed}")
            if not math.isclose(observed["reaction_weight_ratio"], 1.0,
                                abs_tol=0.1):
                fail(f"{name} reaction differs from weight: {observed}")
            if observed["pendulum_error"] > 0.01:
                fail(f"{name} pendulum point drifted: {observed}")
            if abs(observed["pendulum_x"]) < 0.1:
                fail(f"{name} pendulum did not move: {observed}")
        if abs(jolt["anchor_error"] - silex["anchor_error"]) > 0.005:
            fail("Jolt and Silex suspended point errors differ")
        if abs(jolt["pendulum_x"] - silex["pendulum_x"]) > 0.05:
            fail("Jolt and Silex pendulum positions differ")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                  "oracle": jolt, "silex": silex}
        print(f"physics3d point {mode}: Jolt and Silex hold the anchor and weight reaction")
    (BUILD / "point-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d point qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
