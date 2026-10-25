"""Check the explicit Jolt lean adaptation against an independent torque law."""
import json
import math
from pathlib import Path
from MotorcycleLeanOracle import build_motorcycle_oracle, SOURCE_SHA256
from Run import BUILD, GROUP, HERE, verified_source, checked, fail


def qualify(raw, stable):
    seen = set()
    worst = 0.0
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 3:
            fail("invalid small-lean record")
        rate = int(fields[0])
        angle, correction = map(float, fields[1:])
        key = rate, round(angle, 8)
        if key in seen or rate not in (60, 120) or round(abs(angle), 8) not in (.0001, .00001) or not all(map(math.isfinite, (angle, correction))):
            fail("invalid small-lean key or value")
        seen.add(key)
        expected = -5000 * angle / 100
        error = abs(correction - expected)
        if stable and error > .05 * abs(expected) + 1e-7:
            fail("adapted motorcycle response differs from analytical spring torque")
        if not stable and abs(correction) > 1e-7:
            fail("original small-angle dead zone differs from the recorded counterexample")
        worst = max(worst, error)
    if len(seen) != 8:
        fail("missing small-lean records")
    return dict(cases=len(seen), maximum_error=worst, scope="enabled minus disabled assistance, one step; analytical -stiffness*angle/inertia")


def main():
    if Path.cwd().resolve() != GROUP:
        fail("run from the workspace or Spec group root")
    source, digest = verified_source(None)
    record = dict(original_source_sha256=SOURCE_SHA256, archive_sha256=digest, modes={})
    raw_modes = {}
    for mode in ("Debug", "Release"):
        entry = {}
        raw_modes[mode] = {}
        for stable in (False, True):
            binary, provenance = build_motorcycle_oracle(source, mode, HERE / "MotorcycleSmallLeanOracle.cpp", "motorcycle-small-lean", stable=stable)
            raw = checked([str(binary)])
            variant = "stable" if stable else "original"
            (BUILD / f"motorcycle-small-lean-{variant}-{mode.lower()}.txt").write_text(raw)
            raw_modes[mode][variant] = raw
            entry[variant] = dict(provenance=provenance, result=qualify(raw, stable))
        record["modes"][mode] = entry
        print(mode, "small-lean analytical response and original dead zone verified", flush=True)
    if raw_modes["Debug"] != raw_modes["Release"]:
        fail("small-lean Debug/Release outputs differ")
    record["debug_release_identical"] = True
    (BUILD / "motorcycle-small-lean-qualification.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
