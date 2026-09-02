#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


CASES = ("static", "transform_only", "content_mutation", "fullscreen")
LINE = re.compile(r"^SILEX_FILTERED_CANVAS (?P<fields>.+)$")
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
                "warmup": int(fields["warmup"]),
                "iterations": int(fields["iterations"]),
                "elapsed_ms": float(fields["elapsed_ms"]),
                "per_iteration_ms": float(fields["per_iteration_ms"]),
                "gpu_bytes": int(fields["gpu_bytes"]),
                "rss_bytes": rss[0],
                "allocations": int(fields["allocations"]),
                "renders": int(fields["renders"]),
                "cache_hits": int(fields["cache_hits"]),
                "rgba_uploads": int(fields["rgba_uploads"]),
            }
            if row["rgba_uploads"] != 0 or row["gpu_bytes"] <= 0:
                raise SystemExit(f"invalid GPU accounting in {output}")
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
        "# Filtered Canvas surfaces",
        "",
        "Seven independent Release processes per case after an in-process warm-up.",
        "Time is median, sample variance and [minimum, maximum]. GPU bytes are the",
        "deterministic cache-resident estimate reported by the public renderer; RSS is",
        "the operating-system process peak and is not interpreted as live GPU memory.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "| Case | ms/iteration median | Variance | Range | GPU estimate | RSS median |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in CASES:
        timings = values(rows, case, "per_iteration_ms")
        rss = values(rows, case, "rss_bytes")
        gpu_bytes = stable(rows, case, "gpu_bytes")
        variance = statistics.variance(timings)
        lines.append(
            f"| `{case}` | {statistics.median(timings):.4f} | {variance:.6f} | "
            f"[{min(timings):.4f}, {max(timings):.4f}] | {gpu_bytes} | "
            f"{statistics.median(rss):.0f} |"
        )
    lines.extend([
        "",
        "All processes reported zero CPU RGBA uploads. `transform_only` samples one",
        "retained surface into moving viewports and asserts that the source render count",
        "does not change. The mutation cases assert a stable cache-entry count.",
        "",
    ])
    (root / "Summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
