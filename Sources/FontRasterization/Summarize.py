#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


LINE = re.compile(r"^SILEX_FONT_RASTER (?P<fields>.+)$")
DIRECT_LINE = re.compile(r"^SILEX_FONT_DIRECT (?P<fields>.+)$")
FIELD = re.compile(r"([a-z_]+)=([^ ]+)")
RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size\s*$")
CASES = (
    "cold_first",
    "retained_static",
    "retained_static_soak",
    "forced_static_raster",
    "dynamic_short",
    "multi_script",
    "pressure_first",
    "pressure_revisit",
)
DIRECT_METRICS = ("hash_ms", "face_ms", "instance_ms", "shape_ms", "raster_ms")


def parse_measurements(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for engine in ("baseline", "candidate"):
        for case in CASES:
            for repetition in range(1, 8):
                output = root / f"{engine}-{case}-{repetition}.log"
                timing = root / f"{engine}-{case}-{repetition}.time"
                rows.extend(parse_process(output, timing, engine, repetition, case))
    return rows


def parse_process(
    output: Path,
    timing: Path,
    engine: str,
    repetition: int,
    expected_case: str,
) -> list[dict[str, object]]:
    rss_values = [
        int(match.group(1))
        for line in timing.read_text().splitlines()
        if (match := RSS.match(line))
    ]
    if len(rss_values) != 1:
        raise SystemExit(f"missing RSS in {timing}")
    rows: list[dict[str, object]] = []
    for line in output.read_text().splitlines():
        match = LINE.match(line)
        if not match:
            continue
        fields = dict(FIELD.findall(match.group("fields")))
        case = fields["case"]
        if case != expected_case:
            raise SystemExit(f"unexpected case in {output}: {case}")
        load = float(fields["load_ms"])
        measure = float(fields["measure_ms"])
        raster = float(fields["raster_ms"])
        row: dict[str, object] = {
            "engine": engine,
            "repetition": repetition,
            "case": case,
            "iterations": int(fields["iterations"]),
            "load_ms": load,
            "measure_ms": measure,
            "raster_ms": raster,
            "total_ms": load + measure + raster,
            "width_milli": int(fields["width_milli"]),
            "height_milli": int(fields["height_milli"]),
            "lines": int(fields["lines"]),
            "nonzero": int(fields["nonzero"]),
            "alpha": int(fields["alpha"]),
            "rss_bytes": rss_values[0],
        }
        if row["nonzero"] <= 0 or row["alpha"] <= 0:
            raise SystemExit(f"empty raster signature in {output}: {case}")
        rows.append(row)
    if len(rows) != 1:
        raise SystemExit(f"expected one case in {output}, found {len(rows)}")
    return rows


def parse_direct(root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for repetition in range(1, 8):
        output = root / f"direct-{repetition}.log"
        timing = root / f"direct-{repetition}.time"
        rss_values = [
            int(match.group(1))
            for line in timing.read_text().splitlines()
            if (match := RSS.match(line))
        ]
        matches = [
            dict(FIELD.findall(match.group("fields")))
            for line in output.read_text().splitlines()
            if (match := DIRECT_LINE.match(line))
        ]
        if len(rss_values) != 1 or len(matches) != 1:
            raise SystemExit(f"invalid direct output for repetition {repetition}")
        fields = matches[0]
        row: dict[str, object] = {"repetition": repetition}
        for metric in DIRECT_METRICS:
            row[metric] = float(fields[metric])
        row["glyphs"] = int(fields["glyphs"])
        row["alpha_count"] = int(fields["alpha_count"])
        row["alpha_sum"] = int(fields["alpha_sum"])
        row["rss_bytes"] = rss_values[0]
        rows.append(row)
    signatures = {
        (row["glyphs"], row["alpha_count"], row["alpha_sum"])
        for row in rows
    }
    if len(signatures) != 1:
        raise SystemExit("unstable direct raster signature")
    return rows


def values(rows: list[dict[str, object]], engine: str, case: str, metric: str) -> list[float]:
    return [
        float(row[metric])
        for row in rows
        if row["engine"] == engine and row["case"] == case
    ]


def median_range(numbers: list[float]) -> str:
    median = statistics.median(numbers)
    return f"{median:.3f} [{min(numbers):.3f}, {max(numbers):.3f}]"


def delta(baseline: list[float], candidate: list[float]) -> float:
    base = statistics.median(baseline)
    return (statistics.median(candidate) - base) * 100.0 / base


def validate_signatures(rows: list[dict[str, object]]) -> None:
    for case in CASES:
        for engine in ("baseline", "candidate"):
            metrics = {
                (int(row["width_milli"]), int(row["height_milli"]), int(row["lines"]))
                for row in rows
                if row["engine"] == engine and row["case"] == case
            }
            if len(metrics) != 1:
                raise SystemExit(f"unstable metrics for {engine}/{case}: {sorted(metrics)}")
            signatures = {
                (int(row["nonzero"]), int(row["alpha"]))
                for row in rows
                if row["engine"] == engine and row["case"] == case
            }
            if len(signatures) != 1:
                raise SystemExit(f"unstable pixel signature for {engine}/{case}")
        baseline = next(
            row for row in rows if row["engine"] == "baseline" and row["case"] == case
        )
        candidate = next(
            row for row in rows if row["engine"] == "candidate" and row["case"] == case
        )
        if baseline["height_milli"] != candidate["height_milli"] or baseline["lines"] != candidate["lines"]:
            raise SystemExit(f"height or line-count mismatch for {case}")
        baseline_width = int(baseline["width_milli"])
        candidate_width = int(candidate["width_milli"])
        relative_width_delta = abs(candidate_width - baseline_width) / max(baseline_width, 1)
        if relative_width_delta > 0.01:
            raise SystemExit(f"width mismatch above 1% for {case}: {relative_width_delta:.3%}")


def write_csv(root: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0].keys())
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_direct_csv(root: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0].keys())
    with (root / "direct_measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    root: Path,
    rows: list[dict[str, object]],
    direct_rows: list[dict[str, object]],
) -> None:
    metadata = (root / "metadata.txt").read_text().strip()
    leaks_output = (root / "leaks-pressure-revisit.log").read_text()
    if "0 leaks for 0 total leaked bytes" not in leaks_output:
        raise SystemExit("candidate pressure run did not produce a zero-leak report")
    (root / "leaks-pressure-revisit.log").write_text(leaks_output.rstrip() + "\n")
    lines = [
        "# GFX.Font rasterization comparison",
        "",
        "Seven independent Release processes per engine; median [min, max] in milliseconds.",
        "Negative deltas favor the vector candidate. Logical metrics and each engine's pixel",
        "signatures are identical within each engine; every raster is non-empty. Heights and",
        "line counts match exactly; deterministic width differences must remain within 1%.",
        "",
        "```text",
        metadata,
        "```",
        "",
        "| Case | Phase | SDL_ttf baseline | Vector candidate | Delta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for case in CASES:
        for metric, label in (
            ("load_ms", "load"),
            ("measure_ms", "measure"),
            ("raster_ms", "raster"),
            ("total_ms", "combined"),
        ):
            baseline = values(rows, "baseline", case, metric)
            candidate = values(rows, "candidate", case, metric)
            if metric == "load_ms" and max(baseline + candidate) == 0.0:
                continue
            lines.append(
                f"| `{case}` | {label} | {median_range(baseline)} | "
                f"{median_range(candidate)} | {delta(baseline, candidate):+.1f}% |"
            )
    lines.extend([
        "",
        "| Case | SDL_ttf width milli-pixels | Vector width milli-pixels | Delta |",
        "| --- | ---: | ---: | ---: |",
    ])
    for case in CASES:
        baseline_width = values(rows, "baseline", case, "width_milli")
        candidate_width = values(rows, "candidate", case, "width_milli")
        lines.append(
            f"| `{case}` | {statistics.median(baseline_width):.0f} | "
            f"{statistics.median(candidate_width):.0f} | {delta(baseline_width, candidate_width):+.2f}% |"
        )
    lines.extend([
        "",
        "| Case | SDL_ttf maximum RSS bytes | Vector maximum RSS bytes | Delta |",
        "| --- | ---: | ---: | ---: |",
    ])
    for case in CASES:
        baseline_rss = values(rows, "baseline", case, "rss_bytes")
        candidate_rss = values(rows, "candidate", case, "rss_bytes")
        lines.append(
            f"| `{case}` | {median_range(baseline_rss)} | "
            f"{median_range(candidate_rss)} | {delta(baseline_rss, candidate_rss):+.1f}% |"
        )
    baseline_cold_rss = statistics.median(
        values(rows, "baseline", "cold_first", "rss_bytes")
    )
    candidate_cold_rss = statistics.median(
        values(rows, "candidate", "cold_first", "rss_bytes")
    )
    fixed_rss_mib = (candidate_cold_rss - baseline_cold_rss) / (1024.0 * 1024.0)
    retained_short_rss = statistics.median(
        values(rows, "candidate", "retained_static", "rss_bytes")
    )
    retained_soak_rss = statistics.median(
        values(rows, "candidate", "retained_static_soak", "rss_bytes")
    )
    retained_growth_mib = (retained_soak_rss - retained_short_rss) / (1024.0 * 1024.0)
    pressure_first_rss = statistics.median(
        values(rows, "candidate", "pressure_first", "rss_bytes")
    )
    pressure_revisit_rss = statistics.median(
        values(rows, "candidate", "pressure_revisit", "rss_bytes")
    )
    pressure_growth_mib = (pressure_revisit_rss - pressure_first_rss) / (1024.0 * 1024.0)
    lines.extend([
        "",
        f"Cold-process candidate RSS difference: {fixed_rss_mib:+.1f} MiB. This is reported",
        "separately as provider/runtime overhead; per-case peaks are not interpreted as live",
        "cache residency without allocator evidence.",
        "",
        f"Retained ×10 soak RSS growth: {retained_growth_mib:+.1f} MiB. Forced pressure",
        f"second-pass peak growth: {pressure_growth_mib:+.1f} MiB. The accompanying macOS",
        "`leaks --atExit` pressure run reports 0 leaks for 0 total leaked bytes. The",
        "forced-path growth therefore remains visible as allocator/high-water behavior,",
        "while the retained UI path demonstrates the bounded plateau relevant to frames.",
        "",
        "The end-to-end `combined` phase is the UI raster path used for the performance",
        "decision. Cold loading and shaping misses remain visible as separate phases: a",
        "miss-only `measure` regression is not relabeled as a gain even when the subsequent",
        "rasterization makes the complete operation faster. Retained hits are reported",
        "separately and must not be inferred from the forced rerasterization workloads.",
        "",
        "## Candidate direct attribution",
        "",
        "Seven independent Release processes; median [min, max] in milliseconds.",
        "The SHA-256 phase is diagnostic and is absent from bundled-face loading.",
        "",
        "| Phase | Vector candidate |",
        "| --- | ---: |",
    ])
    for metric in DIRECT_METRICS:
        direct_values = [float(row[metric]) for row in direct_rows]
        lines.append(f"| `{metric}` | {median_range(direct_values)} |")
    direct_rss = [float(row["rss_bytes"]) for row in direct_rows]
    lines.extend([
        "",
        f"Direct probe maximum RSS bytes: {median_range(direct_rss)}.",
        "",
    ])
    (root / "SUMMARY.md").write_text("\n".join(lines))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: Summarize.py RESULTS_DIRECTORY")
    root = Path(sys.argv[1]).resolve()
    rows = parse_measurements(root)
    direct_rows = parse_direct(root)
    validate_signatures(rows)
    write_csv(root, rows)
    write_direct_csv(root, direct_rows)
    write_summary(root, rows, direct_rows)
    print(root / "SUMMARY.md")


if __name__ == "__main__":
    main()
