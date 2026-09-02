#!/bin/sh
set -eu

legacy_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
legacy_benchmark_repo=$(CDPATH= cd -- "$legacy_script_dir/../.." && pwd)
legacy_candidate_root=$(CDPATH= cd -- "$legacy_benchmark_repo/.." && pwd)
legacy_workspace_root=$(CDPATH= cd -- "$legacy_candidate_root/../../../.." && pwd)
legacy_results=${1:-"$legacy_script_dir/Baselines/$(date +%Y-%m-%d-%H%M%S)-legacy-regression"}
legacy_run_root=$(mktemp -d /private/tmp/silex-canvas-legacy.XXXXXX)
legacy_silex=${SILEX_BIN:-"$legacy_workspace_root/Silex/Toolchain/zig-out/bin/silex"}

legacy_canvas_baseline=9115713dbad490eef927fa4d553d4aa2599e7bcd
legacy_scene2d_baseline=9d8098dd65770f64ec561c3e4dd1419836015669
legacy_ui_baseline=6b990ac700840255afbbd38d7107054d9e9ee7b2
legacy_rendering_baseline=f77863b4a6135b0ef634d0a6d7a459fda3c0c342

trap 'rm -rf "$legacy_run_root"' EXIT HUP INT TERM

mkdir -p "$legacy_results" "$legacy_run_root/baseline/Packages" \
    "$legacy_run_root/baseline/Workspace/Sources" \
    "$legacy_run_root/candidate/Workspace/Sources" \
    "$legacy_run_root/bin"

extract_package() {
    legacy_name=$1
    legacy_commit=$2
    legacy_source="$legacy_candidate_root/Packages/$legacy_name"
    legacy_destination="$legacy_run_root/baseline/Packages/$legacy_name"
    mkdir -p "$legacy_destination"
    git -C "$legacy_source" archive "$legacy_commit" | tar -x -C "$legacy_destination"
}

extract_package GFX.Canvas "$legacy_canvas_baseline"
extract_package GFX.Scene2D "$legacy_scene2d_baseline"
extract_package GFX.UI "$legacy_ui_baseline"
extract_package GFX.Rendering "$legacy_rendering_baseline"

cp "$legacy_benchmark_repo/Package.json" "$legacy_run_root/baseline/Workspace/Package.json"
cp "$legacy_benchmark_repo/Package.json" "$legacy_run_root/candidate/Workspace/Package.json"
for legacy_workspace in baseline candidate; do
    sed 's/^test "compile a dense retained drawing" {/func main() {/' \
        "$legacy_benchmark_repo/Sources/RetainedCanvasGeometry.sx" \
        >"$legacy_run_root/$legacy_workspace/Workspace/Sources/RetainedCanvasGeometry.sx"
    sed 's/^test "update animated Canvas geometry in retained mesh storage" {/func main() {/' \
        "$legacy_benchmark_repo/Sources/AnimatingCanvasGeometry.sx" \
        >"$legacy_run_root/$legacy_workspace/Workspace/Sources/AnimatingCanvasGeometry.sx"
    cp "$legacy_benchmark_repo/Sources/UpdatingTextLayers2D.sx" \
        "$legacy_run_root/$legacy_workspace/Workspace/Sources/UpdatingTextLayers2D.sx"
    cp "$legacy_benchmark_repo/Sources/RetainedUIInteraction.sx" \
        "$legacy_run_root/$legacy_workspace/Workspace/Sources/RetainedUIInteraction.sx"
done

link_candidate_packages() {
    legacy_workspace=$1
    for legacy_name in GFX GFX.Application GFX.Assets GFX.Canvas GFX.ECS GFX.Font \
        GFX.GPU GFX.Rendering GFX.Scene2D GFX.Scene3D GFX.UI GFX.Viewer
    do
        "$legacy_silex" link "$legacy_candidate_root/Packages/$legacy_name" \
            --workspace "$legacy_workspace"
    done
}

