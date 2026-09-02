#!/bin/sh
set -eu

filtered_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
filtered_benchmark_repo=$(CDPATH= cd -- "$filtered_script_dir/../.." && pwd)
filtered_candidate_root=$(CDPATH= cd -- "$filtered_benchmark_repo/.." && pwd)
filtered_workspace_root=$(CDPATH= cd -- "$filtered_candidate_root/../../../.." && pwd)
filtered_results=${1:-"$filtered_script_dir/Results/$(date +%Y-%m-%d-%H%M%S)"}
filtered_run_root=$(mktemp -d /private/tmp/silex-filtered-canvas.XXXXXX)
filtered_binary="$filtered_run_root/filtered-canvas-surfaces"
filtered_silex=${SILEX_BIN:-"$filtered_workspace_root/Silex/Toolchain/zig-out/bin/silex"}

trap 'rm -rf "$filtered_run_root"' EXIT HUP INT TERM

mkdir -p "$filtered_results"
{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "silex=$($filtered_silex --version)"
    echo "mode=release"
    echo "processes_per_case=7"
    echo "benchmark_commit=$(git -C "$filtered_benchmark_repo" rev-parse HEAD)"
    echo "canvas_commit=$(git -C "$filtered_candidate_root/Packages/GFX.Canvas" rev-parse HEAD)"
    echo "scene2d_commit=$(git -C "$filtered_candidate_root/Packages/GFX.Scene2D" rev-parse HEAD)"
} >"$filtered_results/metadata.txt"

(
    cd "$filtered_candidate_root"
    "$filtered_silex" compile \
        Silex-Benchmarks/Sources/FilteredCanvasSurfaces/Main.sx \
        --release --output "$filtered_binary"
) >"$filtered_results/build.log" 2>&1

for filtered_case in static transform_only content_mutation fullscreen
do
    filtered_repetition=1
    while [ "$filtered_repetition" -le 7 ]; do
        echo "[$filtered_case] process $filtered_repetition/7"
        /usr/bin/time -l "$filtered_binary" "$filtered_case" \
            >"$filtered_results/$filtered_case-$filtered_repetition.log" \
            2>"$filtered_results/$filtered_case-$filtered_repetition.time"
        filtered_repetition=$((filtered_repetition + 1))
    done
done

python3 "$filtered_script_dir/Summarize.py" "$filtered_results"
echo "results: $filtered_results"
