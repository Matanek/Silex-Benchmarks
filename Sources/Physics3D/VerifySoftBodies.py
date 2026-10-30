#!/usr/bin/env python3
"""Compare retained soft constraints and check the Silex public consumer."""

import argparse
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path


def execute(binary, arguments):
    result = subprocess.run([str(binary), *arguments], capture_output=True,
                            text=True, timeout=600)
    return {"code": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr}


def values(result):
    assert result["code"] == 0, result
    rows = [[float(value) for value in row.split()]
            for row in result["stdout"].splitlines() if row.strip()]
    assert rows and all(len(row) == 6 and all(math.isfinite(x) for x in row) for row in rows), result
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silex", type=Path, required=True)
    parser.add_argument("--jolt", type=Path, required=True)
    parser.add_argument("--mode", choices=["Debug", "Release"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"configuration": args.mode, "platform": platform.platform(),
              "architecture": platform.machine(), "primitives": {},
              "surfaces": {}, "contact_controls": {}, "invalid": {}, "binaries": {},
              "reference": "e77f175595e64cb44218cc9d9d56fc365ad0e36a",
              "reference_workers": 1, "steps": 12, "substeps": 8, "delta": "1/60"}
    try:
        for label, binary in [("silex", args.silex), ("jolt", args.jolt)]:
            report["binaries"][label] = {"path": str(binary.resolve()),
                "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        report["jolt_configuration"] = execute(args.jolt, ["--configuration"])
        for case in ["edge", "volume", "bend", "pressure", "tether"]:
            silex = execute(args.silex, [case])
            jolt = execute(args.jolt, [case])
            left, right = values(silex), values(jolt)
            assert len(left) == len(right)
            tolerance = 0.002 if case == "bend" else 0.0002
            error = max(abs(a-b) for first, second in zip(left, right)
                        for a, b in zip(first, second))
            report["primitives"][case] = {"silex": silex, "jolt": jolt,
                "max_absolute_error": error, "tolerance": tolerance}
            assert error <= tolerance, (case, error, tolerance)
        for case in ["cube", "cloth", "drape"]:
            result = execute(args.jolt, [case])
            assert result["code"] == 0, result
            metrics = {key: float(value) for key, value in
                       (part.split("=") for part in result["stdout"].split())}
            report["surfaces"][case] = {"jolt": result, "metrics": metrics}
            assert all(math.isfinite(value) for value in metrics.values())
            assert metrics["minimum"] >= 0.0299 and metrics["strain"] <= 1.2
            assert metrics["penetration"] <= 0.0001
            if case == "cube":
                assert 0.9 < metrics["volume"] < 1.1
            else:
                assert metrics["minimum"] < 1.9
        for case in ["convex-contact", "triangle-contact", "mesh-contact",
                     "front-sweep", "back-sweep"]:
            result = execute(args.jolt, [case])
            rows = values(result)
            report["contact_controls"][case] = result
            if case == "convex-contact":
                assert abs(rows[0][0]-0.53) < 0.0002
            elif case.endswith("contact"):
                assert abs(rows[0][1]-0.03) < 0.0002
            elif case == "back-sweep":
                assert rows[0][1] > 0.99
            else:
                # This isolated one-vertex/one-substep reference crosses the
                # triangle. The Silex surface corpus requires explicit CCD.
                assert rows[0][1] < 0.0
                report["reference_front_sweep_limit"] = True
        for case in ["index", "mass", "triangle", "volume", "pressure",
                     "radius", "owner", "pose", "anchor", "stale"]:
            result = execute(args.silex, ["invalid-"+case])
            report["invalid"][case] = result
            assert result["code"] > 0 and "GFX.Physics" in (
                result["stdout"]+result["stderr"]), (case, result)
        first = execute(args.silex, [])
        second = execute(args.silex, [])
        report["consumer"] = [first, second]
        assert first["code"] == second["code"] == 0, report["consumer"]
        assert "Soft body qualification passed" in first["stdout"]
        assert first["stdout"] == second["stdout"], "repeated observations differ"
        report["passed"] = True
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(f"{args.mode}: five Jolt constraints, ten invalid inputs and repeated public consumer passed")


if __name__ == "__main__":
    main()
