#!/bin/sh
# One executable entry point; Python 3 provides the standard-library checks and statistics.
boids_program=$(cat <<'BOIDS_PYTHON'
"""Sealed three-way Boids comparison for a Spec workspace."""
import argparse
from datetime import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import subprocess
import statistics
import sys


POLICY = {'version': 'boids-stationarity-v2', 'count': 4000, 'frames': 480, 'warmups': 6, 'runs': 12, 'max_mad_fraction': 0.01, 'max_range_fraction': 0.04, 'max_drift_fraction': 0.01, 'max_half_shift_fraction': 0.01}

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


LABELS = ("Silex/Natif", "Silex/LLVM", "C++ architectural")
PREFIXES = ("SILEX_GFX_BOIDS", "SILEX_GFX_BOIDS", "CPP_ARCHITECTURAL_BOIDS")
# All six permutations balance positions and directed transitions.
ORDERS = tuple(itertools.permutations(range(3)))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(config, root):
    if config["version"] != "boids-threeway-diagnostic-v1":
        raise ValueError("unsupported three-way configuration")
    if tuple(item["label"] for item in config["executables"]) != LABELS:
        raise ValueError("configuration must contain the three distinct witnesses")
    for relative, expected in config["files"].items():
        if digest(root / relative) != expected:
            raise ValueError(f"input changed: {relative}; prepare a new comparison")
    for relative, expected in config["repositories"].items():
        repo = root / relative
        head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
        if head != expected or dirty:
            raise ValueError(f"repository changed: {relative}; prepare a new comparison")
    for item in config["executables"]:
        if item["path"] not in config["files"]:
            raise ValueError("unsealed executable")
        if item["expected_exit"] != 0:
            raise ValueError("unexpected exit-code policy")


def observe(index, result):
    expected_exit = 0
    if result.returncode != expected_exit:
        raise ValueError(f"{LABELS[index]} exited {result.returncode}, expected {expected_exit}")
    if result.stderr:
        raise ValueError(f"{LABELS[index]} emitted stderr")
    lines = [line for line in result.stdout.splitlines() if line.startswith(PREFIXES[index] + " ")]
    if len(lines) != 1:
        raise ValueError(f"{LABELS[index]} must emit exactly one state witness")
    fields = lines[0].split()[1:]
    data = dict(field.split("=", 1) for field in fields)
    if len(data) != len(fields):
        raise ValueError("duplicate state field")
    signature = semantic_signature(data)
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



def platform_name():
    system = {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system(), platform.system().lower())
    machine = platform.machine().lower()
    architecture = {"aarch64": "arm64", "amd64": "x64", "x86_64": "x64"}.get(machine, machine)
    return f"{system}-{architecture}"


def render_report(report):
    """One human-readable capture; application state stays in validation only."""
    status = {
        "incomplete": "En cours — résultats partiels, aucune comparaison validée.",
        "invalid": "Capture invalide — aucune comparaison validée.",
        "interrupted": "Capture interrompue — aucune comparaison validée.",
        "diagnostic-complete": "Capture complète — séries stables.",
        "diagnostic-nonstationary": "Capture complète — séries instables ; écarts descriptifs à confirmer.",
    }
    lines = ["# Boids — comparaison FPS", "", report["date"], "",
             f"4 000 boids × 480 frames · {report['warmups']} échauffements + {report['runs']} mesures par variante · Release",
             "", status[report["verdict"]], ""]
    if report.get("note"):
        lines += [report["note"], ""]
    if report["verdict"] in ("diagnostic-complete", "diagnostic-nonstationary"):
        means = {}
        lines += ["| Variante | FPS moyens | FPS min | FPS max | Écart-type FPS |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for label in LABELS:
            values = report["series"][label]["values"]
            means[label] = statistics.mean(values)
            lines.append(f"| {label} | {means[label]:.3f} | {min(values):.3f} | {max(values):.3f} | {statistics.pstdev(values):.3f} |")
        lines += ["", "Moyenne arithmétique des FPS des passages mesurés, hors échauffements.",
                  "Min, max et écart-type décrivent ces passages, pas les frames individuelles.",
                  "", "## Écarts entre variantes", "",
                  "| Variante | Référence | Écart FPS moyens | Écart % |",
                  "| --- | --- | ---: | ---: |"]
        for label, reference in ((LABELS[1], LABELS[0]), (LABELS[0], LABELS[2]), (LABELS[1], LABELS[2])):
            delta = means[label] - means[reference]
            lines.append(f"| {label} | {reference} | {delta:+.3f} | {100 * delta / means[reference]:+.2f} % |")
        lines += ["", "Écart % = (moyenne de la variante / moyenne de la référence − 1) × 100.", ""]
    if report.get("failure"):
        lines += ["## Erreur", "", *('    ' + line for line in report['failure'].splitlines()), ""]
    lines += ["<details>", "<summary>FPS de chaque passage</summary>", "",
              "| Phase | Tour | Ordre | Silex/Natif | Silex/LLVM | C++ architectural |",
              "| --- | ---: | --- | ---: | ---: | ---: |"]
    rounds = sorted({event['round'] for event in report['events']})
    short = dict(zip(LABELS, ("Natif", "LLVM", "C++")))
    for number in rounds:
        events = [e for e in report['events'] if e['round'] == number]
        phase = "Échauffement" if events[0]['phase'] == 'warmup' else "Mesure"
        order = " → ".join(short[e['label']] for e in events)
        cells = []
        for label in LABELS:
            event = next((e for e in events if e['label'] == label), {})
            cells.append(str(event['fps']) if 'fps' in event else '—')
        lines.append(f"| {phase} | {number} | {order} | " + " | ".join(cells) + " |")
    lines += ["", "</details>", "", "<details>", "<summary>Contexte de la capture</summary>", "",
              f"Hôte : {report['host']}", "", f"Configuration SHA-256 : `{report['config_sha256']}`", ""]
    config = report['configuration']
    for item in config['executables']:
        if item['label'] in LABELS and item['path'] in config.get('files', {}):
            lines.append(f"- {item['label']} : `{config['files'][item['path']]}`")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def save_report(handle, report):
    handle.seek(0)
    handle.write(render_report(report))
    handle.truncate()
    handle.flush()


def main():
    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=__doc__)
    parser.add_argument("--config", type=Path, help="prepared configuration (default: workspace Evaluations/boids-comparison/Configuration.json)")
    parser.add_argument("--wait", action="store_true", help="wait for Return before any benchmark process")
    parser.add_argument("--prepare-only", action="store_true", help="verify the prepared binaries without running them")
    parser.add_argument("--warmups", type=int, default=POLICY["warmups"], help="warm-up rounds per executable (multiple of six)")
    parser.add_argument("--runs", type=int, default=POLICY["runs"], help="measured rounds per executable (multiple of six, at least six)")
    parser.add_argument("--output", type=Path, help="single Markdown report path")
    args = parser.parse_args()
    if args.warmups < 0 or args.warmups % 6 or args.runs < 6 or args.runs % 6:
        parser.error("warmups must be a nonnegative multiple of six; runs must be a multiple of six >= 6")
    source = Path(__file__).resolve().parent
    root = source.parents[2]
    args.config = args.config or root / "Evaluations/boids-comparison/Configuration.json"
    config = json.loads(args.config.read_text())
    config_hash = digest(args.config)
    verify(config, root)
    print("Comparaison Boids : 3 exécutables préparés et vérifiés.", flush=True)
    for item in config["executables"]:
        print(f"  {item['label']}: {item['path']}", flush=True)
    print(f"4000 boids × 480 frames ; {args.warmups} échauffements + {args.runs} mesures par variante.", flush=True)
    print("Les trois variantes doivent terminer avec le code 0 ; comparaison diagnostique.", flush=True)
    if args.prepare_only:
        return 0
    if args.wait:
        input("\nPréparation terminée. Laisse l’ordinateur au calme, puis appuie sur Entrée : ")
    # Do not let a rebuild or source change during the user's pause go unnoticed.
    if digest(args.config) != config_hash:
        raise ValueError("configuration changed during the pause")
    verify(config, root)
    output = args.output or source / "Baselines" / (datetime.now().strftime("%Y-%m-%d-%H%M%S-%f") + f"-{platform_name()}.md")
    output = output.resolve()
    if output.exists():
        raise ValueError("refusing to overwrite an existing capture")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(protocol="boids-threeway-diagnostic-v1", configuration=config,
                  config_sha256=config_hash, host=platform.platform(), date=datetime.now().astimezone().isoformat(timespec="seconds"),
                  warmups=args.warmups, runs=args.runs, order=ORDERS,
                  verdict="incomplete", events=[], series={})
    reference = None
    native_states = {}
    llvm_states = {}
    with output.open("x", encoding="utf-8") as handle:
        try:
            save_report(handle, report)
            for round_index in range(args.warmups + args.runs):
                phase = "warmup" if round_index < args.warmups else "sample"
                for position, index in enumerate(ORDERS[round_index % len(ORDERS)], 1):
                    item = config["executables"][index]
                    label = item["label"]
                    print(f"\n{phase} {round_index + 1}, position {position} — {label}", flush=True)
                    event = dict(phase=phase, round=round_index + 1, position=position, label=label)
                    argv = [str(root / item["path"]), "4000", "480"]
                    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
                    report["events"].append(event)
                    try:
                        data, signature, fps = observe(index, result)
                    except (ValueError, KeyError) as error:
                        detail = result.stderr.strip()
                        raise ValueError(str(error) + ("\n" + detail if detail else "")) from error
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
                    print(f"{fps:.3f} FPS", flush=True)
                    save_report(handle, report)
            if digest(args.config) != config_hash:
                raise ValueError("configuration changed during the capture")
            verify(config, root)
            for label in LABELS:
                values = [e["fps"] for e in report["events"] if e["label"] == label and e["phase"] == "sample"]
                report["series"][label] = summarize(values)
            report["stationary"] = all(series["stationary"] for series in report["series"].values())
            report["verdict"] = "diagnostic-complete" if report["stationary"] else "diagnostic-nonstationary"
            # Console and saved report present the same FPS summary and differences.
            print("\n" + render_report(report).split("<details>", 1)[0], flush=True)
            return 0 if report["stationary"] else 2
        except (ValueError, KeyError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
            report["verdict"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "invalid"
            report["failure"] = str(error)
            raise
        finally:
            save_report(handle, report)
            print(f"\nRapport : {output}", flush=True)


if __name__ == "__main__":
    __file__ = sys.argv.pop(1)
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, EOFError, subprocess.CalledProcessError) as error:
        sys.exit(f"comparison: {error}")
    except KeyboardInterrupt:
        sys.exit(130)
BOIDS_PYTHON
)
exec python3 -c "$boids_program" "$0" "$@"
