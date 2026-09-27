#!/usr/bin/env python3
"""Qualify the first Silex 3D foundation witness against pinned Jolt."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile


REFERENCE = "e77f175595e64cb44218cc9d9d56fc365ad0e36a"
ARCHIVE_SHA256 = "ff13202d21a7a09efea72534a0a041cd4971cb9ac66b53262275881387cc6871"
ARCHIVE_URL = f"https://github.com/jrouwe/JoltPhysics/archive/{REFERENCE}.zip"
CMAKE_OPTIONS = (
    "-DDOUBLE_PRECISION=OFF", "-DCROSS_PLATFORM_DETERMINISTIC=OFF",
    "-DTARGET_UNIT_TESTS=OFF", "-DTARGET_HELLO_WORLD=OFF",
    "-DTARGET_PERFORMANCE_TEST=OFF", "-DTARGET_SAMPLES=OFF",
    "-DTARGET_VIEWER=OFF", "-DJPH_USE_MTL=OFF", "-DJPH_USE_VK=OFF",
    "-DJPH_USE_DX12=OFF", "-DJPH_USE_CPU_COMPUTE=ON",
    "-DINTERPROCEDURAL_OPTIMIZATION=OFF", "-DGENERATE_DEBUG_SYMBOLS=OFF",
)
FIELDS = (
    "position_x", "position_y", "position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "rotated_x", "rotated_y", "rotated_z", "inertia_x",
)
HERE = Path(__file__).resolve().parent
GROUP = HERE.parents[2]
PROJECT = GROUP.parents[2]
BUILD = GROUP / ".silex" / "physics3d-oracle"


def fail(message):
    raise ValueError(message)


def checked(command, *, cwd=GROUP, environment=None):
    result = subprocess.run(
        command, cwd=cwd, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        fail(f"command failed ({result.returncode}): {' '.join(map(str, command))}\n"
             f"{result.stdout}{result.stderr}")
    return result.stdout


def fixture_data(path):
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema") != 1 or data.get("oracle_revision") != REFERENCE:
        fail("fixture schema or Jolt revision differs from the accepted reference")
    if data.get("id") != "free-sphere-y-quarter-turn-v1":
        fail("unknown physics3d fixture identity")
    for name in ("radius", "mass", "steps", "step_millis"):
        value = data.get(name)
        if type(value) is not int or not 0 < value <= 1_000_000:
            fail(f"invalid positive fixture field: {name}")
    for name in ("position", "velocity"):
        value = data.get(name)
        if not isinstance(value, list) or len(value) != 3 or any(
            type(component) is not int or not 0 <= component <= 1_000_000
            for component in value
        ):
            fail(f"invalid vector fixture field: {name}")
    tolerance = data.get("absolute_tolerance")
    if type(tolerance) not in (int, float) or not 0 < tolerance < 0.001:
        fail("invalid fixture tolerance")
    return data


def arguments(data):
    return [str(value) for value in (
        data["radius"], data["mass"], *data["position"],
        *data["velocity"], data["steps"], data["step_millis"],
    )]


def parse_result(output, fields=FIELDS):
    result = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator != "=" or key not in fields or key in result:
            fail(f"invalid or duplicate result field: {line}")
        try:
            number = float(value)
        except ValueError:
            fail(f"non-numeric result field: {key}")
        if not math.isfinite(number):
            fail(f"non-finite result field: {key}")
        result[key] = number
    if set(result) != set(fields):
        fail(f"missing result fields: {sorted(set(fields) - set(result))}")
    return result


def expected(data):
    elapsed = data["steps"] * data["step_millis"] / 1000
    position = [
        start + speed * elapsed
        for start, speed in zip(data["position"], data["velocity"])
    ]
    return dict(zip(FIELDS, (
        *position, *data["velocity"], 0, 0, -1,
        0.4 * data["mass"] * data["radius"] ** 2,
    )))


def compare(actual, reference, tolerance, fields=FIELDS):
    for key in fields:
        if abs(actual[key] - reference[key]) > tolerance:
            fail(f"{key}: {actual[key]} differs from {reference[key]}")


def self_test():
    data = fixture_data(HERE / "Fixture.json")
    for changed in (
        {**data, "oracle_revision": "0" * 40},
        {**data, "position": [1, -2, 3]},
    ):
        try:
            fixture_data_from_value(changed)
        except ValueError:
            pass
        else:
            fail("fixture guard accepted invalid input")
    baseline = expected(data)
    output = "\n".join(f"{key}={value}" for key, value in baseline.items())
    for invalid in (output.replace(f"position_x={baseline['position_x']}", "position_x=nan"),
                    output + "\nposition_x=1", output.replace("inertia_x=8.0", "")):
        try:
            parse_result(invalid)
        except ValueError:
            pass
        else:
            fail("result guard accepted invalid output")
    altered = {**baseline, "position_x": baseline["position_x"] + 1}
    try:
        compare(altered, baseline, data["absolute_tolerance"])
    except ValueError:
        pass
    else:
        fail("comparator accepted a perturbed result")
    print("physics3d guard self-test: ok")


def fixture_data_from_value(data):
    temp = BUILD / "self-test-fixture.json"
    BUILD.mkdir(parents=True, exist_ok=True)
    temp.write_text(json.dumps(data), encoding="utf-8")
    try:
        return fixture_data(temp)
    finally:
        temp.unlink()


def verified_source(archive_override):
    BUILD.mkdir(parents=True, exist_ok=True)
    archive = archive_override or BUILD / "JoltPhysics.zip"
    if archive_override and not archive.is_file():
        fail(f"provided Jolt archive is missing: {archive}")
    if not archive.exists():
        checked(["curl", "--fail", "--location", "--silent", "--show-error",
                 ARCHIVE_URL, "--output", str(archive)])
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != ARCHIVE_SHA256:
        fail(f"Jolt archive checksum differs: {digest}")
    source = BUILD / f"JoltPhysics-{REFERENCE}"
    with zipfile.ZipFile(archive) as package:
        if any(not name.startswith(f"JoltPhysics-{REFERENCE}/") for name in package.namelist()):
            fail("Jolt archive contains an unexpected source root")
        package.extractall(BUILD)
    if "project(JoltPhysics VERSION 5.6.0" not in (source / "Build/CMakeLists.txt").read_text():
        fail("Jolt source version differs from v5.6.0")
    return source, digest


def build_oracle(source, mode, oracle_source=HERE / "Oracle.cpp", stem="oracle"):
    directory = BUILD / f"jolt-{mode}"
    checked(["cmake", "-S", str(source / "Build"), "-B", str(directory),
             "-G", "Unix Makefiles", f"-DCMAKE_BUILD_TYPE={mode}", *CMAKE_OPTIONS])
    checked(["cmake", "--build", str(directory), "--target", "Jolt", "-j", "8"])
    binary = BUILD / f"{stem}-{mode.lower()}"
    definitions = ["-DJPH_OBJECT_STREAM", "-DJPH_USE_CPU_COMPUTE"]
    if mode in ("Debug", "Release"):
        definitions += ["-DJPH_DEBUG_RENDERER", "-DJPH_PROFILE_ENABLED"]
    if mode == "Release":
        definitions.append("-DNDEBUG")
    compiler = shutil.which("clang++") or fail("clang++ unavailable")
    deployment = (["-mmacosx-version-min=" + platform.mac_ver()[0]]
                  if platform.system() == "Darwin" else [])
    checked([compiler, "-std=c++23", "-fno-rtti", "-fno-exceptions",
             *deployment,
             "-O0" if mode == "Debug" else "-O2", *definitions,
             "-I", str(source), str(oracle_source),
             str(directory / "libJolt.a"), "-pthread", "-o", str(binary)])
    return binary


def build_silex(mode):
    standard = PROJECT / "Packages" / "STD"
    checked(["silex", "link", str(standard), "--workspace", str(GROUP)])
    resolved = checked(["silex", "packages", "resolve",
                        "Silex-Benchmarks/Sources/Physics3D/Silex.sx"])
    if f"STD 0.22.0 workspace-link {standard}" not in resolved:
        fail("STD does not resolve to the intended workspace source")
    binary = BUILD / f"silex-{mode.lower()}"
    environment = os.environ.copy()
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(GROUP / ".silex" / "zig")
    checked(["silex", "compile", "Silex-Benchmarks/Sources/Physics3D/Silex.sx",
             "--debug" if mode == "Debug" else "--release",
             "--output", str(binary)], environment=environment)
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    if options.self_test:
        return
    data = fixture_data(HERE / "Fixture.json")
    source, digest = verified_source(options.archive)
    record = {
        "schema": 1, "fixture": data["id"], "oracle_revision": REFERENCE,
        "archive_sha256": digest, "host": platform.platform(),
        "architecture": platform.machine(),
        "compiler": checked(["clang++", "--version"]).splitlines()[0],
        "silex": checked(["silex", "version"]).strip(),
        "build": {"generator": "Unix Makefiles", "cmake_options": CMAKE_OPTIONS,
                  "precision": "single", "workers": 1,
                  "job_system": "JobSystemSingleThreaded"},
        "modes": {},
    }
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode)
        silex = build_silex(mode)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail(f"incompatible Jolt precision: {configuration}")
        oracle_result = parse_result(checked([str(oracle), *arguments(data)]))
        silex_result = parse_result(checked([str(silex), *arguments(data)]))
        analytical = expected(data)
        tolerance = data["absolute_tolerance"]
        compare(oracle_result, analytical, tolerance)
        compare(silex_result, analytical, tolerance)
        compare(silex_result, oracle_result, tolerance)
        record["modes"][mode] = {
            "jolt_configuration": configuration,
            "oracle": oracle_result, "silex": silex_result,
            "analytical": analytical,
        }
        print(f"physics3d {mode}: Jolt, Silex and analytical witness agree")
    (BUILD / "qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"physics3d qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
