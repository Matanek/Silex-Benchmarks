#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


GROUPS = ("types", "elementwise", "reduction", "matmul", "chain")
DTYPES = (
    "float32", "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64",
)
EXPECTED_ROWS = {
    "types": 54,
    "elementwise": 9,
    "reduction": 9,
    "matmul": 9,
    "chain": 15,
}
SIZES = {
    "elementwise": (1024, 65536, 1048576),
    "reduction": (1024, 65536, 1048576),
    "matmul": (32, 128, 512),
    "resident_chain_5": (32, 128, 512),
}
LINE = re.compile(r"^SILEX_TENSOR (?P<fields>.+)$")
FIELD = re.compile(r"([a-z0-9_]+)=([^ ]+)")
VERIFY = re.compile(r"^SILEX_TENSOR_VERIFY status=pass ")
RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size\s*$")


def parse(root: Path) -> tuple[list[dict[str, object]], dict[str, list[int]]]:
    rows: list[dict[str, object]] = []
    rss: dict[str, list[int]] = {group: [] for group in GROUPS}
    for group in GROUPS:
        for process in range(1, 8):
            output = root / f"{group}-{process}.log"
            timing = root / f"{group}-{process}.time"
            lines = output.read_text().splitlines()
            if sum(bool(VERIFY.match(line)) for line in lines) != 1:
                raise SystemExit(f"missing functional verifier in {output}")
            matches = [
                dict(FIELD.findall(match.group("fields")))
                for line in lines
                if (match := LINE.match(line))
            ]
            if len(matches) != EXPECTED_ROWS[group]:
                raise SystemExit(
                    f"expected {EXPECTED_ROWS[group]} rows in {output}, got {len(matches)}"
                )
            seen: set[tuple[str, ...]] = set()
            for fields in matches:
                key = tuple(
                    fields[name]
                    for name in (
                        "phase", "family", "backend", "dtype", "size",
                        "transfer_mode",
                    )
                )
                if key in seen:
                    raise SystemExit(f"duplicate measurement {key} in {output}")
                seen.add(key)
                row: dict[str, object] = {
                    "group": group,
                    "process": process,
                    "phase": fields["phase"],
                    "family": fields["family"],
                    "backend": fields["backend"],
                    "dtype": fields["dtype"],
                    "size": int(fields["size"]),
                    "elements": int(fields["elements"]),
                    "bytes": int(fields["bytes"]),
                    "transfer_mode": fields["transfer_mode"],
                    "iterations": int(fields["iterations"]),
                    "elapsed_ms": float(fields["elapsed_ms"]),
                    "per_iteration_ms": float(fields["per_iteration_ms"]),
                    "uploads": int(fields["uploads"]),
                    "downloads": int(fields["downloads"]),
                    "compute_passes": int(fields["compute_passes"]),
                }
                validate_row(row, output)
                rows.append(row)
            rss_matches = [
                int(match.group(1))
                for line in timing.read_text().splitlines()
                if (match := RSS.match(line))
            ]
            if len(rss_matches) != 1:
                raise SystemExit(f"missing RSS measurement in {timing}")
            rss[group].append(rss_matches[0])
    validate_matrix(rows)
    return rows, rss


def validate_row(row: dict[str, object], source: Path) -> None:
    backend = str(row["backend"])
    family = str(row["family"])
    phase = str(row["phase"])
    iterations = int(row["iterations"])
    uploads = int(row["uploads"])
    downloads = int(row["downloads"])
    passes = int(row["compute_passes"])
    if backend == "cpu" and (uploads != 0 or downloads != 0 or passes != 0):
        raise SystemExit(f"CPU row exposes GPU commands in {source}")
    if family == "transfer":
        if phase == "upload" and (uploads != iterations or downloads != 0 or passes != 0):
            raise SystemExit(f"invalid upload counters in {source}")
        if phase == "download" and (uploads != 0 or downloads != iterations or passes != 0):
            raise SystemExit(f"invalid download counters in {source}")
    if family in ("elementwise", "reduction", "matmul") and backend == "gpu":
        if passes != iterations or uploads != 0 or downloads != 0:
            raise SystemExit(f"hidden command in GPU compute row from {source}")
    if family == "resident_chain_5" and backend == "gpu":
        if phase in ("cold", "hot") and (
            passes != iterations * 5 or uploads != 0 or downloads != 0
        ):
            raise SystemExit(f"resident chain is not five transfer-free passes in {source}")
        if phase == "upload" and (uploads != 2 or downloads != 0 or passes != 0):
            raise SystemExit(f"invalid resident ingress in {source}")
        if phase == "download" and (uploads != 0 or downloads != 1 or passes != 0):
            raise SystemExit(f"invalid resident egress in {source}")


