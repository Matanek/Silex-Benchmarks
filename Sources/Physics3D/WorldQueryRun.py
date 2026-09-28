#!/usr/bin/env python3
"""Compare a nearest world ray hit with pinned Jolt."""

import argparse
import json
import math
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, parse_result, self_test, verified_source)


FIELDS = ("near_fraction", "near_selected")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "world-ray-two-spheres-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "WorldQueryOracle.cpp", "world-query-oracle")
        candidate = build_silex(mode, "WorldQuery.sx", "world-query-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        for name, observed in (("Jolt", jolt), ("Silex", silex)):
            if observed["near_selected"] != 1.0:
                fail(f"{name} selected the wrong body: {observed}")
            if not math.isclose(observed["near_fraction"], 0.25, abs_tol=0.00001):
                fail(f"{name} nearest ray fraction drifted: {observed}")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                  "oracle": jolt, "silex": silex}
        print(f"physics3d world query {mode}: Jolt and Silex select the near body")
    (BUILD / "world-query-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d world query qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
