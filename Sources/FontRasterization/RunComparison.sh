#!/bin/sh
set -eu

font_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
font_benchmark_repo=$(CDPATH= cd -- "$font_script_dir/../.." && pwd)
font_candidate_root=$(CDPATH= cd -- "$font_benchmark_repo/.." && pwd)
font_results=${1:-"$font_script_dir/Results/$(date +%Y-%m-%d-%H%M%S)"}
font_run_root=$(mktemp -d /private/tmp/silex-font-raster.XXXXXX)
font_baseline_workspace="$font_run_root/baseline"
font_candidate_workspace="$font_run_root/candidate"
font_baseline_binary="$font_run_root/font-raster-baseline"
font_candidate_binary="$font_run_root/font-raster-candidate"
font_direct_binary="$font_run_root/font-raster-direct"
font_baseline_canvas="$font_run_root/GFX.Canvas-baseline"
font_candidate_canvas="$font_candidate_root/Packages/GFX.Canvas"
font_candidate_font="$font_candidate_root/Packages/GFX.Font"
font_common_gfx="$font_candidate_root/Packages/GFX"
font_common_assets="$font_candidate_root/Packages/GFX.Assets"
font_common_std="$font_candidate_root/Packages/STD"
font_toolchain="$font_candidate_root/Silex"
font_silex=${SILEX_BIN:-"$font_toolchain/Toolchain/zig-out/bin/silex"}
font_baseline_commit=4975f3f8db0628c9bb5740b6f2b77b676599072a
font_candidate_canvas_commit=8c5e3178c222c7bd087dc2d5766a79bb438335ed
font_candidate_font_commit=a1207ecd14cadfae438b4b7c8a4644610a0b30b6
font_toolchain_commit=a7abd029060e6ebaa8b78d4c0426a8f3bf8e2b64

trap 'rm -rf "$font_run_root"' EXIT HUP INT TERM

require_commit() {
    font_repository=$1
    font_expected=$2
    font_actual=$(git -C "$font_repository" rev-parse HEAD)
    if [ "$font_actual" != "$font_expected" ]; then
        echo "unexpected commit for $font_repository: $font_actual (expected $font_expected)" >&2
        exit 1
    fi
    if [ -n "$(git -C "$font_repository" status --short)" ]; then
        echo "benchmark owner is dirty: $font_repository" >&2
        exit 1
    fi
}

prepare_workspace() {
    font_target=$1
    font_canvas=$2
    mkdir -p "$font_target/Sources"
    mkdir -p "$font_target/Sources/FontRasterization"
    mkdir -p "$font_run_root/Packages/GFX.Font/Assets/Fonts"
    cp "$font_script_dir/BenchmarkPackage.json" "$font_target/Package.json"
    cp "$font_script_dir/Main.sx" "$font_target/Sources/Main.sx"
    cp "$font_script_dir/Direct.sx" "$font_target/Sources/FontRasterization/Direct.sx"
    cp "$font_candidate_font/Assets/Fonts/NotoSansMono-Regular.ttf" \
        "$font_run_root/Packages/GFX.Font/Assets/Fonts/NotoSansMono-Regular.ttf"
    (
        cd "$font_target"
        "$font_silex" link "$font_common_gfx" --workspace "$font_target"
        "$font_silex" link "$font_common_assets" --workspace "$font_target"
        "$font_silex" link "$font_canvas" --workspace "$font_target"
        "$font_silex" link "$font_candidate_font" --workspace "$font_target"
        "$font_silex" link "$font_common_std" --workspace "$font_target"
    )
}

run_one() {
    font_engine=$1
    font_repetition=$2
    font_binary=$3
    font_case=$4
    echo "[$font_engine/$font_case] repetition $font_repetition/7"
    /usr/bin/time -l "$font_binary" "$font_case" \
        >"$font_results/$font_engine-$font_case-$font_repetition.log" \
        2>"$font_results/$font_engine-$font_case-$font_repetition.time"
}

require_commit "$font_candidate_canvas" "$font_candidate_canvas_commit"
require_commit "$font_candidate_font" "$font_candidate_font_commit"
require_commit "$font_toolchain" "$font_toolchain_commit"

if ! git -C "$font_candidate_canvas" cat-file -e "$font_baseline_commit^{commit}"; then
    echo "missing baseline commit in $font_candidate_canvas: $font_baseline_commit" >&2
    exit 1