def validate_matrix(rows: list[dict[str, object]]) -> None:
    observed_dtypes = {
        str(row["dtype"])
        for row in rows
        if row["group"] == "types"
    }
    if observed_dtypes != set(DTYPES):
        raise SystemExit(f"unexpected dtype matrix: {sorted(observed_dtypes)}")
    for mode in ("equal_cardinality", "equal_bytes"):
        for phase in ("upload", "download"):
            observed = {
                str(row["dtype"])
                for row in rows
                if row["family"] == "transfer"
                and row["transfer_mode"] == mode
                and row["phase"] == phase
            }
            if observed != set(DTYPES):
                raise SystemExit(f"incomplete {mode} {phase} matrix")
    for family, sizes in SIZES.items():
        observed = {
            int(row["size"])
            for row in rows
            if row["family"] == family
        }
        if observed != set(sizes):
            raise SystemExit(f"unexpected {family} grid: {sorted(observed)}")


def selected(rows: list[dict[str, object]], **filters: object) -> list[dict[str, object]]:
    return [
        row for row in rows
        if all(row[name] == value for name, value in filters.items())
    ]


def samples(rows: list[dict[str, object]], **filters: object) -> list[float]:
    values = [float(row["per_iteration_ms"]) for row in selected(rows, **filters)]
    if len(values) != 7:
        raise SystemExit(f"expected seven samples for {filters}, got {len(values)}")
    return values


def median(rows: list[dict[str, object]], **filters: object) -> float:
    return statistics.median(samples(rows, **filters))


def timing(rows: list[dict[str, object]], **filters: object) -> str:
    values = samples(rows, **filters)
    center = statistics.median(values)
    mad = statistics.median(abs(value - center) for value in values)
    relative_mad = 0.0 if center == 0.0 else mad / center * 100.0
    return f"{center:.4f} [{min(values):.4f}, {max(values):.4f}] ({relative_mad:.1f}%)"


def crossover(rows: list[dict[str, object]], family: str) -> str:
    for size in SIZES[family]:
        cpu = median(rows, family=family, backend="cpu", phase="hot", size=size)
        gpu = median(rows, family=family, backend="gpu", phase="hot", size=size)
        if gpu < cpu:
            return str(size)
    return "none on measured grid"


