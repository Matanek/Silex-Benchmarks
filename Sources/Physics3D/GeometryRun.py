#!/usr/bin/env python3
"""Record pinned Jolt shape-pair and ray observations before 3D query work."""

import argparse
import json
import math
import platform
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, checked,
                 compare, fail, parse_result, verified_source)


FIELDS = (
    "separation", "first_point_x", "first_point_y", "first_point_z",
    "second_point_x", "second_point_y", "second_point_z",
    "normal_x", "normal_y", "normal_z", "ray_fraction",
)


def fixture_data():
    with (HERE / "GeometryFixture.json").open(encoding="utf-8") as stream:
        fixture = json.load(stream)
    if fixture.get("schema") != 1 or fixture.get("oracle_revision") != REFERENCE:
        fail("geometry fixture schema or Jolt revision differs")
    tolerance = fixture.get("absolute_tolerance")
    if type(tolerance) not in (int, float) or not 0 < tolerance < 0.001:
        fail("invalid geometry fixture tolerance")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("geometry fixture has no cases")
    identities = set()
    for case in cases:
        identity = case.get("id")
        if not isinstance(identity, str) or not identity or identity in identities:
            fail("invalid or duplicate geometry case identity")
        identities.add(identity)
        for name in ("first", "second"):
            if case.get(name) not in ("sphere", "box"):
                fail(f"invalid {name} shape in {identity}")
        for name in ("first_x_mm", "second_x_mm", "second_y_degrees",
                     "ray_origin_x_mm", "ray_delta_x_mm"):
            value = case.get(name)
            if type(value) is not int or abs(value) > 1_000_000:
                fail(f"invalid {name} in {identity}")
        if not 0 <= case["second_y_degrees"] <= 360 or case["ray_delta_x_mm"] <= 0:
            fail(f"invalid rotation or ray length in {identity}")
        for name in ("expected_separation", "expected_ray_fraction"):
            value = case.get(name)
            if type(value) not in (int, float) or not math.isfinite(value):
                fail(f"invalid {name} in {identity}")
        if not 0 <= case["expected_ray_fraction"] <= 1:
            fail(f"invalid expected ray fraction in {identity}")
    return fixture


def arguments(case):
    return [str(case[name]) for name in (
        "first", "second", "first_x_mm", "second_x_mm", "second_y_degrees",
        "ray_origin_x_mm", "ray_delta_x_mm",
    )]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    fixture = fixture_data()
    source, digest = verified_source(options.archive)
    record = {
        "schema": 1, "fixture": "convex-pairs-v1", "oracle_revision": REFERENCE,
        "archive_sha256": digest, "host": platform.platform(),
        "absolute_tolerance": fixture["absolute_tolerance"], "modes": {},
    }
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        binary = build_oracle(source, mode, HERE / "GeometryOracle.cpp", "geometry-oracle")
        results = {}
        for case in fixture["cases"]:
            actual = parse_result(checked([str(binary), *arguments(case)]), FIELDS)
            reference = {
                "separation": case["expected_separation"],
                "ray_fraction": case["expected_ray_fraction"],
            }
            compare(actual, reference, fixture["absolute_tolerance"], reference)
            if case["second_y_degrees"] == 0:
                first_x = case["first_x_mm"] / 1000
                second_x = case["second_x_mm"] / 1000
                compare(actual, {
                    "first_point_x": first_x + 1,
                    "second_point_x": second_x - 1,
                    "normal_x": 1,
                }, fixture["absolute_tolerance"],
                    ("first_point_x", "second_point_x", "normal_x"))
            results[case["id"]] = actual
        record["modes"][mode] = results
        print(f"physics3d geometry {mode}: {len(results)} Jolt cases match analytical checks")
    (BUILD / "geometry-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d geometry qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
