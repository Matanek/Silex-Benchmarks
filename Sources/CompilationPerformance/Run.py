#!/usr/bin/env python3
"""Measure Silex compilation misses and hits from one disposable root cache."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


TRACE_ENVIRONMENT = "SILEX_COMPILATION_TRACE"
OWNER_MARKER = "compilation-performance-owner"
REAL_DARWIN = re.compile(r"^\s*([0-9.]+)\s+real\b", re.MULTILINE)
RSS_DARWIN = re.compile(r"^\s*(\d+)\s+maximum resident set size\b", re.MULTILINE)
REAL_GNU = re.compile(r"^\s*Elapsed \(wall clock\) time.*:\s*([0-9:.]+)\s*$", re.MULTILINE)
RSS_GNU = re.compile(r"^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$", re.MULTILINE)


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"error: {message}")


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            candidate = Path(root) / name
            try:
                total += candidate.stat().st_size
            except FileNotFoundError:
                pass
    return total


def elapsed_gnu(value: str) -> float:
    fields = value.split(":")
    if len(fields) == 2:
        return float(fields[0]) * 60 + float(fields[1])
    if len(fields) == 3:
        return float(fields[0]) * 3600 + float(fields[1]) * 60 + float(fields[2])
    return float(value)


def external_metrics(source: str) -> tuple[float, int]:
    if platform.system() == "Darwin":
        real = REAL_DARWIN.search(source)
        rss = RSS_DARWIN.search(source)
        if real is None or rss is None:
            fail("cannot parse macOS /usr/bin/time output")
        return float(real.group(1)), int(rss.group(1))
    real = REAL_GNU.search(source)
    rss = RSS_GNU.search(source)
    if real is None or rss is None:
        fail("cannot parse GNU /usr/bin/time output")
    return elapsed_gnu(real.group(1)), int(rss.group(1)) * 1024


def resolve_packages(silex: Path, workspace: Path, source: Path) -> list[dict[str, str]]:
    result = subprocess.run(
        [str(silex), "packages", "resolve", str(source)],
        cwd=workspace,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    packages: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) != 4:
            fail(f"unexpected package resolution line: {line}")
        packages.append(
            {"name": fields[0], "version": fields[1], "origin": fields[2], "path": fields[3]}
        )
    return packages


def install_workspace_links(
    silex: Path,
    workspace: Path,
    packages_root: Path,
    source: Path,
) -> list[dict[str, str]]:
    discovered = resolve_packages(silex, workspace, source)
    for package in discovered:
        candidate = packages_root / package["name"]
        if not candidate.is_dir():
            fail(f"workspace package is missing: {candidate}")
        subprocess.run(
            [str(silex), "link", str(candidate), "--workspace", str(workspace)],
            cwd=workspace,
            check=True,
            stdout=subprocess.DEVNULL,
        )

    resolved = resolve_packages(silex, workspace, source)
    for package in resolved:
        expected = (packages_root / package["name"]).resolve()
        actual = Path(package["path"]).resolve()
        if package["origin"] != "workspace-link" or actual != expected:
            fail(
                f"{package['name']} resolved as {package['origin']} {actual}; "
                f"expected workspace-link {expected}"
            )
        package["commit"] = git(actual, "rev-parse", "HEAD")
        package["dirty"] = "true" if git(actual, "status", "--short") else "false"
    return resolved


def timed_command() -> list[str]:
    return ["/usr/bin/time", "-l"] if platform.system() == "Darwin" else ["/usr/bin/time", "-v"]


def run_sample(
    *,
    profile: str,
    repetition: int,
    silex: Path,
    workspace: Path,
    source: Path,
    output: Path,
    results: Path,
    cache_enabled: bool,
    trace_enabled: bool,
) -> dict[str, Any]:
    stem = f"{profile}-{repetition:02d}"
    trace_path = results / f"{stem}.trace.json"
    stdout_path = results / f"{stem}.stdout.log"
    time_path = results / f"{stem}.time.log"
    command = [
        *timed_command(),
        str(silex),
        "compile",
        str(source),
        "--release",
        "--output",
        str(output),
    ]
    if not cache_enabled:
        command.append("--nocache")
    environment = os.environ.copy()
    zig_cache = workspace / ".compilation-performance" / "zig-cache"
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(zig_cache / "global")
    environment["ZIG_LOCAL_CACHE_DIR"] = str(zig_cache / "local")
    if trace_enabled:
        environment[TRACE_ENVIRONMENT] = str(trace_path)
    else:
        environment.pop(TRACE_ENVIRONMENT, None)

    cache_path = workspace / ".silex"
    cache_before = directory_bytes(cache_path)
    with stdout_path.open("wb") as stdout_file, time_path.open("wb") as time_file:
        result = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            stdout=stdout_file,
            stderr=time_file,
        )
    if result.returncode != 0:
        fail(f"{profile} repetition {repetition} failed; inspect {time_path}")
    timing = time_path.read_text(errors="replace")
    wall_seconds, peak_rss_bytes = external_metrics(timing)
    trace = json.loads(trace_path.read_text()) if trace_enabled else None
    if trace is not None and not trace.get("success", False):
        fail(f"compiler trace reports failure for {profile} repetition {repetition}")
    return {
        "repetition": repetition,
        "wall_seconds": wall_seconds,
        "peak_rss_bytes": peak_rss_bytes,
        "cache_bytes_before": cache_before,
        "cache_bytes_after": directory_bytes(cache_path),
        "trace": trace,
        "command": command[len(timed_command()) :],
    }


def profile_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "runs": len(samples),
        "median_wall_seconds": statistics.median(sample["wall_seconds"] for sample in samples),
        "min_wall_seconds": min(sample["wall_seconds"] for sample in samples),
        "max_wall_seconds": max(sample["wall_seconds"] for sample in samples),
        "median_peak_rss_bytes": int(
            statistics.median(sample["peak_rss_bytes"] for sample in samples)
        ),
        "maximum_cache_bytes": max(sample["cache_bytes_after"] for sample in samples),
    }


def write_reports(results: Path, report: dict[str, Any]) -> None:
    (results / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Silex compilation baseline",
        "",
        f"- Captured: `{report['metadata']['captured']}`",
        f"- OS: `{report['metadata']['platform']}`",
        f"- Architecture: `{report['metadata']['architecture']}`",
        f"- Runs per profile: `{report['metadata']['runs']}`",
        f"- Silex commit: `{report['metadata']['silex_commit']}`",
        f"- Benchmarks commit: `{report['metadata']['benchmarks_commit']}`",
        f"- Examples commit: `{report['metadata']['examples_commit']}`",
        "",
        "| Profile | Median wall | Range | Median peak RSS | Maximum root cache |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, summary in report["summaries"].items():
        lines.append(
            f"| `{name}` | {summary['median_wall_seconds']:.3f} s | "
            f"{summary['min_wall_seconds']:.3f}–{summary['max_wall_seconds']:.3f} s | "
            f"{summary['median_peak_rss_bytes'] / 1024 / 1024:.1f} MiB | "
            f"{summary['maximum_cache_bytes'] / 1024 / 1024:.1f} MiB |"
        )
    traced = report["summaries"]["cold_no_cache"]["median_wall_seconds"]
    plain = report["summaries"]["cold_no_trace"]["median_wall_seconds"]
    overhead = 0.0 if plain == 0 else (traced / plain - 1.0) * 100.0
    lines.extend(
        [
            "",
            f"Trace overhead on the cold profile: `{overhead:+.2f}%`.",
            "",
            "`cold_no_cache` measures a real compiler miss with `--nocache`. "
            "`shared_packages` compiles a distinct entry after another GFX entry. "
            "`entry_modified` changes only the entry text. `exact_hit` repeats the "
            "same source, options and output after priming.",
            "",
        ]
    )
    (results / "SUMMARY.md").write_text("\n".join(lines))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--packages-root", type=Path, required=True)
    parser.add_argument("--silex", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--warm-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    workspace = arguments.workspace.resolve()
    packages_root = arguments.packages_root.resolve()
    silex = arguments.silex.resolve()
    primary = arguments.primary.resolve()
    warm_source = arguments.warm_source.resolve()
    results = arguments.output.resolve()
    if arguments.runs < 1 or arguments.warmups < 0:
        fail("--runs must be positive and --warmups must be non-negative")
    for path, label in ((workspace, "workspace"), (packages_root, "packages root")):
        if not path.is_dir():
            fail(f"{label} is not a directory: {path}")
    if not os.access(silex, os.X_OK):
        fail(f"Silex binary is not executable: {silex}")
    for source in (primary, warm_source):
        if not source.is_file():
            fail(f"source does not exist: {source}")

    cache = workspace / ".silex"
    scratch = workspace / ".compilation-performance"
    entry = primary.parent / "CompilationPerformanceEntry.sx"
    if cache.exists():
        fail(f"refusing to touch pre-existing cache: {cache}")
    if scratch.exists() or entry.exists() or results.exists():
        fail("scratch entry, scratch directory, or result directory already exists")

    token = uuid.uuid4().hex
    results.mkdir(parents=True)
    scratch.mkdir()
    profiles: dict[str, list[dict[str, Any]]] = {
        "cold_no_trace": [],
        "cold_no_cache": [],
        "shared_packages": [],
        "entry_modified": [],
        "exact_hit": [],
    }
    try:
        cache.mkdir()
        marker = cache / OWNER_MARKER
        marker.write_text(token)
        packages = install_workspace_links(silex, workspace, packages_root, primary)

        primary_source = primary.read_text()
        for warmup in range(arguments.warmups):
            run_sample(
                profile="warmup",
                repetition=warmup + 1,
                silex=silex,
                workspace=workspace,
                source=primary,
                output=scratch / f"warmup-{warmup + 1}",
                results=results,
                cache_enabled=False,
                trace_enabled=False,
            )

        for repetition in range(1, arguments.runs + 1):
            cold_order = (
                ("cold_no_trace", False),
                ("cold_no_cache", True),
            )
            if repetition % 2 == 0:
                cold_order = tuple(reversed(cold_order))
            for profile_name, trace_enabled in cold_order:
                file_name = profile_name.replace("_", "-")
                profiles[profile_name].append(
                    run_sample(
                        profile=file_name,
                        repetition=repetition,
                        silex=silex,
                        workspace=workspace,
                        source=primary,
                        output=scratch / f"{file_name}-{repetition}",
                        results=results,
                        cache_enabled=False,
                        trace_enabled=trace_enabled,
                    )
                )

        run_sample(
            profile="shared-prime",
            repetition=1,
            silex=silex,
            workspace=workspace,
            source=warm_source,
            output=scratch / "shared-prime",
            results=results,
            cache_enabled=True,
            trace_enabled=True,
        )
        for repetition in range(1, arguments.runs + 1):
            entry.write_text(primary_source + f"\n// shared profile {repetition}\n")
            profiles["shared_packages"].append(
                run_sample(
                    profile="shared-packages",
                    repetition=repetition,
                    silex=silex,
                    workspace=workspace,
                    source=entry,
                    output=scratch / f"shared-packages-{repetition}",
                    results=results,
                    cache_enabled=True,
                    trace_enabled=True,
                )
            )

        for repetition in range(1, arguments.runs + 1):
            entry.write_text(primary_source + f"\n// entry modification {repetition}\n")
            profiles["entry_modified"].append(
                run_sample(
                    profile="entry-modified",
                    repetition=repetition,
                    silex=silex,
                    workspace=workspace,
                    source=entry,
                    output=scratch / "entry-modified",
                    results=results,
                    cache_enabled=True,
                    trace_enabled=True,
                )
            )

        entry.write_text(primary_source + "\n// exact hit profile\n")
        run_sample(
            profile="exact-prime",
            repetition=1,
            silex=silex,
            workspace=workspace,
            source=entry,
            output=scratch / "exact-hit",
            results=results,
            cache_enabled=True,
            trace_enabled=True,
        )
        for repetition in range(1, arguments.runs + 1):
            sample = run_sample(
                profile="exact-hit",
                repetition=repetition,
                silex=silex,
                workspace=workspace,
                source=entry,
                output=scratch / "exact-hit",
                results=results,
                cache_enabled=True,
                trace_enabled=True,
            )
            if sample["trace"]["cache_result"] != "hit_before_frontend":
                fail("exact hit profile did not hit before the frontend")
            profiles["exact_hit"].append(sample)

        metadata = {
            "captured": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "runs": arguments.runs,
            "warmups": arguments.warmups,
            "workspace": str(workspace),
            "silex_binary": str(silex),
            "silex_version": subprocess.run(
                [str(silex), "--version"], check=True, text=True, stdout=subprocess.PIPE
            ).stdout.strip(),
            "silex_commit": git(workspace / "Silex", "rev-parse", "HEAD"),
            "benchmarks_commit": git(workspace / "Silex-Benchmarks", "rev-parse", "HEAD"),
            "examples_commit": git(workspace / "Silex-Examples", "rev-parse", "HEAD"),
            "primary": str(primary),
            "warm_source": str(warm_source),
            "packages": packages,
        }
        report = {
            "metadata": metadata,
            "profiles": profiles,
            "summaries": {name: profile_summary(samples) for name, samples in profiles.items()},
        }
        write_reports(results, report)
        print(results)
        return 0
    finally:
        entry.unlink(missing_ok=True)
        shutil.rmtree(scratch, ignore_errors=True)
        marker = cache / OWNER_MARKER
        if marker.is_file() and marker.read_text() == token and not cache.is_symlink():
            shutil.rmtree(cache)


if __name__ == "__main__":
    sys.exit(main())
