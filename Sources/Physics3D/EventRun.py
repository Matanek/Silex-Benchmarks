#!/usr/bin/env python3
"""Compare simple contact event timing with pinned Jolt."""

import argparse
import json
from pathlib import Path
import sys

from Run import (BUILD, GROUP, HERE, REFERENCE, build_oracle, build_silex,
                 checked, compare, fail, parse_result, self_test, verified_source)


FIELDS = tuple(f"{phase}_{kind}" for phase in ("entry", "stay", "destroy")
               for kind in ("added", "persisted", "removed"))
EXPECTED = {field: 0.0 for field in FIELDS}
EXPECTED.update(entry_added=1.0, stay_persisted=1.0, destroy_removed=1.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="pre-downloaded official commit archive")
    parser.add_argument("--mode", choices=("Debug", "Release", "both"), default="both")
    options = parser.parse_args()
    if Path.cwd().resolve() != GROUP:
        fail(f"run from the Spec worktree group: {GROUP}")
    self_test()
    source, digest = verified_source(options.archive)
    record = {"schema": 1, "fixture": "contact-lifecycle-v1",
              "oracle_revision": REFERENCE, "archive_sha256": digest,
              "absolute_tolerance": 0.0, "modes": {}}
    for mode in (("Debug", "Release") if options.mode == "both" else (options.mode,)):
        oracle = build_oracle(source, mode, HERE / "EventOracle.cpp", "event-oracle")
        candidate = build_silex(mode, "Events.sx", "events-silex", physics=True)
        configuration = checked([str(oracle), "--configuration"]).strip()
        if not configuration.startswith("Single precision "):
            fail("incompatible Jolt precision")
        jolt = parse_result(checked([str(oracle)]), FIELDS)
        silex = parse_result(checked([str(candidate)]), FIELDS)
        compare(jolt, EXPECTED, 0.0, FIELDS)
        compare(silex, EXPECTED, 0.0, FIELDS)
        compare(silex, jolt, 0.0, FIELDS)
        record["modes"][mode] = {"jolt_configuration": configuration,
                                 "oracle": jolt, "silex": silex}
        print(f"physics3d events {mode}: entry, persistence and removal agree")
    (BUILD / "event-qualification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"physics3d event qualification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