def write_csv(root: Path, rows: list[dict[str, object]]) -> None:
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_summary(
    root: Path,
    rows: list[dict[str, object]],
    rss: dict[str, list[int]],
) -> str:
    lines = [
        "# Tensor 0.1.0 memory and performance campaign",
        "",
        "Seven independent Release processes per group follow one Debug diagnostic run.",
        "Every Release process runs the functional verifier before measuring. Timings",
        "below are median [minimum, maximum] milliseconds per iteration, followed by",
        "relative MAD. GPU compute regions include dispatch, explicit completion wait and",
        "result allocation; cold rows also include first pipeline creation. Upload and",
        "download are reported separately.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "## CPU construction and extraction",
        "",
        "Equal cardinality: 65,536 elements. Construction receives an already populated",
        "typed Silex array; extraction materializes the public typed array.",
        "",
        "| Dtype | Bytes | Construction ms | Extraction ms |",
        "| --- | ---: | ---: | ---: |",
    ]
    for dtype in DTYPES:
        row = selected(
            rows, family="cpu_memory", dtype=dtype,
            transfer_mode="equal_cardinality",
        )[0]
        lines.append(
            f"| `{dtype}` | {int(row['bytes'])} | "
            f"{timing(rows, family='cpu_memory', dtype=dtype, phase='construction')} | "
            f"{timing(rows, family='cpu_memory', dtype=dtype, phase='extraction')} |"
        )

    for mode, title in (
        ("equal_cardinality", "Equal-cardinality transfers"),
        ("equal_bytes", "Equal-byte transfers"),
    ):
        lines.extend([
            "",
            f"## {title}",
            "",
            "| Dtype | Elements | Bytes | Upload ms | Upload MiB/s | Download ms | Download MiB/s |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for dtype in DTYPES:
            upload_rows = selected(
                rows, family="transfer", dtype=dtype, phase="upload",
                transfer_mode=mode,
            )
            row = upload_rows[0]
            upload = statistics.median(float(item["per_iteration_ms"]) for item in upload_rows)
            download_rows = selected(
                rows, family="transfer", dtype=dtype, phase="download",
                transfer_mode=mode,
            )
            download = statistics.median(float(item["per_iteration_ms"]) for item in download_rows)
            mib = int(row["bytes"]) / (1024.0 * 1024.0)
            lines.append(
                f"| `{dtype}` | {int(row['elements'])} | {int(row['bytes'])} | "
                f"{timing(rows, family='transfer', dtype=dtype, phase='upload', transfer_mode=mode)} | "
                f"{mib / (upload / 1000.0):.2f} | "
                f"{timing(rows, family='transfer', dtype=dtype, phase='download', transfer_mode=mode)} | "
                f"{mib / (download / 1000.0):.2f} |"
            )

    lines.extend([
        "",
        "## Float32 compute grids",
        "",
        "No upload or download occurs in GPU cold/hot rows. CPU and GPU compare the",
        "same logical cardinality; matmul `size` is the side of two square matrices.",
        "",
        "| Family | Size | CPU hot ms | GPU cold ms | GPU hot ms | Resident speedup |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for family in ("elementwise", "reduction", "matmul"):
        for size in SIZES[family]:
            cpu = median(rows, family=family, backend="cpu", phase="hot", size=size)
            gpu = median(rows, family=family, backend="gpu", phase="hot", size=size)
            lines.append(
                f"| `{family}` | {size} | "
                f"{timing(rows, family=family, backend='cpu', phase='hot', size=size)} | "
                f"{timing(rows, family=family, backend='gpu', phase='cold', size=size)} | "
                f"{timing(rows, family=family, backend='gpu', phase='hot', size=size)} | "
                f"{cpu / gpu:.2f}× |"
            )

    lines.extend([
        "",
        "## Five-operation resident chain",
        "",
        "The exact public chain is `add -> multiply -> matmul -> sum -> add`. Each GPU",
        "cold/hot iteration records five compute passes and zero intermediate readbacks.",
        "End-to-end adds two input uploads and the final scalar download to one hot chain.",
        "",
        "| Size | CPU hot ms | Upload ms | GPU cold ms | GPU hot ms | Download ms | Resident speedup | End-to-end speedup |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    resident_wins = 0
    for size in SIZES["resident_chain_5"]:
        cpu = median(rows, family="resident_chain_5", backend="cpu", phase="hot", size=size)
        upload = median(rows, family="resident_chain_5", backend="gpu", phase="upload", size=size)
        hot = median(rows, family="resident_chain_5", backend="gpu", phase="hot", size=size)
        download = median(rows, family="resident_chain_5", backend="gpu", phase="download", size=size)
        if hot < cpu:
            resident_wins += 1
        lines.append(
            f"| {size} | "
            f"{timing(rows, family='resident_chain_5', backend='cpu', phase='hot', size=size)} | "
            f"{timing(rows, family='resident_chain_5', backend='gpu', phase='upload', size=size)} | "
            f"{timing(rows, family='resident_chain_5', backend='gpu', phase='cold', size=size)} | "
            f"{timing(rows, family='resident_chain_5', backend='gpu', phase='hot', size=size)} | "
            f"{timing(rows, family='resident_chain_5', backend='gpu', phase='download', size=size)} | "
            f"{cpu / hot:.2f}× | {cpu / (upload + hot + download):.2f}× |"
        )

    chain_crossover = crossover(rows, "resident_chain_5")
    lines.extend([
        "",
        "## Observed recommendation",
        "",
        f"- Elementwise resident crossover: {crossover(rows, 'elementwise')} elements.",
        f"- Global-sum resident crossover: {crossover(rows, 'reduction')} elements.",
        f"- Square-matmul resident crossover: side {crossover(rows, 'matmul')}.",
        f"- Five-operation chain resident crossover: side {chain_crossover}.",
        "- Integer rows measure storage and exact round trips only; Tensor 0.1.0 does",
        "  not claim integer GPU compute acceleration.",
        "- Transfer-inclusive decisions must use the end-to-end column, not the resident",
        "  speedup alone. Reuse GPU-resident inputs across several operations whenever",
        "  upload and download would otherwise dominate.",
        "",
    ])
    if resident_wins == 0:
        lines.append(
            "**Release gate: blocked.** The GPU did not beat the CPU on any measured "
            "resident chain."
        )
    else:
        lines.append(
            "**Release gate: passed on this machine.** The GPU beats the CPU on "
            f"{resident_wins}/3 representative resident-chain sizes; command counters "
            "show no hidden upload/download inside the chain."
        )

    wide_ranges: list[str] = []
    for family in ("matmul", "resident_chain_5"):
        for size in SIZES[family]:
            values = samples(rows, family=family, backend="cpu", phase="hot", size=size)
            if min(values) > 0.0 and max(values) / min(values) >= 4.0:
                wide_ranges.append(f"`{family}/{size}`")
    if wide_ranges:
        lines.extend([
            "",
            "## Measurement limitations",
            "",
            "CPU process timings showed multiple scheduling regimes for "
            + ", ".join(wide_ranges)
            + ". All seven samples remain in the report with no outlier rejection. "
            "Use the median for this run, inspect the full range, and do not generalize "
            "the resulting speedup ratios.",
        ])

    lines.extend([
        "",
        "## Peak process memory",
        "",
        "`/usr/bin/time -l` peak resident size includes runtime and driver allocations.",
        "",
        "| Group | Median bytes | Range bytes |",
        "| --- | ---: | ---: |",
    ])
    for group in GROUPS:
        values = rss[group]
        lines.append(
            f"| `{group}` | {statistics.median(values):.0f} | "
            f"[{min(values)}, {max(values)}] |"
        )
    lines.extend([
        "",
        "These results are local macOS ARM64 evidence for the exact commits above.",
        "They do not predict another CPU architecture, GPU, driver or backend.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    root = Path(sys.argv[1])
    rows, rss = parse(root)
    write_csv(root, rows)
    (root / "Summary.md").write_text(build_summary(root, rows, rss))


if __name__ == "__main__":
    main()
