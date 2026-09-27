#!/usr/bin/env python3
"""Compare Silex 3D shape-pair and ray queries with pinned Jolt."""

import argparse
import json
import math
import platform
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex, checked,
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
        for name in ("first_x_mm", "second_x_mm", "second_degrees",
                     "ray_origin_x_mm", "ray_delta_x_mm"):
            value = case.get(name)
            if type(value) is not int or abs(value) > 1_000_000:
                fail(f"invalid {name} in {identity}")
        axis = case.get("second_axis")
        if not isinstance(axis, list) or len(axis) != 3 or any(
            type(value) is not int or abs(value) > 1000 for value in axis
        ) or axis == [0, 0, 0]:
            fail(f"invalid rotation axis in {identity}")
        if not 0 <= case["second_degrees"] <= 360 or case["ray_delta_x_mm"] <= 0:
            fail(f"invalid rotation or ray length in {identity}")
        for name in ("expected_separation", "expected_ray_fraction"):
            value = case.get(name)
            if value is not None and (
                type(value) not in (int, float) or not math.isfinite(value)
            ):
                fail(f"invalid {name} in {identity}")
        if "expected_ray_fraction" in case and not 0 <= case["expected_ray_fraction"] <= 1:
            fail(f"invalid expected ray fraction in {identity}")
    return fixture


def arguments(case):
    return [str(value) for value in (
        case["first"], case["second"], case["first_x_mm"],
        case["second_x_mm"], case["second_degrees"], *case["second_axis"],
        case["ray_origin_x_mm"], case["ray_delta_x_mm"],
    )]


def check_witness(case, result, prefix, shape, center_x, degrees, axis, tolerance):
    point = [result[f"{prefix}_point_{axis}"] for axis in "xyz"]
    offset = [point[0] - center_x, point[1], point[2]]
    if shape == "sphere":
        if abs(math.sqrt(sum(value * value for value in offset)) - 1) > tolerance:
            fail(f"{case['id']}: {prefix} witness is not on its sphere")
        return
    axis_length = math.sqrt(sum(value * value for value in axis))
    unit = [value / axis_length for value in axis]
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    cross = [unit[1] * offset[2] - unit[2] * offset[1],
             unit[2] * offset[0] - unit[0] * offset[2],
             unit[0] * offset[1] - unit[1] * offset[0]]
    projection = sum(value * component for value, component in zip(unit, offset))
    local = [value * cosine - component * sine + direction * projection * (1 - cosine)
             for value, component, direction in zip(offset, cross, unit)]
    if any(abs(value) > 1 + tolerance for value in local) or not any(
        abs(abs(value) - 1) <= tolerance for value in local
    ):
        fail(f"{case['id']}: {prefix} witness is not on its box")


def check_candidate(case, actual, oracle, tolerance):
    compare(actual, oracle, tolerance,
            ("separation", "ray_fraction", "normal_x", "normal_y", "normal_z"))
    normal = [actual[f"normal_{axis}"] for axis in "xyz"]
    if abs(math.sqrt(sum(value * value for value in normal)) - 1) > tolerance:
        fail(f"{case['id']}: non-unit candidate normal")
    check_witness(case, actual, "first", case["first"],
                  case["first_x_mm"] / 1000, 0, [0, 1, 0], tolerance)
    check_witness(case, actual, "second", case["second"],
                  case["second_x_mm"] / 1000,
                  case["second_degrees"], case["second_axis"], tolerance)
    first = [actual[f"first_point_{axis}"] for axis in "xyz"]
    second = [actual[f"second_point_{axis}"] for axis in "xyz"]
    offset = [b - a for a, b in zip(first, second)]
    projection = sum(value * axis for value, axis in zip(offset, normal))
    if actual["separation"] >= 0:
        if abs(projection - actual["separation"]) > tolerance:
            fail(f"{case['id']}: witness projection differs from separation")
        if math.sqrt(sum(
            (value - projection * axis) ** 2
            for value, axis in zip(offset, normal)
        )) > tolerance:
            fail(f"{case['id']}: separated witnesses are not a closest pair")


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
        candidate = build_silex(mode, "Geometry.sx", "geometry-silex", physics=True)
        results = {}
        for case in fixture["cases"]:
            actual = parse_result(checked([str(binary), *arguments(case)]), FIELDS)
            silex = parse_result(checked([str(candidate), *arguments(case)]), FIELDS)
            reference = {}
            if "expected_separation" in case:
                reference["separation"] = case["expected_separation"]
            if "expected_ray_fraction" in case:
                reference["ray_fraction"] = case["expected_ray_fraction"]
            compare(actual, reference, fixture["absolute_tolerance"], reference)
            if case["second_degrees"] == 0:
                first_x = case["first_x_mm"] / 1000
                second_x = case["second_x_mm"] / 1000
                compare(actual, {
                    "first_point_x": first_x + 1,
                    "second_point_x": second_x - 1,
                    "normal_x": 1,
                }, fixture["absolute_tolerance"],
                    ("first_point_x", "second_point_x", "normal_x"))
            try:
                check_candidate(case, silex, actual, fixture["absolute_tolerance"])
            except ValueError as error:
                fail(f"{case['id']}: {error}")
            results[case["id"]] = {"oracle": actual, "silex": silex}
        record["modes"][mode] = results
        print(f"physics3d geometry {mode}: {len(results)} Jolt and Silex cases agree")
    (BUILD / "geometry-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d geometry qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
