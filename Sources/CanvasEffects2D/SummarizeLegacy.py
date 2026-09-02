#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


CASES = (
    "RetainedCanvasGeometry",
    "AnimatingCanvasGeometry",
    "UpdatingTextLayers2D",
    "RetainedUIInteraction",
)
VERSIONS = ("baseline", "candidate")
PATTERNS = {
    "RetainedCanvasGeometry": re.compile(
        r"10000 retained primitives: 60000 vertices, 2160000 GPU bytes, ([0-9.]+) ms"
    ),
    "AnimatingCanvasGeometry": re.compile(
        r"1000 animated primitives x 240 frames: ([0-9.]+) ms"
    ),
    "UpdatingTextLayers2D": re.compile(r"SILEX_GFX_TEXT_LAYERS .* ms_per_frame=([0-9.]+)"),
    "RetainedUIInteraction": re.compile(r"layered_presentation_ms_per_update=([0-9.]+)"),
}


def primary(case: str, text: str) -> float:
    matches = PATTERNS[case].findall(text)
    if len(matches) != 1:
        raise SystemExit(f"expected one primary metric for {case}, found {matches}")
    value = float(matches[0])
    if case == "AnimatingCanvasGeometry":
        value /= 240.0
    return value


def mad_ratio(samples: list[float]) -> float:
    center = statistics.median(samples)
    deviation = statistics.median(abs(value - center) for value in samples)
    return deviation / center if center else 0.0


def main() -> None:
    root = Path(sys.argv[1])
    rows: list[dict[str, object]] = []
    for case in CASES:
        for version in VERSIONS:
            for repetition in range(1, 8):
                output = root / f"{case}-{version}-{repetition}.log"
                rows.append({
                    "case": case,
                    "version": version,
                    "process": repetition,
                    "primary_ms": primary(case, output.read_text()),
                })
    with (root / "legacy-measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Legacy no-effect regression gates",
        "",
        "The unchanged public workloads were built in Release against the pre-Part07",
        "package commits and the candidate commits, then run as seven alternating",
        "independent processes after one discarded warm-up process per executable.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "| Workload | Primary metric | Baseline median | Candidate median | Change | Baseline MAD | Candidate MAD | Gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    labels = {
        "RetainedCanvasGeometry": "construction + vector_geometry ms",
        "AnimatingCanvasGeometry": "ms per update",
        "UpdatingTextLayers2D": "ms_per_frame",
        "RetainedUIInteraction": "layered_presentation_ms_per_update",
    }
    blocked: list[str] = []
    for case in CASES:
        baseline = [float(row["primary_ms"]) for row in rows if row["case"] == case and row["version"] == "baseline"]
        candidate = [float(row["primary_ms"]) for row in rows if row["case"] == case and row["version"] == "candidate"]
        baseline_median = statistics.median(baseline)
        candidate_median = statistics.median(candidate)
        change = (candidate_median / baseline_median - 1.0) * 100.0
        baseline_mad = mad_ratio(baseline)
        candidate_mad = mad_ratio(candidate)
        gate = "pass" if change <= 5.0 and baseline_mad <= 0.05 and candidate_mad <= 0.05 else "BLOCK"
        if gate == "BLOCK": blocked.append(case)
        lines.append(
            f"| `{case}` | {labels[case]} | {baseline_median:.4f} | "
            f"{candidate_median:.4f} | {change:+.2f}% | {baseline_mad:.2%} | "
            f"{candidate_mad:.2%} | **{gate}** |"
        )
    lines.extend([
        "",
        "Secondary RetainedUIInteraction selection timings remain in every raw log and",
        "do not compensate for its primary layered-presentation gate. Raw",
        "`/usr/bin/time -l` files are retained for audit but include process-level residency rather than",
        "renderer-owned live memory.",
        "",
    ])
    (root / "LegacySummary.md").write_text("\n".join(lines))
    if blocked:
        raise SystemExit("legacy regression gate failed: " + ", ".join(blocked))


if __name__ == "__main__":
    main()
