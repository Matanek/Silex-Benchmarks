#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


FAMILIES = ("mlp", "cnn", "rnn")
PROCESSES = 5
BATCHES = {
    "mlp": (4, 16, 64),
    "cnn": (1, 4, 16),
    "rnn": (4, 16, 64),
}
PHASES = (
    "construction", "forward_cold", "forward_hot", "backward_cold",
    "backward_hot", "step_sgd", "step_adam", "loss_read",
    "step_resident", "step_end_to_end",
)
LINE = re.compile(r"^SILEX_TENSOR_NEURAL (?P<fields>.+)$")
FIELD = re.compile(r"([a-z0-9_]+)=([^ ]+)")
VERIFY = re.compile(r"^SILEX_TENSOR_NEURAL_VERIFY status=pass ")
RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size\s*$")


def parse(root: Path) -> tuple[list[dict[str, object]], dict[str, list[int]]]:
    rows: list[dict[str, object]] = []
    rss: dict[str, list[int]] = {family: [] for family in FAMILIES}
    for family in FAMILIES:
        for process in range(1, PROCESSES + 1):
            output = root / f"{family}-{process}.log"
            timing = root / f"{family}-{process}.time"
            lines = output.read_text().splitlines()
            if sum(bool(VERIFY.match(line)) for line in lines) != 1:
                raise SystemExit(f"missing functional verifier in {output}")
            matches = [
                dict(FIELD.findall(match.group("fields")))
                for line in lines
                if (match := LINE.match(line))
            ]
            if len(matches) != 54:
                raise SystemExit(f"expected 54 rows in {output}, got {len(matches)}")
            seen: set[tuple[str, ...]] = set()
            for fields in matches:
                key = (fields["phase"], fields["backend"], fields["batch"])
                if key in seen:
                    raise SystemExit(f"duplicate measurement {key} in {output}")
                seen.add(key)
                row: dict[str, object] = {
                    "family": fields["family"],
                    "process": process,
                    "phase": fields["phase"],
                    "backend": fields["backend"],
                    "batch": int(fields["batch"]),
                    "iterations": int(fields["iterations"]),
                    "elapsed_ms": float(fields["elapsed_ms"]),
                    "per_iteration_ms": float(fields["per_iteration_ms"]),
                    "observation": fields["observation"],
                    "uploads": int(fields["uploads"]),
                    "downloads": int(fields["downloads"]),
                    "compute_passes": int(fields["compute_passes"]),
                }
                validate_row(row, family, output)
                rows.append(row)
            rss_matches = [
                int(match.group(1))
                for line in timing.read_text().splitlines()
                if (match := RSS.match(line))
            ]
            if len(rss_matches) != 1:
                raise SystemExit(f"missing RSS measurement in {timing}")
            rss[family].append(rss_matches[0])
    validate_matrix(rows)
    return rows, rss


def validate_row(
    row: dict[str, object], expected_family: str, source: Path,
) -> None:
    family = str(row["family"])
    backend = str(row["backend"])
    phase = str(row["phase"])
    uploads = int(row["uploads"])
    downloads = int(row["downloads"])
    passes = int(row["compute_passes"])
    if family != expected_family:
        raise SystemExit(f"unexpected family {family} in {source}")
    if backend == "cpu" and (uploads or downloads or passes):
        raise SystemExit(f"CPU row exposes GPU commands in {source}")
    if backend == "gpu":
        if phase == "loss_read":
            if uploads != 0 or downloads != 1:
                raise SystemExit(f"invalid loss observation boundary in {source}")
        elif phase == "step_end_to_end":
            if uploads <= 0 or downloads <= 0 or passes <= 0:
                raise SystemExit(f"end-to-end row misses explicit boundaries in {source}")
        elif uploads != 0 or downloads != 0:
            raise SystemExit(f"hidden transfer in resident GPU row from {source}")
    if phase in ("forward_cold", "forward_hot", "backward_cold", "backward_hot",
                 "step_sgd", "step_adam", "step_resident", "step_end_to_end"):
        if backend == "gpu" and passes <= 0:
            raise SystemExit(f"GPU compute row has no compute pass in {source}")


def validate_matrix(rows: list[dict[str, object]]) -> None:
    for family in FAMILIES:
        observed_batches = {int(row["batch"]) for row in rows if row["family"] == family}
        if observed_batches != set(BATCHES[family]):
            raise SystemExit(f"unexpected {family} batches: {sorted(observed_batches)}")
        for process in range(1, PROCESSES + 1):
            process_rows = [
                row for row in rows
                if row["family"] == family and row["process"] == process
            ]
            for batch in BATCHES[family]:
                batch_rows = [row for row in process_rows if row["batch"] == batch]
                observed = {(str(row["phase"]), str(row["backend"])) for row in batch_rows}
                expected = {("construction", "cpu"), ("step_end_to_end", "gpu")}
                expected.update((phase, backend) for phase in PHASES[1:-1] for backend in ("cpu", "gpu"))
                if observed != expected:
                    raise SystemExit(f"incomplete matrix for {family} batch {batch} process {process}")


