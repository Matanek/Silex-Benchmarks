#!/bin/sh
set -eu

tensor_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tensor_benchmark_repo=$(CDPATH= cd -- "$tensor_script_dir/../.." && pwd)
tensor_candidate_root=$(CDPATH= cd -- "$tensor_benchmark_repo/.." && pwd)
tensor_workspace_root=$(CDPATH= cd -- "$tensor_candidate_root/../../../.." && pwd)
tensor_results=${1:-"$tensor_script_dir/Baselines/$(date +%Y-%m-%d-%H%M%S)"}
tensor_run_root=$(mktemp -d /private/tmp/silex-tensor-benchmark.XXXXXX)
tensor_debug_binary="$tensor_run_root/tensor-debug"
tensor_release_binary="$tensor_run_root/tensor-release"
tensor_silex=${SILEX_BIN:-"$tensor_candidate_root/Silex/Toolchain/zig-out/bin/silex"}

trap 'rm -rf "$tensor_run_root"' EXIT HUP INT TERM

if [ -n "$(git -C "$tensor_benchmark_repo" status --porcelain)" ]; then
    echo "Silex-Benchmarks must be clean before a campaign" >&2
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
    echo "processes_per_group=7"
    echo "dtype_cardinality=65536"
    echo "equal_transfer_bytes=262144"
    echo "elementwise_sizes=1024,65536,1048576"
    echo "reduction_sizes=1024,65536,1048576"
    echo "matmul_sizes=32,128,512"
    echo "resident_chain_operations=5"
    echo "benchmark_commit=$(git -C "$tensor_benchmark_repo" rev-parse HEAD)"
    echo "silex_commit=$(git -C "$tensor_candidate_root/Silex" rev-parse HEAD)"
    echo "tensor_commit=$(git -C "$tensor_candidate_root/Packages/Tensor" rev-parse HEAD)"
    echo "gfx_gpu_commit=$(git -C "$tensor_candidate_root/Packages/GFX.GPU" rev-parse HEAD)"
    echo "gfx_commit=$(git -C "$tensor_candidate_root/Packages/GFX" rev-parse HEAD)"
    echo "std_commit=$(git -C "$tensor_candidate_root/Packages/STD" rev-parse HEAD)"
} >"$tensor_results/metadata.txt"

(
    cd "$tensor_candidate_root"
    "$tensor_silex" compile \
        Silex-Benchmarks/Sources/TensorStableCompute/Main.sx \
        --debug --nocache --output "$tensor_debug_binary"
) >"$tensor_results/build-debug.log" 2>&1

/usr/bin/time -l "$tensor_debug_binary" --verify \
    >"$tensor_results/diagnostic-debug.log" \
    2>"$tensor_results/diagnostic-debug.time"

(
    cd "$tensor_candidate_root"
    "$tensor_silex" compile \
        Silex-Benchmarks/Sources/TensorStableCompute/Main.sx \
        --release --nocache --output "$tensor_release_binary"
) >"$tensor_results/build-release.log" 2>&1

for tensor_group in types elementwise reduction matmul chain
do
    tensor_repetition=1
    while [ "$tensor_repetition" -le 7 ]; do
        echo "[$tensor_group] process $tensor_repetition/7"
        /usr/bin/time -l "$tensor_release_binary" "--measure-$tensor_group" \
            >"$tensor_results/$tensor_group-$tensor_repetition.log" \
            2>"$tensor_results/$tensor_group-$tensor_repetition.time"
        tensor_repetition=$((tensor_repetition + 1))
    done
done

python3 "$tensor_script_dir/Summarize.py" "$tensor_results"
echo "results: $tensor_results"
