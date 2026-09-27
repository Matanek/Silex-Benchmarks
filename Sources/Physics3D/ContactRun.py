#!/usr/bin/env python3
"""Compare the first head-on sphere response with pinned Jolt."""

import argparse
import json
import math
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, compare, fail, parse_result, self_test,
                 verified_source)


FIELDS = ("first_x", "second_x", "first_vx", "second_vx")


def fixture():
    with (HERE / "ContactFixture.json").open(encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema") != 1 or data.get("oracle_revision") != REFERENCE:
        fail("contact fixture schema or Jolt revision differs")
    for name in ("radius_mm", "center_mm", "speed_mm_s", "step_ms"):
        value = data.get(name)
        if type(value) is not int or not 0 < value <= 100_000:
            fail(f"invalid contact fixture field: {name}")
    if data["center_mm"] != data["radius_mm"]:
        fail("contact fixture must start at first tangency")
    tolerance = data.get("absolute_tolerance")
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 0 < tolerance < 0.001:
        fail("invalid contact tolerance")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    data = fixture()
    source, digest = verified_source(options.archive)
    arguments = [str(data[name]) for name in
                 ("radius_mm", "center_mm", "speed_mm_s", "step_ms")]
    expected = {"first_x": -data["radius_mm"] / 1000,
                "second_x": data["radius_mm"] / 1000,
                "first_vx": 0.0, "second_vx": 0.0}
    record = {"schema": 1, "fixture": data["id"], "oracle_revision": REFERENCE,
              "archive_sha256": digest, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "ContactOracle.cpp", "contact-oracle")
        candidate = build_silex(mode, "Contact.sx", "contact-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail(f"incompatible Jolt precision: {configuration}")
        actual = parse_result(checked([str(oracle), *arguments]), FIELDS)
        silex = parse_result(checked([str(candidate), *arguments]), FIELDS)
        compare(actual, expected, data["absolute_tolerance"], FIELDS)
        compare(silex, expected, data["absolute_tolerance"], FIELDS)
        compare(silex, actual, data["absolute_tolerance"], FIELDS)
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "oracle": actual, "silex": silex,
                                 "analytical": expected}
        print(f"physics3d contact {mode}: Jolt, Silex and analytical witness agree")
    (BUILD / "contact-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d contact qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
