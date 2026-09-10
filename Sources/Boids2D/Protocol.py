#!/usr/bin/env python3
"""Deterministic Boids ordering, raw-log audit and fixed-window stationarity."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

LABELS = ("silex", "cpp-architectural", "cpp-direct")
PREFIXES = ("SILEX_GFX_BOIDS", "CPP_ARCHITECTURAL_BOIDS", "CPP_DIRECT_BOIDS")
ORDERS = tuple(itertools.permutations(range(3)))
POLICY_PATH = Path(__file__).with_name("Protocol.json")
POLICY = json.loads(POLICY_PATH.read_text())


def schedule(warmups, runs):
    for round_index in range(warmups + runs):
        phase = "warmup" if round_index < warmups else "sample"
        for position, witness in enumerate(ORDERS[round_index % len(ORDERS)], 1):
            yield phase, round_index + 1, position, LABELS[witness]


def summarize(values):
    if len(values) < 6 or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("need at least six positive finite samples")
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    center = (len(values) - 1) / 2
    slope = sum((i - center) * v for i, v in enumerate(values)) / sum(
        (i - center) ** 2 for i in range(len(values)))
    half = len(values) // 2
    drift = slope * (len(values) - 1) / median
    shift = (statistics.median(values[half:]) - statistics.median(values[:half])) / median
    checks = {"mad": mad / median, "range": (max(values) - min(values)) / median,
              "drift": abs(drift), "half_shift": abs(shift)}
    failures = [f"{key}={value:.6f} exceeds {POLICY['max_' + key + '_fraction']:.6f}"
                for key, value in checks.items() if value > POLICY['max_' + key + '_fraction']]
    return {"values": values, "median": median, "mad": mad,
            "minimum": min(values), "maximum": max(values),
            "drift_fraction": drift, "half_shift_fraction": shift,
            "failures": failures, "stationary": not failures}


def semantic_signature(data):
    if int(data["count"]) != POLICY["count"] or int(data["frames"]) != POLICY["frames"]:
        raise ValueError("noncanonical workload")
    if abs(float(data["fixed_delta"]) - 1 / 60) > 1e-7 or int(data["state_step"]) != 4:
        raise ValueError("noncanonical simulation delta or state step")
    if data["present"] != "immediate":
        raise ValueError("noncanonical presentation")
    window = tuple(map(float, data["window"].split("x")))
    pixels = tuple(map(float, data["pixels"].split("x")))
    scale, density = float(data["scale"]), float(data["density"])
    if window != (960, 640) or len(pixels) != 2 or any(not math.isfinite(v) or v <= 0 for v in (*pixels, scale, density)):
        raise ValueError("invalid display dimensions")
    state = [float(data[f"{stage}_{component}"]) for stage in ("initial", "state")
             for component in ("px", "py", "vx", "vy", "p2", "v2")]
    if any(not math.isfinite(v) for v in (*state, float(data["fixed_delta"]))):
        raise ValueError("nonfinite semantic witness")
    return (*window, *pixels, scale, density), state


def analyze(path):
    metadata = {}
    events = []
    sentinels = []
    pending = None
    reference = None
    for line in path.read_text().splitlines():
        if line.startswith("# event="):
            if pending is not None:
                raise ValueError("event without matching sentinel")
            phase, round_index, position, label = line.removeprefix("# event=").split(",")
            pending = (phase, int(round_index), int(position), label)
            events.append(pending)
        elif line.startswith("# ") and "=" in line:
            key, value = line[2:].split("=", 1)
            if key in metadata:
                raise ValueError(f"duplicate metadata {key}")
            metadata[key] = value
        elif line.split(" ", 1)[0] in PREFIXES:
            if pending is None:
                raise ValueError("sentinel without execution event")
            fields = line.split()
            label = LABELS[PREFIXES.index(fields[0])]
            if label != pending[3]:
                raise ValueError("actual witness contradicts order metadata")
            data = dict(field.split("=", 1) for field in fields[1:])
            if len(data) != len(fields) - 1:
                raise ValueError("duplicate sentinel field")
            signature = semantic_signature(data)
            if reference is None:
                reference = signature
            elif signature[0] != reference[0] or any(abs(a - b) > 0.05 + max(abs(a), abs(b)) * 0.00002
                                                    for a, b in zip(reference[1], signature[1])):
                raise ValueError("display or deterministic state mismatch")
            if int(data["count"]) != POLICY["count"] or int(data["frames"]) != POLICY["frames"]:
                raise ValueError("noncanonical workload")
            fps = float(data["fps"])
            if not math.isfinite(fps) or fps <= 0:
                raise ValueError("invalid FPS")
            sentinels.append((pending, fps))
            pending = None
    if pending is not None:
        raise ValueError("incomplete final process")
    if metadata.get("protocol_sha256") != hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest():
        raise ValueError("protocol hash differs from sealed rule")
    seal_path = path.with_name(path.name + ".seal.json")
    if metadata.get("artifact_seal_sha256") != hashlib.sha256(seal_path.read_bytes()).hexdigest():
        raise ValueError("artifact seal hash mismatch")
    warmups, runs = int(metadata["warmups"]), int(metadata["runs"])
    if events != list(schedule(warmups, runs)):
        raise ValueError("missing, duplicated, reordered or falsified execution events")
    if (warmups, runs) != (POLICY["warmups"], POLICY["runs"]):
        raise ValueError("diagnostic sample count differs from sealed window")
    values = {label: [] for label in LABELS}
    discarded = {label: [] for label in LABELS}
    for event, fps in sentinels:
        (discarded if event[0] == "warmup" else values)[event[3]].append(fps)
    series = {label: summarize(v) for label, v in values.items()}
    for witness in LABELS[1:]:
        series[f"silex/{witness}"] = summarize([a / b for a, b in zip(values["silex"], values[witness])])
    failures = [f"{label}: {failure}" for label, result in series.items() for failure in result["failures"]]
    if metadata.get("source_repositories_dirty") != "false":
        failures.append("source repositories dirty or provenance unavailable")
    return {"protocol": POLICY, "metadata": metadata,
            "workload_signature": reference,
            "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "discarded_window": [1, warmups], "accepted_window": [warmups + 1, warmups + runs],
            "discarded_values": discarded, "series": series, "failures": failures,
            "verdict": "inconclusive" if failures else "stationary"}


def compare(first, second):
    failures = []
    for report in (first, second):
        if report["verdict"] != "stationary":
            failures.append("capture is not stationary")
    for key in ("artifact_seal_sha256", "protocol_sha256", "cpu", "os", "architecture"):
        if not first["metadata"].get(key) or first["metadata"].get(key) != second["metadata"].get(key):
            failures.append(f"capture identity mismatch: {key}")
    if first["workload_signature"] != second["workload_signature"]:
        failures.append("capture workload signature mismatch")
    for label in first["series"]:
        a, b = first["series"][label]["median"], second["series"][label]["median"]
        if abs(b / a - 1) > POLICY["max_repeat_median_fraction"]:
            failures.append(f"repeat median differs by more than sealed budget: {label}")
    return {"verdict": "inconclusive" if failures else "repeatable", "failures": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("schedule", "analyze", "compare"))
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--warmups", type=int, default=POLICY["warmups"])
    parser.add_argument("--runs", type=int, default=POLICY["runs"])
    args = parser.parse_args()
    if args.command == "schedule":
        for event in schedule(args.warmups, args.runs):
            print(*event)
        return 0
    try:
        reports = [analyze(path) for path in args.paths]
        result = compare(*reports) if args.command == "compare" else reports[0]
    except (ValueError, KeyError, OSError) as error:
        result = {"verdict": "invalid", "failures": [str(error)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] in ("stationary", "repeatable") else 2


if __name__ == "__main__":
    raise SystemExit(main())
