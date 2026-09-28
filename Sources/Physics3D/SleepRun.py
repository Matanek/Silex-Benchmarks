#!/usr/bin/env python3
"""Compare free-body sleeping and command wakeup with pinned Jolt."""

import argparse
import json
import math
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, fail, parse_result, self_test, verified_source)


FIELDS = ("sleep_step", "awake_after_command", "velocity_after_wake")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "free-sphere-sleep-wake-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "SleepOracle.cpp", "sleep-oracle")
        candidate = build_silex(mode, "Sleep.sx", "sleep-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        for name, observed in (("Jolt", jolt), ("Silex", silex)):
            if not 1 <= observed["sleep_step"] <= 120:
                fail(f"{name} did not sleep within 120 fixed steps")
            if observed["awake_after_command"] != 1:
                fail(f"{name} did not wake from a velocity command")
            if not math.isclose(observed["velocity_after_wake"], 1.0,
                                rel_tol=0.0, abs_tol=0.00001):
                fail(f"{name} changed the commanded velocity")
        if abs(jolt["sleep_step"] - silex["sleep_step"]) > 2:
            fail("sleep onset differs by more than two fixed steps")
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "oracle": jolt, "silex": silex}
        print(f"physics3d sleep {mode}: Jolt step {jolt['sleep_step']}, "
              f"Silex step {silex['sleep_step']}; both wake on command")
    (BUILD / "sleep-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d sleep qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
