#!/bin/sh
set -eu

tensor_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tensor_benchmark_repo=$(CDPATH= cd -- "$tensor_script_dir/../.." && pwd)
tensor_candidate_root=$(CDPATH= cd -- "$tensor_benchmark_repo/.." && pwd)
tensor_results=${1:-"$tensor_script_dir/Baselines/$(date +%Y-%m-%d-%H%M%S)-neural"}
tensor_run_root=$(mktemp -d /private/tmp/silex-tensor-neural.XXXXXX)
tensor_debug_binary="$tensor_run_root/tensor-neural-debug"
tensor_release_binary="$tensor_run_root/tensor-neural-release"
tensor_silex=${SILEX_BIN:-"$tensor_candidate_root/Silex/Toolchain/zig-out/bin/silex"}
tensor_processes=5

trap 'rm -rf "$tensor_run_root"' EXIT HUP INT TERM

if [ -n "$(git -C "$tensor_benchmark_repo" status --porcelain)" ]; then
    echo "Silex-Benchmarks must be clean before a neural campaign" >&2
    exit 1
fi

mkdir -p "$tensor_results"
tensor_os_version=$(sw_vers -productVersion)
tensor_os_build=$(sw_vers -buildVersion)
tensor_chip=$(system_profiler SPHardwareDataType | awk -F': ' '/Chip:/{print $2; exit}')
tensor_gpu=$(system_profiler SPDisplaysDataType | awk -F': ' '/Chipset Model:/{print $2; exit}')
tensor_memory=$(sysctl -n hw.memsize)
{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=macOS $tensor_os_version ($tensor_os_build)"
    echo "architecture=$(uname -m)"
    echo "cpu=$tensor_chip"
    echo "gpu=$tensor_gpu"
    echo "gpu_driver=Apple Metal supplied by macOS $tensor_os_build"
    echo "memory_bytes=$tensor_memory"
    echo "silex=$($tensor_silex --version)"
    echo "diagnostic_mode=debug"
    echo "measurement_mode=release"
    echo "processes_per_family=$tensor_processes"
    echo "families=mlp,cnn,rnn"
    echo "mlp_batches=4,16,64"
    echo "cnn_batches=1,4,16"
    echo "rnn_batches=4,16,64"
    echo "benchmark_commit=$(git -C "$tensor_benchmark_repo" rev-parse HEAD)"
    echo "silex_commit=$(git -C "$tensor_candidate_root/Silex" rev-parse HEAD)"
    echo "tensor_commit=$(git -C "$tensor_candidate_root/Packages/Tensor" rev-parse HEAD)"
    echo "gfx_gpu_commit=$(git -C "$tensor_candidate_root/Packages/GFX.GPU" rev-parse HEAD)"
    echo "gfx_commit=$(git -C "$tensor_candidate_root/Packages/GFX" rev-parse HEAD)"
    echo "std_commit=$(git -C "$tensor_candidate_root/Packages/STD" rev-parse HEAD)"
} >"$tensor_results/metadata.txt"

export ZIG_GLOBAL_CACHE_DIR="$tensor_candidate_root/.silex/zig-global"
(
    cd "$tensor_candidate_root"
    "$tensor_silex" compile \
        Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx \
        --debug --nocache --output "$tensor_debug_binary"
) >"$tensor_results/build-debug.log" 2>&1

/usr/bin/time -l "$tensor_debug_binary" --verify \
    >"$tensor_results/diagnostic-debug.log" \
    2>"$tensor_results/diagnostic-debug.time"

(
    cd "$tensor_candidate_root"
    "$tensor_silex" compile \
        Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx \
        --release --nocache --output "$tensor_release_binary"
) >"$tensor_results/build-release.log" 2>&1

for tensor_family in mlp cnn rnn
do
    tensor_repetition=1
    while [ "$tensor_repetition" -le "$tensor_processes" ]; do
        echo "[$tensor_family] process $tensor_repetition/$tensor_processes"
        /usr/bin/time -l "$tensor_release_binary" "--measure-$tensor_family" \
            >"$tensor_results/$tensor_family-$tensor_repetition.log" \
            2>"$tensor_results/$tensor_family-$tensor_repetition.time"
        tensor_repetition=$((tensor_repetition + 1))
    done
done

python3 "$tensor_script_dir/SummarizeNeural.py" "$tensor_results"
echo "results: $tensor_results"
