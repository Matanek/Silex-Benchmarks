#!/bin/sh
set -eu

behaviour_script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
behaviour_benchmark_repo=$(CDPATH= cd -- "$behaviour_script_dir/../.." && pwd)
behaviour_candidate_root=$(CDPATH= cd -- "$behaviour_benchmark_repo/.." && pwd)
behaviour_workspace_root=$(CDPATH= cd -- "$behaviour_candidate_root/../../.." && pwd)
behaviour_results=${1:-"$behaviour_script_dir/Results/$(date +%Y-%m-%d-%H%M%S)"}
behaviour_run_root=$(mktemp -d /private/tmp/silex-behaviour-tree.XXXXXX)
behaviour_binary="$behaviour_run_root/behaviour-tree-scheduling"
behaviour_silex=${SILEX_BIN:-"$behaviour_workspace_root/Silex/Toolchain/zig-out/bin/silex"}

trap 'rm -rf "$behaviour_run_root"' EXIT HUP INT TERM

mkdir -p "$behaviour_results"
"$behaviour_silex" packages resolve "$behaviour_benchmark_repo" \
    >"$behaviour_results/resolution.txt"
grep -F "AI 0.1.0 workspace-link $behaviour_candidate_root/Packages/AI" \
    "$behaviour_results/resolution.txt" >/dev/null

{
    echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "os=$(sw_vers -productName) $(sw_vers -productVersion) $(sw_vers -buildVersion)"
    echo "architecture=$(uname -m)"
    echo "target=macos-arm64"
    echo "cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || sysctl -n hw.model)"
    echo "silex=$($behaviour_silex --version)"
    echo "silex_commit=$(git -C "$behaviour_workspace_root/Silex" rev-parse HEAD)"
    echo "ai_commit=$(git -C "$behaviour_candidate_root/Packages/AI" rev-parse HEAD)"
    echo "benchmark_commit=$(git -C "$behaviour_benchmark_repo" rev-parse HEAD)"
    echo "mode=release"
    echo "processes_per_case=7"
    echo "tree_nodes=11"
    echo "tree_depth=5"
    echo "root_width=2"
} >"$behaviour_results/metadata.txt"

(
    cd "$behaviour_workspace_root"
    "$behaviour_silex" compile \
        .specs/AI-Behaviour-Tree/Worktree/Silex-Benchmarks/Sources/BehaviourTreeScheduling/Main.sx \
        --release --output "$behaviour_binary"
) >"$behaviour_results/build.log" 2>&1

"$behaviour_binary" verify >"$behaviour_results/verification.log"
grep -F "result=equivalent" "$behaviour_results/verification.log" >/dev/null

for behaviour_agents in 1000 10000 100000
do
    for behaviour_wake in 0 1 10 100
    do
        for behaviour_strategy in root resume event state_machine
        do
            behaviour_repetition=1
            while [ "$behaviour_repetition" -le 7 ]; do
                echo "[$behaviour_strategy agents=$behaviour_agents wake=$behaviour_wake%] process $behaviour_repetition/7"
                "$behaviour_binary" \
                    "$behaviour_strategy" "$behaviour_agents" "$behaviour_wake" \
                    >"$behaviour_results/$behaviour_agents-$behaviour_wake-$behaviour_strategy-$behaviour_repetition.log"
                behaviour_repetition=$((behaviour_repetition + 1))
            done
        done
    done
done

python3 "$behaviour_script_dir/Summarize.py" "$behaviour_results"
echo "results: $behaviour_results"
