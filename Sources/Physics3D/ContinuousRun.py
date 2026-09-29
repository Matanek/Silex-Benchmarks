#!/usr/bin/env python3
"""Compare a fast sphere hitting a thin wall with pinned Jolt CCD."""

import argparse
import json
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, parse_result, self_test, verified_source)


FIELDS = ("added", "final_x", "final_vx")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "continuous-sphere-thin-wall-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "ContinuousOracle.cpp", "continuous-oracle")
        candidate = build_silex(mode, "Continuous.sx", "continuous-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        for name, observed in (("Jolt", jolt), ("Silex", silex)):
            if observed["added"] != 1.0 or abs(observed["final_vx"]) > 0.001:
                fail(f"{name} did not stop with one contact: {observed}")
            if not -0.31 <= observed["final_x"] <= -0.25:
                fail(f"{name} stopped outside the wall's near face: {observed}")
        if abs(jolt["final_x"] - silex["final_x"]) > 0.03:
            fail(f"continuous stop differs from Jolt beyond contact slop: {jolt}, {silex}")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                  "oracle": jolt, "silex": silex}
        print(f"physics3d continuous {mode}: thin wall stops the fast sphere")
    (BUILD / "continuous-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d continuous qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
