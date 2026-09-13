#!/usr/bin/env python3
"""Temporary, sealed four-way Boids comparison for a Spec workspace."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

import Protocol

LABELS = ("Silex/Natif", "Silex/LLVM", "C++ architectural", "C++ direct")
PREFIXES = ("SILEX_GFX_BOIDS", "SILEX_GFX_BOIDS", "CPP_ARCHITECTURAL_BOIDS", "CPP_DIRECT_BOIDS")
# Williams design: every position and every directed within-round transition
# occurs equally often in each block of four rounds.
ORDERS = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(config, root):
    if config["version"] != "boids-fourway-diagnostic-v1":
        raise ValueError("unsupported four-way configuration")
    if tuple(item["label"] for item in config["executables"]) != LABELS:
        raise ValueError("configuration must contain the four distinct witnesses")
    for relative, expected in config["files"].items():
        if digest(root / relative) != expected:
            raise ValueError(f"input changed: {relative}; prepare a new comparison")
    for relative, expected in config["repositories"].items():
        repo = root / relative
        head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
        if head != expected or dirty:
            raise ValueError(f"repository changed: {relative}; prepare a new comparison")
    for index, item in enumerate(config["executables"]):
        if item["path"] not in config["files"]:
            raise ValueError("unsealed executable")
        if item["expected_exit"] != (2 if index == 1 else 0):
            raise ValueError("unexpected exit-code policy")


def observe(index, result):
    expected_exit = 2 if index == 1 else 0
    if result.returncode != expected_exit:
        raise ValueError(f"{LABELS[index]} exited {result.returncode}, expected {expected_exit}")
    if result.stderr:
        raise ValueError(f"{LABELS[index]} emitted stderr; inspect the raw log")
    lines = [line for line in result.stdout.splitlines() if line.startswith(PREFIXES[index] + " ")]
    if len(lines) != 1:
        raise ValueError(f"{LABELS[index]} must emit exactly one state witness")
    fields = lines[0].split()[1:]
    data = dict(field.split("=", 1) for field in fields)
    if len(data) != len(fields):
        raise ValueError("duplicate state field")
    signature = Protocol.semantic_signature(data)
    fps = float(data["fps"])
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("invalid FPS")
    return data, signature, fps


def match(reference, observed):
    if reference[0] != observed[0] or any(
        abs(a - b) > 0.05 + max(abs(a), abs(b)) * 0.00002
        for a, b in zip(reference[1], observed[1])
    ):
        raise ValueError("display or deterministic state differs between witnesses")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--wait", action="store_true", help="wait for Return before any benchmark process")
    parser.add_argument("--prepare-only", action="store_true", help="verify the prepared binaries without running them")
    parser.add_argument("--warmups", type=int, default=4, help="warm-up rounds per executable (multiple of four)")
    parser.add_argument("--runs", type=int, default=12, help="measured rounds per executable (multiple of four, at least eight)")
    parser.add_argument("--output", type=Path, help="raw log path; JSON report is written beside it")
    args = parser.parse_args()
    if args.warmups < 0 or args.warmups % 4 or args.runs < 8 or args.runs % 4:
        parser.error("warmups must be a nonnegative multiple of four; runs must be a multiple of four >= 8")
    source = Path(__file__).resolve().parent
    root = source.parents[2]
    config = json.loads(args.config.read_text())
    config_hash = digest(args.config)
    verify(config, root)
    print("Comparaison temporaire : 4 exécutables préparés et vérifiés.", flush=True)
    for item in config["executables"]:
        print(f"  {item['label']}: {item['path']}", flush=True)
    print(f"4000 boids × 480 frames ; {args.warmups} échauffements + {args.runs} mesures par variante.", flush=True)
    print("LLVM : réserve de finalisation connue (code 2), résultats diagnostiques uniquement.", flush=True)
    if args.prepare_only:
        return 0
    if args.wait:
        input("\nPréparation terminée. Laisse l’ordinateur au calme, puis appuie sur Entrée : ")
    # Do not let a rebuild or source change during the user's pause go unnoticed.
    if digest(args.config) != config_hash:
        raise ValueError("configuration changed during the pause")
    verify(config, root)
    output = args.output or args.config.parent / "Results" / (datetime.now().strftime("%Y-%m-%d-%H%M%S-%f") + "-boids-fourway.log")
    output = output.resolve()
    report_path = Path(str(output) + ".json")
    if output.exists() or report_path.exists():
        raise ValueError("refusing to overwrite an existing capture")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(protocol="boids-fourway-diagnostic-v1", configuration=config,
                  config_sha256=config_hash, host=platform.platform(),
                  warmups=args.warmups, runs=args.runs, order=ORDERS,
                  verdict="incomplete", events=[], series={})
    reference = None
    native_states = {}
    llvm_states = {}
    try:
        with output.open("x") as log:
            log.write("# boids-fourway-diagnostic-v1\n")
            for round_index in range(args.warmups + args.runs):
                phase = "warmup" if round_index < args.warmups else "sample"
                # Restart at row zero after warm-up; both windows are balanced.
                for position, index in enumerate(ORDERS[round_index % 4], 1):
                    item = config["executables"][index]
                    label = item["label"]
                    print(f"\n{phase} {round_index + 1}, position {position} — {label}", flush=True)
                    event = dict(phase=phase, round=round_index + 1, position=position, label=label)
                    argv = [str(root / item["path"]), "4000", "480"]
                    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
                    event.update(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
                    report["events"].append(event)
                    log.write(json.dumps(event, ensure_ascii=False) + "\n")
                    log.flush()
                    data, signature, fps = observe(index, result)
                    if reference is None:
                        reference = signature
                    match(reference, signature)
                    state = {key: value for key, value in data.items() if key != "fps"}
                    if index == 0:
                        native_states[round_index] = state
                    elif index == 1:
                        llvm_states[round_index] = state
                    if round_index in native_states and round_index in llvm_states:
                        if native_states[round_index] != llvm_states[round_index]:
                            raise ValueError("Silex native/LLVM deterministic fields differ")
                    event["fps"] = fps
                    print(f"{fps:.3f} FPS — code {result.returncode}", flush=True)
                    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        verify(config, root)
        for label in LABELS:
            values = [event["fps"] for event in report["events"] if event["label"] == label and event["phase"] == "sample"]
            report["series"][label] = Protocol.summarize(values)
        report["stationary"] = all(series["stationary"] for series in report["series"].values())
        report["verdict"] = "diagnostic-finalization-pending"
        print("\nComparaison terminée — réserve de finalisation LLVM, aucun verdict final.", flush=True)
        for label, series in report["series"].items():
            print(f"{label}: médiane={series['median']:.3f} FPS, MAD={series['mad']:.3f}, dérive={series['drift_fraction']:.2%}")
            for failure in series["failures"]:
                print("  Instabilité : " + failure)
        return 2
    except (ValueError, KeyError, OSError, KeyboardInterrupt) as error:
        report["verdict"] = "invalid" if not isinstance(error, KeyboardInterrupt) else "interrupted"
        report["failure"] = str(error)
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"\nJournal : {output}\nRapport : {report_path}", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, EOFError, subprocess.CalledProcessError) as error:
        sys.exit(f"comparison: {error}")
    except KeyboardInterrupt:
        sys.exit(130)
