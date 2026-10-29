#!/usr/bin/env python3
"""Qualify edited height terrains and loaded mixed constraints against pinned Jolt."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import sys

from Run import BUILD, GROUP, HERE, PROJECT, REFERENCE, checked, fail, parse_result, verified_source

ENTRY = "Packages/GFX.Physics/Tests/Consumer/Tests/TerrainConstraintQualification3D.sx"
EXPECTED = {"terrain_before": -0.027, "terrain_raised": 0.4,
            "terrain_outside": 0.011, "terrain_restored": -0.041, "terrain_hole": 0.0}
TOLERANCES = {key: 0.0002 for key in EXPECTED}
TOLERANCES["terrain_hole"] = 0.0
for label in ("before", "raised", "outside", "restored"):
    name = "terrain_" + label
    normal = (0.0, 1.0, 0.0) if label == "raised" else (-0.02 / 0.75, 1.0, 0.03 / 1.25)
    length = math.sqrt(sum(value * value for value in normal))
    for axis, value in zip("xyz", normal):
        EXPECTED[name + "_n" + axis] = value / length
        TOLERANCES[name + "_n" + axis] = 0.002
    EXPECTED[name + "_fraction"] = (2.0 - EXPECTED[name]) / 4.0
    TOLERANCES[name + "_fraction"] = 0.00005
for case in (0, 1):
    prefix = f"pulley_{case}_"
    ratio, z1, z2 = (1.0, 0.0, 0.0) if case == 0 else (2.0, 0.4, -0.6)
    l1, l2 = math.sqrt(36 + z1 * z1), math.sqrt(36 + z2 * z2)
    length = l1 + ratio * l2
    k = ratio * (6.0 / l2) / (6.0 / l1)
    a2 = 9.81 * (2 * k - 8) / (8 + 2 * k * k)
    final_l2 = math.sqrt(7.75 * 7.75 + z2 * z2)
    final_l1 = length - ratio * final_l2
    vertical = math.sqrt(final_l1 * final_l1 - z1 * z1)
    tension = 19.62 * final_l1 / vertical
    values = {"positions": (8.0 if case == 0 else 48.0, 0.0),
              "first_vy": (-k * a2 / 60, 0.005), "second_vy": (a2 / 60, 0.005),
              "final_first_vy": (0.0, 0.02), "final_second_vy": (0.0, 0.02),
              "first_y": (8 - vertical, 0.01), "second_y": (0.25, 0.01),
              "tension": (tension, 0.5), "guide_first_z": (-tension * z1 / final_l1, 0.5),
              "guide_second_z": (-ratio * tension * z2 / final_l2, 0.5), "lifetime": (1.0, 0.0)}
    for name, (value, tolerance) in values.items():
        EXPECTED[prefix + name] = value
        TOLERANCES[prefix + name] = tolerance
EXPECTED.update({"path_blocked_x": 1.3, "path_support_y": 58.86,
                 "path_max_motor": 20.0, "path_released": 1.0, "path_lifetime": 1.0})
TOLERANCES.update({"path_blocked_x": 0.02, "path_support_y": 1.0,
                   "path_max_motor": 0.0001, "path_released": 0.0, "path_lifetime": 0.0})
BOUNDS = {"pulley_0_max_error": 0.01, "pulley_1_max_error": 0.01, "path_max_error": 0.03, "path_normal_error": 0.02}
FIELDS = tuple(EXPECTED) + tuple(BOUNDS)


def verify(actual, reference=EXPECTED):
    for key, expected in reference.items():
        if abs(actual[key] - expected) > TOLERANCES[key]:
            fail(f"{key}: {actual[key]} differs from {expected} (tolerance {TOLERANCES[key]})")
    for key, maximum in BOUNDS.items():
        if not 0.0 <= actual[key] < maximum:
            fail(f"{key}: {actual[key]} exceeds the predeclared residual bound {maximum}")


def self_test():
    valid = {**EXPECTED, **{key: limit / 2 for key, limit in BOUNDS.items()}}
    lines = [f"{key}={value}" for key, value in valid.items()]
    verify(parse_result("\n".join(lines), FIELDS))
    for invalid in ("\n".join(lines[:-1]), "\n".join(lines + lines[:1]),
                    "\n".join(lines + ["unknown=1"]),
                    "\n".join(lines[1:] + [lines[0].split("=")[0] + "=nan"]),
                    "\n".join(lines[1:] + [lines[0].split("=")[0] + "=inf"])):
        try:
            parse_result(invalid, FIELDS)
        except ValueError:
            pass
        else:
            fail("terrain/constraint parser accepted invalid observations")
    for key in FIELDS:
        perturbed = dict(valid)
        perturbed[key] = BOUNDS[key] * 2 if key in BOUNDS else valid[key] + max(0.001, TOLERANCES[key] * 2)
        try:
            verify(perturbed)
        except ValueError:
            pass
        else:
            fail(f"terrain/constraint comparator accepted a perturbation of {key}")


def oracle(source, mode):
    library = BUILD / f"jolt-{mode}" / "libJolt.a"
    cache = library.parent / "CMakeCache.txt"
    if not library.is_file() or not cache.is_file():
        fail("build the pinned Jolt library with the foundation runner before this small witness")
    for expected in (f"CMAKE_BUILD_TYPE:STRING={mode}", "DOUBLE_PRECISION:BOOL=OFF"):
        if expected not in cache.read_text():
            fail(f"cached Jolt configuration differs: {expected}")
    binary = BUILD / f"terrain-constraints-oracle-{mode.lower()}"
    definitions = ["-DJPH_OBJECT_STREAM", "-DJPH_USE_CPU_COMPUTE", "-DJPH_DEBUG_RENDERER", "-DJPH_PROFILE_ENABLED"]
    if mode == "Release":
        definitions.append("-DNDEBUG")
    deployment = ["-mmacosx-version-min=" + platform.mac_ver()[0]] if platform.system() == "Darwin" else []
    checked([shutil.which("clang++") or fail("clang++ unavailable"), "-std=c++23",
             "-fno-rtti", "-fno-exceptions", *deployment,
             "-O0" if mode == "Debug" else "-O2", *definitions, "-I", str(source),
             str(HERE / "TerrainConstraintsOracle.cpp"), str(library), "-pthread", "-o", str(binary)])
    return binary


def build_candidate(mode):
    for directory in (PROJECT / "Packages/STD", GROUP / "Packages/GFX.Physics"):
        checked(["silex", "link", str(directory), "--workspace", str(GROUP)])
    resolved = checked(["silex", "packages", "resolve", ENTRY])
    for name, version, directory in (("STD", "0.22.0", PROJECT / "Packages/STD"),
                                      ("GFX.Physics", "0.7.0", GROUP / "Packages/GFX.Physics")):
        if f"{name} {version} workspace-link {directory}" not in resolved:
            fail(f"{name} does not resolve to the intended sources")
    (BUILD / "terrain-constraints-resolution.log").write_text(resolved)
    binary = BUILD / f"terrain-constraints-silex-{mode.lower()}"
    checked(["silex", "compile", ENTRY, "--debug" if mode == "Debug" else "--release", "--output", str(binary)])
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the workspace or Spec group root: {GROUP}")
    self_test()
    if options.self_test:
        print(f"terrain/constraint parser and {len(FIELDS)} perturbation guards: green")
        return
    source, digest = verified_source(None)
    physics = GROUP / "Packages/GFX.Physics"
    record = {"schema": 1, "status": "in_progress", "id": "height-terrain-mixed-constraints-v2", "oracle_revision": REFERENCE,
              "archive_sha256": digest, "host": platform.platform(), "architecture": platform.machine(),
              "compiler": checked(["silex", "version"]).strip(), "analytical": EXPECTED,
              "tolerances": TOLERANCES, "residual_upper_bounds": BOUNDS,
              "position_budgets": {"pulley_planar": 8, "pulley_spatial": 48, "loaded_path": 8},
              "sources_sha256": {str(p.relative_to(GROUP)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [GROUP / ENTRY, HERE / "TerrainConstraintsOracle.cpp", HERE / "TerrainConstraintsRun.py"]},
              "physics_modules_sha256": {str(p.relative_to(physics)): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in sorted((physics / "Module").rglob("*.sx"))}, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        print(f"terrain/constraints {mode}: building small Jolt witness", flush=True)
        reference_binary = oracle(source, mode)
        print(f"terrain/constraints {mode}: compiling Silex consumer", flush=True)
        candidate_binary = build_candidate(mode)
        configuration = checked([str(reference_binary), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        outputs = {"oracle": checked([str(reference_binary)]), "silex": checked([str(candidate_binary)])}
        values = {name: parse_result(output, FIELDS) for name, output in outputs.items()}
        record["modes"][mode] = {"verified": False, "jolt_configuration": configuration, **values,
                                 "raw_output": outputs,
                                 "library_sha256": hashlib.sha256((BUILD / f"jolt-{mode}/libJolt.a").read_bytes()).hexdigest(),
                                 "binaries_sha256": {"oracle": hashlib.sha256(reference_binary.read_bytes()).hexdigest(),
                                                     "silex": hashlib.sha256(candidate_binary.read_bytes()).hexdigest()}}
        (BUILD / "terrain-constraints-qualification.json").write_text(json.dumps(record, indent=2) + "\n")
        verify(values["oracle"])
        verify(values["silex"])
        verify(values["silex"], {key: values["oracle"][key] for key in EXPECTED})
        record["modes"][mode]["verified"] = True
        (BUILD / "terrain-constraints-qualification.json").write_text(json.dumps(record, indent=2) + "\n")
        print(f"terrain/constraints {mode}: {len(FIELDS)} analytical/oracle observations green", flush=True)
    if len(record["modes"]) == 2:
        verify(record["modes"]["Debug"]["silex"], {key: record["modes"]["Release"]["silex"][key] for key in EXPECTED})

    record["status"] = "verified"
    (BUILD / "terrain-constraints-qualification.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"terrain/constraint qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