def samples(
    rows: list[dict[str, object]], family: str, batch: int, phase: str, backend: str,
) -> list[float]:
    values = [
        float(row["per_iteration_ms"])
        for row in rows
        if row["family"] == family and row["batch"] == batch
        and row["phase"] == phase and row["backend"] == backend
    ]
    if len(values) != PROCESSES:
        raise SystemExit(f"expected {PROCESSES} samples for {family}/{batch}/{phase}/{backend}")
    return values


def median_sample(
    rows: list[dict[str, object]], family: str, batch: int, phase: str, backend: str,
) -> float:
    return statistics.median(samples(rows, family, batch, phase, backend))


def timing(
    rows: list[dict[str, object]], family: str, batch: int, phase: str, backend: str,
) -> str:
    values = samples(rows, family, batch, phase, backend)
    center = statistics.median(values)
    mad = statistics.median(abs(value - center) for value in values)
    relative_mad = 0.0 if center == 0.0 else mad / center * 100.0
    return f"{center:.4f} [{min(values):.4f}, {max(values):.4f}] ({relative_mad:.1f}%)"


def write_csv(root: Path, rows: list[dict[str, object]]) -> None:
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_summary(
    root: Path, rows: list[dict[str, object]], rss: dict[str, list[int]],
) -> str:
    lines = [
        "# Tensor neural training campaign",
        "",
        "Five independent Release processes per family follow one Debug diagnostic run.",
        "Every Release process reruns the functional verifier. Timings below are median",
        "[minimum, maximum] milliseconds per iteration followed by relative MAD. GPU",
        "regions include explicit completion waits. Resident regions exclude transfers;",
        "loss readback and end-to-end rows expose their deliberate transfers separately.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
    ]
    for family in FAMILIES:
        lines.extend([
            "",
            f"## {family.upper()}",
            "",
            "| Batch | Phase | CPU ms | GPU ms | CPU/GPU ratio |",
            "| ---: | --- | ---: | ---: | ---: |",
        ])
        for batch in BATCHES[family]:
            for phase in ("forward_cold", "forward_hot", "backward_cold", "backward_hot",
                          "step_sgd", "step_adam", "loss_read", "step_resident"):
                cpu = median_sample(rows, family, batch, phase, "cpu")
                gpu = median_sample(rows, family, batch, phase, "gpu")
                ratio = 0.0 if gpu == 0.0 else cpu / gpu
                lines.append(
                    f"| {batch} | `{phase}` | {timing(rows, family, batch, phase, 'cpu')} | "
                    f"{timing(rows, family, batch, phase, 'gpu')} | {ratio:.2f}× |"
                )
            lines.append(
                f"| {batch} | `step_end_to_end` | n/a | "
                f"{timing(rows, family, batch, 'step_end_to_end', 'gpu')} | n/a |"
            )
        rss_mib = [value / (1024.0 * 1024.0) for value in rss[family]]
        lines.extend([
            "",
            f"Maximum process RSS: median {statistics.median(rss_mib):.1f} MiB "
            f"[{min(rss_mib):.1f}, {max(rss_mib):.1f}] across the five family processes.",
        ])
    representative = []
    for family in FAMILIES:
        for batch in BATCHES[family]:
            cpu = median_sample(rows, family, batch, "step_resident", "cpu")
            gpu = median_sample(rows, family, batch, "step_resident", "gpu")
            if gpu < cpu:
                representative.append(f"{family} batch {batch} ({cpu / gpu:.2f}×)")
    lines.extend([
        "",
        "## Interpretation boundary",
        "",
        "This is a local baseline for the machine and exact commits above, not a portable",
        "GPU performance claim. Package-private lifetime tests separately prove stable",
        "live autograd-edge and GPU-buffer counts across repeated optimizer steps.",
        "",
        "Resident GPU steps were faster on the measured grid only for: "
        + (", ".join(representative) if representative else "none of the measured cases")
        + ".",
        "Cold execution, scalar observation, and end-to-end transfer costs must remain",
        "separate when interpreting that result.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: SummarizeNeural.py RESULTS_DIRECTORY")
    root = Path(sys.argv[1])
    rows, rss = parse(root)
    write_csv(root, rows)
    (root / "Summary.md").write_text(build_summary(root, rows, rss))


if __name__ == "__main__":
    main()
