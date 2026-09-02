#!/bin/sh
set -eu

batch_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
batch_benchmark_repo=$(CDPATH= cd -- "$batch_script_dir/../.." && pwd)
batch_candidate_root=$(CDPATH= cd -- "$batch_benchmark_repo/.." && pwd)
batch_workspace_root=$(CDPATH= cd -- "$batch_candidate_root/../../../.." && pwd)
batch_results=${1:-"$batch_script_dir/Results/$(date +%Y-%m-%d-%H%M%S)"}
batch_run_root=$(mktemp -d /private/tmp/silex-canvas-filter-batches.XXXXXX)
batch_binary="$batch_run_root/canvas-filter-batches"
batch_silex=${SILEX_BIN:-"$batch_workspace_root/Silex/Toolchain/zig-out/bin/silex"}

trap 'rm -rf "$batch_run_root"' EXIT HUP INT TERM

mkdir -p "$batch_results"
{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "silex=$($batch_silex --version)"
    echo "mode=release"
    echo "processes_per_case=7"
    echo "placements=16"
    echo "benchmark_commit=$(git -C "$batch_benchmark_repo" rev-parse HEAD)"
    echo "gpu_commit=$(git -C "$batch_candidate_root/Packages/GFX.GPU" rev-parse HEAD)"
    echo "canvas_commit=$(git -C "$batch_candidate_root/Packages/GFX.Canvas" rev-parse HEAD)"
    echo "scene2d_commit=$(git -C "$batch_candidate_root/Packages/GFX.Scene2D" rev-parse HEAD)"
} >"$batch_results/metadata.txt"

(
    cd "$batch_candidate_root"
    "$batch_silex" compile \
        Silex-Benchmarks/Sources/CanvasFilterBatches2D/Main.sx \
        --release --output "$batch_binary"
) >"$batch_results/build.log" 2>&1

for batch_case in unfiltered shared fragmented
do
    batch_repetition=1
    while [ "$batch_repetition" -le 7 ]; do
        echo "[$batch_case] process $batch_repetition/7"
        /usr/bin/time -l "$batch_binary" "$batch_case" \
            >"$batch_results/$batch_case-$batch_repetition.log" \
            2>"$batch_results/$batch_case-$batch_repetition.time"
        batch_repetition=$((batch_repetition + 1))
    done
done

python3 "$batch_script_dir/Summarize.py" "$batch_results"
echo "results: $batch_results"
