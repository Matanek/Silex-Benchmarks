#!/usr/bin/env python3
"""Qualify physical and virtual character capabilities against pinned Jolt."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, compare, fail, parse_result, verified_source)


EXPECTED = {"weak_vx": 0.009, "weak_spin": 0.0, "capped_vx": 1.0,
            "capped_spin": 0.0, "weight_vy": -70.0 / 10.0 * 9.81 / 60.0,
            "physical_vx": 0.7, "physical_body_vx": 0.7, "physical_spin": 0.0,
            "rest_y": 0.85, "rest_vy": 0.0, "rest_normal_y": 1.0,
            "resize_blocked": 1.0, "resize_feet": 0.002, "resize_mass": 70.0}
FIXTURE_SHA256 = "d6d059403ba4ea5560960bd92d032e8f935cc1a70963acac3dc80c3ce112a6c6"
FIELDS = tuple(EXPECTED)
TOLERANCES = {field: 0.005 if field.startswith("rest_") else 0.0001 for field in FIELDS}


def character_oracle(source, mode):
    directory = BUILD / f"jolt-{mode}"
    library = directory / "libJolt.a"
    cache = directory / "CMakeCache.txt"
    if not library.is_file() or not cache.is_file():
        return build_oracle(source, mode, HERE / "CharacterOracle.cpp", "character-oracle")
    configuration = cache.read_text()
    for expected in (f"CMAKE_BUILD_TYPE:STRING={mode}", "DOUBLE_PRECISION:BOOL=OFF"):
        if expected not in configuration:
            fail(f"cached Jolt configuration differs: {expected}")
    binary = BUILD / f"character-oracle-{mode.lower()}"
    definitions = ["-DJPH_OBJECT_STREAM", "-DJPH_USE_CPU_COMPUTE", "-DJPH_DEBUG_RENDERER", "-DJPH_PROFILE_ENABLED"]
    if mode == "Release":
        definitions.append("-DNDEBUG")
    deployment = (["-mmacosx-version-min=" + platform.mac_ver()[0]]
                  if platform.system() == "Darwin" else [])
    checked([shutil.which("clang++") or fail("clang++ unavailable"), "-std=c++23",
             "-fno-rtti", "-fno-exceptions", *deployment,
             "-O0" if mode == "Debug" else "-O2", *definitions,
             "-I", str(source), str(HERE / "CharacterOracle.cpp"), str(library),
             "-pthread", "-o", str(binary)])
    return binary


def verify(actual, reference):
    for field in FIELDS:
        compare(actual, reference, TOLERANCES[field], (field,))


def self_test():
    valid = "\n".join(f"{key}={value}" for key, value in EXPECTED.items())
    for invalid in (valid + "\nweak_vx=0", valid.replace("weak_vx=0.009", "weak_vx=nan"),
                    valid.replace("weak_vx=0.009", "")):
        try:
            parse_result(invalid, FIELDS)
        except ValueError:
            pass
        else:
            fail("character output guard accepted invalid data")
    for field in FIELDS:
        try:
            verify({**EXPECTED, field: EXPECTED[field] + TOLERANCES[field] * 2}, EXPECTED)
        except ValueError:
            pass
        else:
            fail(f"character comparator accepted a perturbation of {field}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the workspace root or Spec group: {GROUP}")
    self_test()
    if options.self_test:
        print("character comparator self-test: ok")
        return
    fixture = HERE / "CharacterFixture.json"
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != FIXTURE_SHA256:
        fail("fixed scenario fixture changed; update both consumers and qualify the new inputs")
    data = json.loads(fixture.read_text())
    if data["schema"] != 1 or data["id"] != "character-modes-v1" or data["oracle_revision"] != REFERENCE:
        fail("character fixture identity differs from the compiled fixed scenarios")
    source, digest = verified_source(None)
    record = {"schema": 1, "fixture": data, "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
              "oracle_revision": REFERENCE, "archive_sha256": digest,
              "sources_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                 for name in ("Characters.sx", "CharacterOracle.cpp", "CharacterRun.py")},
              "host": platform.platform(), "architecture": platform.machine(),
              "silex": checked(["silex", "version"]).strip(),
              "absolute_tolerances": TOLERANCES, "analytical": EXPECTED, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = character_oracle(source, mode)
        candidate = build_silex(mode, "Characters.sx", "characters-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        oracle_values = parse_result(checked([str(oracle)]), FIELDS)
        candidate_values = parse_result(checked([str(candidate)]), FIELDS)
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "library_sha256": hashlib.sha256((BUILD / f"jolt-{mode}" / "libJolt.a").read_bytes()).hexdigest(),
                                 "oracle": oracle_values, "silex": candidate_values}
        (BUILD / "character-qualification.json").write_text(json.dumps(record, indent=2) + "\n")
        verify(oracle_values, EXPECTED)
        verify(candidate_values, EXPECTED)
        verify(candidate_values, oracle_values)
        print(f"characters {mode}: six scenarios, fourteen observables agree", flush=True)
    if len(record["modes"]) == 2:
        verify(record["modes"]["Debug"]["silex"], record["modes"]["Release"]["silex"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"character qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
