#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


CASES = (
    "analytic-static",
    "analytic-transform",
    "filtered-static",
    "filtered-dynamic",
    "fullscreen",
)
LINE = re.compile(r"^SILEX_CANVAS_EFFECTS_2D (?P<fields>.+)$")
FIELD = re.compile(r"([a-z_]+)=([^ ]+)")
RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size\s*$")
INT_FIELDS = (
    "warmup",
    "frames",
    "width",
    "height",
    "density",
    "seed",
    "draw_calls",
    "pipeline_bindings",
    "texture_bindings",
    "triangles",
    "instances",
    "uniform_bytes",
    "surface_renders",
    "cache_hits",
    "texture_allocations",
    "texture_bytes",
    "geometry_uploads",
    "filtered_pixels",
    "image_uploads",
    "vector_tessellations",
    "coverage_rasters",
    "coverage_pixels",
    "rgba_uploads",
)
FLOAT_FIELDS = (
    "cpu_prepare_submit_ms",
    "gpu_queue_drain_ms",
    "mutation_ms",
    "minimum_ms",
    "maximum_ms",
)


def parse(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case in CASES:
        for repetition in range(1, 8):
            output = root / f"{case}-{repetition}.log"
            timing = root / f"{case}-{repetition}.time"
            matches = [
                dict(FIELD.findall(match.group("fields")))
                for line in output.read_text().splitlines()
                if (match := LINE.match(line))
            ]
            rss = [
                int(match.group(1))
                for line in timing.read_text().splitlines()
                if (match := RSS.match(line))
            ]
            if len(matches) != 1 or len(rss) != 1:
                raise SystemExit(f"invalid measurement for {case} process {repetition}")
            fields = matches[0]
            if fields.get("case") != case:
                raise SystemExit(f"unexpected case in {output}: {fields.get('case')}")
            if fields.get("gpu_ms") != "unavailable" or fields.get("presentation") != "false":
                raise SystemExit(f"invalid measurement mode in {output}")
            row: dict[str, object] = {"case": case, "process": repetition}
            for field in INT_FIELDS:
                row[field] = int(fields[field])
            for field in FLOAT_FIELDS:
                row[field] = float(fields[field])
            row["rss_bytes"] = rss[0]
            if row["warmup"] != 120 or row["frames"] != 600:
                raise SystemExit(f"invalid frame protocol in {output}")
            if row["width"] != 1920 or row["height"] != 1080 or row["density"] != 1:
                raise SystemExit(f"invalid fixed target in {output}")
            if row["rgba_uploads"] != 0 or row["texture_allocations"] != 0:
                raise SystemExit(f"failed structural gate in {output}")
            rows.append(row)
    return rows


def values(rows: list[dict[str, object]], case: str, field: str) -> list[float]:
    return [float(row[field]) for row in rows if row["case"] == case]


def stable(rows: list[dict[str, object]], case: str, field: str) -> int:
    observed = {int(row[field]) for row in rows if row["case"] == case}
    if len(observed) != 1:
        raise SystemExit(f"unstable {field} for {case}: {sorted(observed)}")
    return observed.pop()


def median_absolute_deviation(samples: list[float]) -> float:
    center = statistics.median(samples)
    return statistics.median(abs(value - center) for value in samples)


def main() -> None:
    root = Path(sys.argv[1])
    rows = parse(root)
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Canvas effects 2D final campaign",
        "",
        "Seven independent Release processes per case, each with 120 warm-up and",
        "600 measured frames. CPU preparation/submit time is distinct from the GPU",
        "queue drain. No reliable GPU timestamp is available on this backend, so the",
        "campaign makes no GPU-time claim. RSS is the operating-system process peak;",
        "texture bytes are the renderer's deterministic cache-resident estimate.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "| Case | CPU ms/frame median | Variance | MAD/median | Queue drain ms | Draws | Instances | Geometry uploads | Texture allocations | Texture bytes | Filtered pixels | RSS median |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in CASES:
        timings = values(rows, case, "cpu_prepare_submit_ms")
        drains = values(rows, case, "gpu_queue_drain_ms")
        rss = values(rows, case, "rss_bytes")
        median = statistics.median(timings)
        mad_ratio = median_absolute_deviation(timings) / median if median else 0.0
        if mad_ratio > 0.05:
            raise SystemExit(f"unstable CPU timing for {case}: MAD/median={mad_ratio:.2%}")
        lines.append(
            f"| `{case}` | {median:.4f} | {statistics.variance(timings):.6f} | "
            f"{mad_ratio:.2%} | {statistics.median(drains):.4f} | "
            f"{stable(rows, case, 'draw_calls')} | {stable(rows, case, 'instances')} | "
            f"{stable(rows, case, 'geometry_uploads')} | "
            f"{stable(rows, case, 'texture_allocations')} | "
            f"{stable(rows, case, 'texture_bytes')} | "
            f"{stable(rows, case, 'filtered_pixels')} | {statistics.median(rss):.0f} |"
        )
    lines.extend([
        "",
        "Correctness and structural gates are asserted inside every process: fixed",
        "offscreen target, disabled presentation, zero CPU RGBA uploads, zero texture",
        "allocations after warm-up, static-cache reuse, and bounded proportional mesh",
        "uploads for the dynamic groups. `fullscreen` is an informational stress case,",
        "not an ordinary-path non-regression baseline.",
        "",
    ])
    (root / "Summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
