#!/bin/sh
set -eu

effects_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
effects_benchmark_repo=$(CDPATH= cd -- "$effects_script_dir/../.." && pwd)
effects_candidate_root=$(CDPATH= cd -- "$effects_benchmark_repo/.." && pwd)
effects_workspace_root=$(CDPATH= cd -- "$effects_candidate_root/../../../.." && pwd)
effects_results=${1:-"$effects_script_dir/Baselines/$(date +%Y-%m-%d-%H%M%S)-macos-arm64"}
effects_run_root=$(mktemp -d /private/tmp/silex-canvas-effects-2d.XXXXXX)
effects_binary="$effects_run_root/canvas-effects-2d"
effects_silex=${SILEX_BIN:-"$effects_workspace_root/Silex/Toolchain/zig-out/bin/silex"}

trap 'rm -rf "$effects_run_root"' EXIT HUP INT TERM

effects_benchmark_status=$(git -C "$effects_benchmark_repo" status --porcelain)
effects_canvas_status=$(git -C "$effects_candidate_root/Packages/GFX.Canvas" status --porcelain)
effects_scene2d_status=$(git -C "$effects_candidate_root/Packages/GFX.Scene2D" status --porcelain)
if [ -n "$effects_benchmark_status" ] || [ -n "$effects_canvas_status" ] || \
    [ -n "$effects_scene2d_status" ]; then
    echo "CanvasEffects2D requires clean benchmark, Canvas, and Scene2D repositories" >&2
    exit 1
fi

mkdir -p "$effects_results"
effects_cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p)
effects_gpu=$(system_profiler SPDisplaysDataType 2>/dev/null | \
    awk -F': ' '/Chipset Model:/{print $2; exit}')
if [ -z "$effects_gpu" ]; then effects_gpu="unavailable"; fi
{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "cpu=$effects_cpu"
    echo "gpu=$effects_gpu"
    echo "backend=Metal"
    echo "silex=$($effects_silex version)"
    echo "mode=release"
    echo "processes_per_case=7"
    echo "warmup_frames=120"
    echo "measured_frames=600"
    echo "target=1920x1080"
    echo "display_density=1"
    echo "seed=12648430"
    echo "vsync=false"
    echo "presentation=false"
    echo "voluntary_gpu_competitors=none"
    echo "gpu_timestamp=unavailable"
    echo "benchmark_commit=$(git -C "$effects_benchmark_repo" rev-parse HEAD)"
    echo "canvas_commit=$(git -C "$effects_candidate_root/Packages/GFX.Canvas" rev-parse HEAD)"
    echo "scene2d_commit=$(git -C "$effects_candidate_root/Packages/GFX.Scene2D" rev-parse HEAD)"
} >"$effects_results/metadata.txt"

(
    cd "$effects_workspace_root"
    "$effects_silex" compile \
        ".specs/Canvas-Effects-And-Materials/Worktrees/spec-gfx-canvas-effects-07/Silex-Benchmarks/Sources/CanvasEffects2D/Main.sx" \
        --release --output "$effects_binary"
) >"$effects_results/build.log" 2>&1

effects_repetition=1
while [ "$effects_repetition" -le 7 ]; do
    for effects_case in analytic-static analytic-transform filtered-static filtered-dynamic fullscreen
    do
        echo "[$effects_case] process $effects_repetition/7"
        /usr/bin/time -l "$effects_binary" "$effects_case" \
            >"$effects_results/$effects_case-$effects_repetition.log" \
            2>"$effects_results/$effects_case-$effects_repetition.time"
    done
    effects_repetition=$((effects_repetition + 1))
done

python3 "$effects_script_dir/Summarize.py" "$effects_results"
echo "results: $effects_results"