fi
mkdir -p "$font_baseline_canvas"
git -C "$font_candidate_canvas" archive "$font_baseline_commit" |
    tar -x -C "$font_baseline_canvas"
if [ -d "$font_candidate_canvas/Boundary" ]; then
    mkdir -p "$font_baseline_canvas/Boundary"
    cp -R "$font_candidate_canvas/Boundary/." "$font_baseline_canvas/Boundary/"
fi

font_baseline_mono=$(shasum -a 256 "$font_baseline_canvas/Assets/Fonts/NotoSansMono-Regular.ttf" | cut -d ' ' -f 1)
font_candidate_mono=$(shasum -a 256 "$font_candidate_font/Assets/Fonts/NotoSansMono-Regular.ttf" | cut -d ' ' -f 1)
font_baseline_default=$(shasum -a 256 "$font_baseline_canvas/Assets/Fonts/NotoSans.ttf" | cut -d ' ' -f 1)
font_candidate_default=$(shasum -a 256 "$font_candidate_font/Assets/Fonts/NotoSans.ttf" | cut -d ' ' -f 1)
if [ "$font_baseline_mono" != "$font_candidate_mono" ] || [ "$font_baseline_default" != "$font_candidate_default" ]; then
    echo "baseline and candidate font assets differ" >&2
    exit 1
fi

mkdir -p "$font_results"
{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "silex=$($font_silex --version)"
    echo "compiler_commit=$font_toolchain_commit"
    echo "compiler_binary=$font_silex"
    echo "mode=release"
    echo "density=2.0"
    echo "repetitions=7"
    echo "baseline_canvas=$font_baseline_commit"
    echo "candidate_canvas=$font_candidate_canvas_commit"
    echo "candidate_font=$font_candidate_font_commit"
    echo "common_gfx=$(git -C "$font_common_gfx" rev-parse HEAD)"
    echo "common_assets=$(git -C "$font_common_assets" rev-parse HEAD)"
    echo "common_std=$(git -C "$font_common_std" rev-parse HEAD)"
    echo "monospace_sha256=$font_candidate_mono"
    echo "default_sha256=$font_candidate_default"
} >"$font_results/metadata.txt"

prepare_workspace "$font_baseline_workspace" "$font_baseline_canvas" \
    >"$font_results/build-baseline.log" 2>&1
prepare_workspace "$font_candidate_workspace" "$font_candidate_canvas" \
    >"$font_results/build-candidate.log" 2>&1

(
    cd "$font_baseline_workspace"
    "$font_silex" compile Sources/Main.sx --release --nocache --output "$font_baseline_binary"
) >>"$font_results/build-baseline.log" 2>&1
(
    cd "$font_candidate_workspace"
    "$font_silex" compile Sources/Main.sx --release --nocache --output "$font_candidate_binary"
) >>"$font_results/build-candidate.log" 2>&1
(
    cd "$font_candidate_workspace"
    "$font_silex" compile Sources/FontRasterization/Direct.sx --release --nocache \
        --output "$font_direct_binary"
) >>"$font_results/build-candidate.log" 2>&1

for font_case in \
    cold_first \
    retained_static \
    retained_static_soak \
    forced_static_raster \
    dynamic_short \
    multi_script \
    pressure_first \
    pressure_revisit
do
    font_repetition=1
    while [ "$font_repetition" -le 7 ]; do
        if [ $((font_repetition % 2)) -eq 1 ]; then
            run_one candidate "$font_repetition" "$font_candidate_binary" "$font_case"
            run_one baseline "$font_repetition" "$font_baseline_binary" "$font_case"
        else
            run_one baseline "$font_repetition" "$font_baseline_binary" "$font_case"
            run_one candidate "$font_repetition" "$font_candidate_binary" "$font_case"
        fi
        font_repetition=$((font_repetition + 1))
    done
done

font_repetition=1
while [ "$font_repetition" -le 7 ]; do
    echo "[candidate/direct] repetition $font_repetition/7"
    /usr/bin/time -l "$font_direct_binary" \
        >"$font_results/direct-$font_repetition.log" \
        2>"$font_results/direct-$font_repetition.time"
    font_repetition=$((font_repetition + 1))
done

leaks --atExit -- "$font_candidate_binary" pressure_revisit \
    >"$font_results/leaks-pressure-revisit.log" 2>&1

python3 "$font_script_dir/Summarize.py" "$font_results"
echo "results: $font_results"