link_candidate_packages "$legacy_run_root/candidate/Workspace"
link_candidate_packages "$legacy_run_root/baseline/Workspace"
for legacy_name in GFX.Canvas GFX.Scene2D GFX.UI GFX.Rendering; do
    "$legacy_silex" link "$legacy_run_root/baseline/Packages/$legacy_name" \
        --workspace "$legacy_run_root/baseline/Workspace"
done

{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -p)"
    echo "gpu=$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Chipset Model:/{print $2; exit}')"
    echo "backend=Metal"
    echo "mode=release"
    echo "processes_per_version=7"
    echo "order=alternating"
    echo "voluntary_gpu_competitors=none"
    echo "benchmark_commit=$(git -C "$legacy_benchmark_repo" rev-parse HEAD)"
    echo "canvas_baseline=$legacy_canvas_baseline"
    echo "canvas_candidate=$(git -C "$legacy_candidate_root/Packages/GFX.Canvas" rev-parse HEAD)"
    echo "scene2d_baseline=$legacy_scene2d_baseline"
    echo "scene2d_candidate=$(git -C "$legacy_candidate_root/Packages/GFX.Scene2D" rev-parse HEAD)"
    echo "ui_baseline=$legacy_ui_baseline"
    echo "ui_candidate=$(git -C "$legacy_candidate_root/Packages/GFX.UI" rev-parse HEAD)"
    echo "rendering_baseline=$legacy_rendering_baseline"
    echo "rendering_candidate=$(git -C "$legacy_candidate_root/Packages/GFX.Rendering" rev-parse HEAD)"
} >"$legacy_results/metadata.txt"

(
    cd "$legacy_workspace_root"
    for legacy_version in baseline candidate; do
        for legacy_case in RetainedCanvasGeometry AnimatingCanvasGeometry UpdatingTextLayers2D RetainedUIInteraction; do
            "$legacy_silex" compile \
                "$legacy_run_root/$legacy_version/Workspace/Sources/$legacy_case.sx" \
                --release --output "$legacy_run_root/bin/$legacy_version-$legacy_case"
        done
    done
) >"$legacy_results/build.log" 2>&1

for legacy_case in RetainedCanvasGeometry AnimatingCanvasGeometry UpdatingTextLayers2D RetainedUIInteraction; do
    "$legacy_run_root/bin/baseline-$legacy_case" >"$legacy_results/$legacy_case-baseline-warmup.log" 2>&1
    "$legacy_run_root/bin/candidate-$legacy_case" >"$legacy_results/$legacy_case-candidate-warmup.log" 2>&1
done

run_measurement() {
    legacy_case=$1
    legacy_version=$2
    legacy_repetition=$3
    echo "[$legacy_case] $legacy_version process $legacy_repetition/7"
    /usr/bin/time -l "$legacy_run_root/bin/$legacy_version-$legacy_case" \
        >"$legacy_results/$legacy_case-$legacy_version-$legacy_repetition.log" \
        2>"$legacy_results/$legacy_case-$legacy_version-$legacy_repetition.time"
}

legacy_repetition=1
while [ "$legacy_repetition" -le 7 ]; do
    for legacy_case in RetainedCanvasGeometry AnimatingCanvasGeometry UpdatingTextLayers2D RetainedUIInteraction; do
        if [ $((legacy_repetition % 2)) -eq 1 ]; then
            run_measurement "$legacy_case" baseline "$legacy_repetition"
            run_measurement "$legacy_case" candidate "$legacy_repetition"
        else
            run_measurement "$legacy_case" candidate "$legacy_repetition"
            run_measurement "$legacy_case" baseline "$legacy_repetition"
        fi
    done
    legacy_repetition=$((legacy_repetition + 1))
done

python3 "$legacy_script_dir/SummarizeLegacy.py" "$legacy_results"
echo "results: $legacy_results"
