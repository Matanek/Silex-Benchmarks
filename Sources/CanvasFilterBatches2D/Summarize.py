#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


CASES = ("unfiltered", "shared", "fragmented")
LINE = re.compile(r"^SILEX_CANVAS_FILTER_BATCHES (?P<fields>.+)$")
FIELD = re.compile(r"([a-z_]+)=([^ ]+)")
RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size\s*$")


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
            if fields["case"] != case:
                raise SystemExit(f"unexpected case in {output}: {fields['case']}")
            row: dict[str, object] = {
                "case": case,
                "process": repetition,
                "placements": int(fields["placements"]),
                "warmup": int(fields["warmup"]),
                "iterations": int(fields["iterations"]),
                "elapsed_ms": float(fields["elapsed_ms"]),
                "per_frame_ms": float(fields["per_frame_ms"]),
                "source_renders": int(fields["source_renders"]),
                "source_cache_hits": int(fields["source_cache_hits"]),
                "filter_renders": int(fields["filter_renders"]),
                "filter_cache_hits": int(fields["filter_cache_hits"]),
                "pipelines": int(fields["pipelines"]),
                "pipeline_creations": int(fields["pipeline_creations"]),
                "pipeline_cache_hits": int(fields["pipeline_cache_hits"]),
                "allocations": int(fields["allocations"]),
                "gpu_bytes": int(fields["gpu_bytes"]),
                "rgba_uploads": int(fields["rgba_uploads"]),
                "rss_bytes": rss[0],
            }
            if row["source_renders"] != 1 or row["rgba_uploads"] != 0:
                raise SystemExit(f"invalid sharing evidence in {output}")
            rows.append(row)
    return rows


def values(rows: list[dict[str, object]], case: str, field: str) -> list[float]:
    return [float(row[field]) for row in rows if row["case"] == case]


def stable(rows: list[dict[str, object]], case: str, field: str) -> int:
    observed = {int(row[field]) for row in rows if row["case"] == case}
    if len(observed) != 1:
        raise SystemExit(f"unstable {field} for {case}: {sorted(observed)}")
    return observed.pop()


def main() -> None:
    root = Path(sys.argv[1])
    rows = parse(root)
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Scene2D CanvasFilter batching",
        "",
        "Seven independent Release processes per case after an in-process warm-up.",
        "Each measured frame waits for GPU completion. Time is median, sample",
        "variance and [minimum, maximum]. GPU bytes are the renderer's deterministic",
        "cache-resident estimate; RSS is the operating-system process peak.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "| Case | ms/frame median | Variance | Range | Filter draws | Pipelines | GPU estimate | RSS median |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in CASES:
        timings = values(rows, case, "per_frame_ms")
        rss = values(rows, case, "rss_bytes")
        lines.append(
            f"| `{case}` | {statistics.median(timings):.4f} | "
            f"{statistics.variance(timings):.6f} | "
            f"[{min(timings):.4f}, {max(timings):.4f}] | "
            f"{stable(rows, case, 'filter_renders')} | "
            f"{stable(rows, case, 'pipelines')} | "
            f"{stable(rows, case, 'gpu_bytes')} | {statistics.median(rss):.0f} |"
        )
    lines.extend([
        "",
        "All processes retained one Canvas source render and reported zero CPU RGBA",
        "uploads. `shared` performs one filter draw per frame for 16 placements;",
        "`fragmented` performs 16 and alternates two cached programs. Results are",
        "local macOS ARM64 evidence and do not predict another architecture or backend.",
        "",
    ])
    (root / "Summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
