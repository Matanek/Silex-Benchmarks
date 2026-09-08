#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import statistics
import sys
from pathlib import Path


AGENT_COUNTS = (1_000, 10_000, 100_000)
WAKE_PERCENTAGES = (0, 1, 10, 100)
STRATEGIES = ("root", "resume", "event", "state_machine")
LINE = re.compile(r"^SILEX_BEHAVIOUR_TREE (?P<fields>.+)$")
FIELD = re.compile(r"([a-z_]+)=([^ ]+)")


def expected_frames(agents: int) -> int:
    return {1_000: 1_000, 10_000: 100, 100_000: 10}[agents]


def parse(root: Path) -> list[dict[str, object]]:
    verification = (root / "verification.log").read_text()
    if "result=equivalent" not in verification:
        raise SystemExit("functional verification did not pass")

    rows: list[dict[str, object]] = []
    for agents in AGENT_COUNTS:
        for wake_percent in WAKE_PERCENTAGES:
            for strategy in STRATEGIES:
                for repetition in range(1, 8):
                    output = root / f"{agents}-{wake_percent}-{strategy}-{repetition}.log"
                    matches = [
                        dict(FIELD.findall(match.group("fields")))
                        for line in output.read_text().splitlines()
                        if (match := LINE.match(line))
                    ]
                    if len(matches) != 1:
                        raise SystemExit(f"invalid measurement in {output}")
                    fields = matches[0]
                    row: dict[str, object] = {
                        "agents": int(fields["agents"]),
                        "wake_percent": int(fields["wake_percent"]),
                        "strategy": fields["strategy"],
                        "process": repetition,
                        "woken": int(fields["woken"]),
                        "warmup": int(fields["warmup"]),
                        "frames": int(fields["frames"]),
                        "elapsed_ms": float(fields["elapsed_ms"]),
                        "per_frame_ms": float(fields["per_frame_ms"]),
                        "condition_calls": int(fields["condition_calls"]),
                        "action_calls": int(fields["action_calls"]),
                        "node_visits": int(fields["node_visits"]),
                        "queue_size": int(fields["queue_size"]),
                        "checksum": int(fields["checksum"]),
                        "tree_nodes": int(fields["tree_nodes"]),
                        "tree_depth": int(fields["tree_depth"]),
                        "root_width": int(fields["root_width"]),
                    }
                    validate_row(row, agents, wake_percent, strategy, output)
                    rows.append(row)
    return rows


def validate_row(
    row: dict[str, object],
    agents: int,
    wake_percent: int,
    strategy: str,
    output: Path,
) -> None:
    frames = expected_frames(agents)
    woken = agents * wake_percent // 100
    if row["agents"] != agents or row["wake_percent"] != wake_percent:
        raise SystemExit(f"matrix identity mismatch in {output}")
    if row["strategy"] != strategy or row["frames"] != frames:
        raise SystemExit(f"strategy or frame mismatch in {output}")
    if row["woken"] != woken or row["queue_size"] != woken:
        raise SystemExit(f"wake queue mismatch in {output}")
    if (row["tree_nodes"], row["tree_depth"], row["root_width"]) != (11, 5, 2):
        raise SystemExit(f"tree shape mismatch in {output}")

    expected_checksum = frames * woken * (woken + 1) // 2
    if row["checksum"] != expected_checksum:
        raise SystemExit(f"final-state checksum mismatch in {output}")

    if strategy == "root":
        expected_conditions = agents * frames * 4
        expected_actions = agents * frames
        expected_visits = agents * frames * 10
    elif strategy == "resume":
        expected_conditions = 0
        expected_actions = agents * frames
        expected_visits = agents * frames
    elif strategy == "event":
        expected_conditions = 0
        expected_actions = woken * frames
        expected_visits = woken * frames
    else:
        expected_conditions = 0
        expected_actions = woken * frames
        expected_visits = 0
    observed = (row["condition_calls"], row["action_calls"], row["node_visits"])
    expected = (expected_conditions, expected_actions, expected_visits)
    if observed != expected:
        raise SystemExit(f"structural counters mismatch in {output}: {observed} != {expected}")


def selected(
    rows: list[dict[str, object]], agents: int, wake_percent: int, strategy: str
) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if row["agents"] == agents
        and row["wake_percent"] == wake_percent
        and row["strategy"] == strategy
    ]


def timings(
    rows: list[dict[str, object]], agents: int, wake_percent: int, strategy: str
) -> list[float]:
    return [float(row["per_frame_ms"]) for row in selected(rows, agents, wake_percent, strategy)]


def stable(rows: list[dict[str, object]], field: str) -> int:
    values = {int(row[field]) for row in rows}
    if len(values) != 1:
        raise SystemExit(f"unstable {field}: {sorted(values)}")
    return values.pop()


def validate_sparse_advantage(rows: list[dict[str, object]]) -> None:
    for agents in AGENT_COUNTS:
        for wake_percent in (1, 10):
            event = timings(rows, agents, wake_percent, "event")
            root = timings(rows, agents, wake_percent, "root")
            resume = timings(rows, agents, wake_percent, "resume")
            if max(event) >= min(root) or max(event) >= min(resume):
                raise SystemExit(
                    "event scheduling is not separated from full-population strategies "
                    f"for agents={agents} wake={wake_percent}%: "
                    f"event={event} root={root} resume={resume}"
                )


def main() -> None:
    root = Path(sys.argv[1])
    rows = parse(root)
    validate_sparse_advantage(rows)
    with (root / "measurements.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Behaviour Tree scheduling",
        "",
        "Seven independent Release processes per matrix row after an in-process warm-up.",
        "CPU time is the arithmetic mean, sample variance and measured range. Structural",
        "counters come from a separate replay, so the public transition observer does not",
        "alter the timed loop. The functional verifier established identical final business",
        "state for all four strategies before the campaign.",
        "",
        "```text",
        (root / "metadata.txt").read_text().strip(),
        "```",
        "",
        "| Agents | Wake | Strategy | CPU ms/frame mean | Variance | Range | Conditions | Actions | Nodes | Queue | vs state machine |",
        "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for agents in AGENT_COUNTS:
        for wake_percent in WAKE_PERCENTAGES:
            machine = timings(rows, agents, wake_percent, "state_machine")
            machine_mean = statistics.mean(machine)
            for strategy in STRATEGIES:
                group = selected(rows, agents, wake_percent, strategy)
                samples = [float(row["per_frame_ms"]) for row in group]
                mean = statistics.mean(samples)
                ratio = mean / machine_mean if machine_mean > 0.0 else float("inf")
                lines.append(
                    f"| {agents} | {wake_percent}% | `{strategy}` | {mean:.6f} | "
                    f"{statistics.variance(samples):.9f} | [{min(samples):.6f}, {max(samples):.6f}] | "
                    f"{stable(group, 'condition_calls')} | {stable(group, 'action_calls')} | "
                    f"{stable(group, 'node_visits')} | {stable(group, 'queue_size')} | {ratio:.2f}x |"
                )
    lines.extend([
        "",
        "The event strategy visits zero nodes at 0% wake-up and its structural work is",
        "exactly `woken agents × measured frames` at 1%, 10%, and 100%. For sparse 1%",
        "and 10% rows, its entire measured range is below the ranges of both strategies",
        "that scan the full population. Ratios against the handwritten state machine are",
        "reported as context, not as a promise that a generic tree beats specialized code.",
        "",
        "These macOS ARM64 measurements characterize this machine and exact commits only;",
        "they are neither an x64 result nor a portable performance guarantee.",
        "",
    ])
    (root / "Summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
