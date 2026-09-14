"""Shared statistical and semantic checks for the Boids comparison runner."""
import json
import math
from pathlib import Path
import statistics

POLICY_PATH = Path(__file__).with_name("Protocol.json")
POLICY = json.loads(POLICY_PATH.read_text())


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
