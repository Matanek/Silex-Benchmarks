#!/usr/bin/env python3
"""Compare compatible Silex compilation reports and reject mixed campaigns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"error: {message}")


def load_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read report {path}: {error}")
    if report.get("schema_version") != 1:
        fail(f"unsupported report schema in {path}")
    if not isinstance(report.get("metadata", {}).get("comparison_key"), dict):
        fail(f"report has no comparison identity: {path}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--allow-worker-change",
        action="store_true",
        help="compare otherwise identical campaigns whose worker counts differ",
    )
    arguments = parser.parse_args()
    baseline = load_report(arguments.baseline)
    candidate = load_report(arguments.candidate)
    baseline_key = dict(baseline["metadata"]["comparison_key"])
    candidate_key = dict(candidate["metadata"]["comparison_key"])
    baseline_workers = baseline_key.pop("worker_count", None)
    candidate_workers = candidate_key.pop("worker_count", None)
    if baseline_key != candidate_key or (
        not arguments.allow_worker_change and baseline_workers != candidate_workers
    ):
        fail("reports differ in target, mode, corpus, machine, workers, runs, packages, or cache provenance")
    if baseline["summaries"].keys() != candidate["summaries"].keys():
        fail("reports do not contain the same profiles")

    print(f"workers\t{baseline_workers}\t{candidate_workers}")
    print("profile\tbaseline_seconds\tcandidate_seconds\tdelta_percent")
    for profile in baseline["summaries"]:
        before = baseline["summaries"][profile]["median_wall_seconds"]
        after = candidate["summaries"][profile]["median_wall_seconds"]
        delta = 0.0 if before == 0 else (after / before - 1.0) * 100.0
        print(f"{profile}\t{before:.6f}\t{after:.6f}\t{delta:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
