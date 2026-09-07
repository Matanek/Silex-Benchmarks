#!/usr/bin/env bash

set -euo pipefail
export LC_ALL=C

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package_directory="$(cd "${script_directory}/../.." && pwd)"
workspace_directory="$(cd "${script_directory}/../../.." && pwd)"
baseline_directory="${script_directory}/Baselines"

count=4000
frames=480
runs=7
warmups=1
wait_before_run=false
skip_build=false
capture_timestamp="$(date '+%Y-%m-%d-%H%M%S')"
architecture="$(uname -m)"
output_path="${baseline_directory}/${capture_timestamp}-${architecture}-boids.log"

usage() {
    cat <<'EOF'
Usage: RunComparison.sh [options]

Build and compare the Silex, C++ architectural, and C++ direct Boids
witnesses. The default protocol discards one warm-up process per executable,
then records seven fixed-workload runs in rotating witness order.

Options:
  --count N          Boid count passed to every executable (default: 4000)
  --frames N         Measured fixed-delta frames per executable (default: 480)
  --runs N           Recorded processes per executable (default: 7)
  --warmups N        Discarded warm-up processes per executable (default: 1)
  --output PATH      Final log path (default: timestamped Baselines log)
  --build-dir PATH   Reusable build directory (default: workspace-isolated temp directory)
  --skip-build       Reuse executables already present in --build-dir
  --wait             Pause after building so active competing workloads can stop
  -h, --help         Show this help
EOF
}

fail() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

command -v awk >/dev/null || fail "awk is required"
command -v cksum >/dev/null || fail "cksum is required"
workspace_cache_key="$(printf '%s' "${workspace_directory}" | cksum | awk '{print $1}')"
build_directory="${TMPDIR:-/tmp}"
build_directory="${build_directory%/}/gfx-scene2d-boids-${workspace_cache_key}"

require_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "${value}" ]] || fail "${option} requires a value"
}

require_nonnegative_integer() {
    local option="$1"
    local value="$2"
    case "${value}" in
        ''|*[!0-9]*) fail "${option} must be a non-negative integer" ;;
    esac
}

while (( $# > 0 )); do
    case "$1" in
        --count)
            require_value "$1" "${2:-}"
            count="$2"
            shift 2
            ;;
        --runs)
            require_value "$1" "${2:-}"
            runs="$2"
            shift 2
            ;;
        --frames)
            require_value "$1" "${2:-}"
            frames="$2"
            shift 2
            ;;
        --warmups)
            require_value "$1" "${2:-}"
            warmups="$2"
            shift 2
            ;;
        --output)
            require_value "$1" "${2:-}"
            output_path="$2"
            shift 2
            ;;
        --build-dir)
            require_value "$1" "${2:-}"
            build_directory="$2"
            shift 2
            ;;
        --skip-build)
            skip_build=true
            shift
            ;;
        --wait)
            wait_before_run=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
done

require_nonnegative_integer --count "${count}"
require_nonnegative_integer --frames "${frames}"
require_nonnegative_integer --runs "${runs}"
require_nonnegative_integer --warmups "${warmups}"
(( count > 0 )) || fail "--count must be greater than zero"
(( frames > 0 )) || fail "--frames must be greater than zero"
(( runs > 0 )) || fail "--runs must be greater than zero"

case "${output_path}" in
    /*) ;;
    *) output_path="${PWD}/${output_path}" ;;
esac
case "${build_directory}" in
    /*) ;;
    *) build_directory="${PWD}/${build_directory}" ;;
esac

partial_output_path="${output_path}.partial"
[[ ! -e "${output_path}" ]] || fail "refusing to overwrite ${output_path}"
[[ ! -e "${partial_output_path}" ]] || fail "refusing to overwrite ${partial_output_path}"

silex_compiler="${workspace_directory}/Silex/Toolchain/zig-out/bin/silex"
silex_executable="${build_directory}/gfx-boids-silex"
cpp_build_directory="${build_directory}/cpp"
cpp_architectural_executable="${cpp_build_directory}/BoidsCppArchitectural"
cpp_direct_executable="${cpp_build_directory}/BoidsCppDirect"

command -v git >/dev/null || fail "git is required"
[[ -x "${silex_compiler}" ]] || fail "build the workspace Silex compiler first: ${silex_compiler}"

if [[ "${skip_build}" == false ]]; then
    command -v cmake >/dev/null || fail "cmake is required"
    mkdir -p "${build_directory}"
    printf 'Building Silex witness...\n'
    "${silex_compiler}" compile \
        "${script_directory}/Silex.sx" \
        -o "${silex_executable}"

    printf 'Configuring C++ witnesses...\n'
    cmake \
        -S "${script_directory}/Cpp" \
        -B "${cpp_build_directory}" \
        -DCMAKE_BUILD_TYPE=Release
    cmake --build "${cpp_build_directory}" --config Release
fi

if [[ ! -x "${cpp_architectural_executable}" && -x "${cpp_build_directory}/Release/BoidsCppArchitectural" ]]; then
    cpp_architectural_executable="${cpp_build_directory}/Release/BoidsCppArchitectural"
fi
if [[ ! -x "${cpp_direct_executable}" && -x "${cpp_build_directory}/Release/BoidsCppDirect" ]]; then
    cpp_direct_executable="${cpp_build_directory}/Release/BoidsCppDirect"
fi

[[ -x "${silex_executable}" ]] || fail "missing Silex executable: ${silex_executable}"
[[ -x "${cpp_architectural_executable}" ]] || fail "missing C++ architectural executable: ${cpp_architectural_executable}"
[[ -x "${cpp_direct_executable}" ]] || fail "missing C++ direct executable: ${cpp_direct_executable}"

if [[ "${wait_before_run}" == true ]]; then
    printf '\nBuild complete. Ensure no competing workload is active, then press Return. Idle applications may remain open.\n'
    IFS= read -r _
fi

git_commit() {
    git -C "$1" rev-parse HEAD 2>/dev/null || printf 'unavailable'
}

repository_is_dirty() {
    local repository="$1"
    local status
    status="$(git -C "${repository}" status --porcelain 2>/dev/null)"
    if [[ "${repository}" == "${package_directory}" ]]; then
        status="$(printf '%s\n' "${status}" | awk \
            '$0 !~ /^\?\? Sources\/Boids2D\/Baselines\/.*-boids\.log(\.partial)?$/ { print }')"
    fi
    if [[ -n "${status}" ]]; then
        printf 'true'
    else
        printf 'false'
    fi
}

sanitize_metadata() {
    printf '%s' "$1" | tr ' /' '__' | tr -cd '[:alnum:]_.:+,-'
}

is_linked_repository() {
    [[ "$1" == user-link || "$1" == workspace-link ]]
}

host_model="unknown"
cpu="unknown"
memory_bytes="unknown"
os_name="$(uname -s)"
os_version="$(uname -r)"
if [[ "$(uname -s)" == Darwin ]]; then
    host_model="$(sysctl -n hw.model 2>/dev/null || printf 'unknown')"
    cpu="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || printf 'unknown')"
    memory_bytes="$(sysctl -n hw.memsize 2>/dev/null || printf 'unknown')"
    os_name="macOS"
    os_version="$(sw_vers -productVersion 2>/dev/null || printf 'unknown')"
    os_build="$(sw_vers -buildVersion 2>/dev/null || printf 'unknown')"
else
    os_build="unknown"
fi

silex_version="$("${silex_compiler}" --version 2>/dev/null | awk 'NR == 1 { print $NF; exit }')"
cpp_compiler="unknown"
cmake_version="unknown"
sdl_version="unknown"
if command -v c++ >/dev/null; then
    cpp_compiler="$(c++ --version 2>/dev/null | awk 'NR == 1 { print; exit }')"
fi
if command -v cmake >/dev/null; then
    cmake_version="$(cmake --version | awk 'NR == 1 { print $3; exit }')"
fi
if command -v pkg-config >/dev/null; then
    sdl_version="$(pkg-config --modversion sdl3 2>/dev/null || printf 'unknown')"
fi
entt_revision="system_package"
if [[ -d "${cpp_build_directory}/_deps/entt-src/.git" ]]; then
    entt_revision="$(git_commit "${cpp_build_directory}/_deps/entt-src")"
fi

resolved_packages="$("${silex_compiler}" packages resolve "${script_directory}/Silex.sx")" || \
    fail "could not resolve the Silex witness package closure"
resolved_package_names=()
resolved_package_versions=()
resolved_package_origins=()
resolved_package_paths=()
while read -r package_name package_version package_origin package_path; do
    [[ -n "${package_name}" ]] || continue
    resolved_package_names+=("${package_name}")
    resolved_package_versions+=("${package_version}")
    resolved_package_origins+=("${package_origin}")
    resolved_package_paths+=("${package_path}")
done <<< "${resolved_packages}"

source_repositories_dirty=false
source_repositories=("${package_directory}" "${workspace_directory}/Silex")
for package_index in "${!resolved_package_names[@]}"; do
    if is_linked_repository "${resolved_package_origins[package_index]}"; then
        source_repositories+=("${resolved_package_paths[package_index]}")
    fi
done
for repository in "${source_repositories[@]}"
do
    if [[ "$(repository_is_dirty "${repository}")" == true ]]; then
        source_repositories_dirty=true
        break
    fi
done

mkdir -p "$(dirname "${output_path}")"
{
    printf '# captured=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')"
    printf '# host_model=%s\n' "$(sanitize_metadata "${host_model}")"
    printf '# cpu=%s\n' "$(sanitize_metadata "${cpu}")"
    printf '# memory_bytes=%s\n' "${memory_bytes}"
    printf '# os=%s_%s_%s\n' "$(sanitize_metadata "${os_name}")" "$(sanitize_metadata "${os_version}")" "$(sanitize_metadata "${os_build}")"
    printf '# architecture=%s\n' "${architecture}"
    printf '# source_repositories_dirty=%s\n' "${source_repositories_dirty}"
    printf '# waited_for_competing_workloads=%s\n' "${wait_before_run}"
    printf '# silex_mode=release_default\n'
    printf '# cpp_mode=Release\n'
    printf '# silex_version=%s\n' "$(sanitize_metadata "${silex_version}")"
    printf '# benchmarks_commit=%s\n' "$(git_commit "${package_directory}")"
    printf '# silex_toolchain_commit=%s\n' "$(git_commit "${workspace_directory}/Silex")"
    for package_index in "${!resolved_package_names[@]}"; do
        package_key="$(printf '%s' "${resolved_package_names[package_index]}" | \
            tr '[:upper:].' '[:lower:]_')"
        printf '# %s_version=%s\n' \
            "${package_key}" "${resolved_package_versions[package_index]}"
        printf '# %s_source=%s\n' \
            "${package_key}" "${resolved_package_origins[package_index]}"
        if is_linked_repository "${resolved_package_origins[package_index]}"; then
            printf '# %s_commit=%s\n' \
                "${package_key}" "$(git_commit "${resolved_package_paths[package_index]}")"
        fi
    done
    printf '# cpp_compiler=%s\n' "$(sanitize_metadata "${cpp_compiler}")"
    printf '# cmake_version=%s\n' "${cmake_version}"
    printf '# sdl_version=%s\n' "${sdl_version}"
    printf '# entt_revision=%s\n' "${entt_revision}"
    printf '# protocol=%s_discarded_warmups_per_executable_then_%s_isolated_rotated_fixed_workload_runs\n' "${warmups}" "${runs}"
    printf '# rotation=silex_cpp-architectural_cpp-direct\n'
    printf '# count=%s\n' "${count}"
    printf '# frames=%s\n' "${frames}"
    printf '# simulation_delta=1_over_60_seconds\n'
    printf '# presentation=immediate\n'
} > "${partial_output_path}"

expected_signature=""
expected_state=""
expected_state_label=""

sentinel_signature() {
    awk '
        {
            for (field_index = 1; field_index <= NF; field_index++) {
                split($field_index, pair, "=")
                if (pair[1] == "present") present = pair[2]
                if (pair[1] == "window") {
                    split(pair[2], size, "x")
                    window_width = size[1] + 0
                    window_height = size[2] + 0
                }
                if (pair[1] == "pixels") {
                    split(pair[2], size, "x")
                    pixel_width = size[1] + 0
                    pixel_height = size[2] + 0
                }
                if (pair[1] == "scale") scale = pair[2] + 0
                if (pair[1] == "density") density = pair[2] + 0
            }
        }
        END {
            if (present == "" || window_width == 0 || window_height == 0 ||
                pixel_width == 0 || pixel_height == 0 || scale == 0 || density == 0) {
                exit 1
            }
            printf "%s|%.6g|%.6g|%.6g|%.6g|%.6g|%.6g", present,
                window_width, window_height, pixel_width, pixel_height, scale, density
        }
    '
}

state_vector() {
    awk '
        {
            for (field_index = 1; field_index <= NF; field_index++) {
                split($field_index, pair, "=")
                if (pair[1] == "fixed_delta") { fixed_delta = pair[2] + 0; found_delta = 1 }
                if (pair[1] == "state_step") { state_step = pair[2] + 0; found_step = 1 }
                if (pair[1] == "initial_px") { initial_px = pair[2] + 0; found_initial_px = 1 }
                if (pair[1] == "initial_py") { initial_py = pair[2] + 0; found_initial_py = 1 }
                if (pair[1] == "initial_vx") { initial_vx = pair[2] + 0; found_initial_vx = 1 }
                if (pair[1] == "initial_vy") { initial_vy = pair[2] + 0; found_initial_vy = 1 }
                if (pair[1] == "initial_p2") { initial_p2 = pair[2] + 0; found_initial_p2 = 1 }
                if (pair[1] == "initial_v2") { initial_v2 = pair[2] + 0; found_initial_v2 = 1 }
                if (pair[1] == "state_px") { state_px = pair[2] + 0; found_px = 1 }
                if (pair[1] == "state_py") { state_py = pair[2] + 0; found_py = 1 }
                if (pair[1] == "state_vx") { state_vx = pair[2] + 0; found_vx = 1 }
                if (pair[1] == "state_vy") { state_vy = pair[2] + 0; found_vy = 1 }
                if (pair[1] == "state_p2") { state_p2 = pair[2] + 0; found_p2 = 1 }
                if (pair[1] == "state_v2") { state_v2 = pair[2] + 0; found_v2 = 1 }
            }
        }
        END {
            if (!found_delta || !found_step || !found_initial_px ||
                !found_initial_py || !found_initial_vx || !found_initial_vy ||
                !found_initial_p2 || !found_initial_v2 || !found_px || !found_py ||
                !found_vx || !found_vy || !found_p2 || !found_v2) exit 1
            printf "%.9g|%d|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g|%.9g", fixed_delta,
                state_step, initial_px, initial_py, initial_vx, initial_vy,
                initial_p2, initial_v2, state_px, state_py, state_vx, state_vy,
                state_p2, state_v2
        }
    '
}

state_vectors_match() {
    local reference="$1"
    local observed="$2"
    awk -F'|' -v reference="${reference}" -v observed="${observed}" '
        function absolute(value) { return value < 0 ? -value : value }
        BEGIN {
            split(reference, expected, "|")
            split(observed, actual, "|")
            if (actual[2] != expected[2]) exit 1
            if (absolute(actual[1] - expected[1]) > 0.0000001) exit 1
            for (item = 3; item <= 14; item++) {
                scale = absolute(expected[item])
                if (absolute(actual[item]) > scale) scale = absolute(actual[item])
                if (absolute(actual[item] - expected[item]) > 0.05 + scale * 0.00002) {
                    exit 1
                }
            }
        }
    '
}

run_witness() {
    local label="$1"
    local prefix="$2"
    local executable="$3"
    local record="$4"
    local process_output
    local sentinel
    local sentinel_count
    local signature
    local state

    printf '%s\n' "${label}"
    process_output="$("${executable}" "${count}" "${frames}")"
    printf '%s\n' "${process_output}"
    sentinel="$(printf '%s\n' "${process_output}" | awk -v prefix="${prefix} " 'index($0, prefix) == 1 { print }')"
    sentinel_count="$(printf '%s\n' "${sentinel}" | awk 'NF > 0 { count++ } END { print count + 0 }')"
    [[ "${sentinel_count}" == 1 ]] || fail "${label} emitted ${sentinel_count} matching sentinels"
    [[ "${sentinel}" == *"count=${count} "* ]] || fail "${label} reported the wrong boid count"
    [[ "${sentinel}" == *"frames=${frames} "* ]] || fail "${label} reported the wrong frame count"
    [[ "${sentinel}" == *"present=immediate "* ]] || fail "${label} did not use immediate presentation"

    signature="$(printf '%s\n' "${sentinel}" | sentinel_signature)" || fail "${label} omitted window or display metadata"
    if [[ -z "${expected_signature}" ]]; then
        expected_signature="${signature}"
    elif [[ "${signature}" != "${expected_signature}" ]]; then
        fail "${label} display signature ${signature} differs from ${expected_signature}"
    fi

    state="$(printf '%s\n' "${sentinel}" | state_vector)" || fail "${label} omitted the deterministic state witness"
    if [[ -z "${expected_state}" ]]; then
        expected_state="${state}"
        expected_state_label="${label}"
    elif ! state_vectors_match "${expected_state}" "${state}"; then
        fail "${label} state ${state} differs from ${expected_state_label} state ${expected_state}"
    fi

    if [[ "${record}" == true ]]; then
        printf '%s\n' "${sentinel}" >> "${partial_output_path}"
    fi
}

for (( warmup = 1; warmup <= warmups; warmup++ )); do
    printf '\nWarm-up %d/%d (discarded)\n' "${warmup}" "${warmups}"
    run_witness '  Silex/GFX' 'SILEX_GFX_BOIDS' "${silex_executable}" false
    run_witness '  C++ architectural' 'CPP_ARCHITECTURAL_BOIDS' "${cpp_architectural_executable}" false
    run_witness '  C++ direct' 'CPP_DIRECT_BOIDS' "${cpp_direct_executable}" false
done

for (( run = 1; run <= runs; run++ )); do
    printf '\nRecorded round %d/%d\n' "${run}" "${runs}"
    printf '# round=%d\n' "${run}" >> "${partial_output_path}"
    run_witness '  Silex/GFX' 'SILEX_GFX_BOIDS' "${silex_executable}" true
    run_witness '  C++ architectural' 'CPP_ARCHITECTURAL_BOIDS' "${cpp_architectural_executable}" true
    run_witness '  C++ direct' 'CPP_DIRECT_BOIDS' "${cpp_direct_executable}" true
done

statistics_for() {
    local prefix="$1"
    awk -v prefix="${prefix}" '
        index($0, prefix " ") == 1 {
            for (field = 1; field <= NF; field++) {
                if ($field ~ /^fps=/) {
                    split($field, pair, "=")
                    values[++count] = pair[2] + 0
                }
            }
        }
        END {
            if (count == 0) exit 1
            for (left = 1; left <= count; left++) {
                for (right = left + 1; right <= count; right++) {
                    if (values[right] < values[left]) {
                        temporary = values[left]
                        values[left] = values[right]
                        values[right] = temporary
                    }
                }
            }
            if (count % 2 == 1) median = values[(count + 1) / 2]
            else median = (values[count / 2] + values[count / 2 + 1]) / 2
            for (item = 1; item <= count; item++) {
                deviation = values[item] - median
                if (deviation < 0) deviation = -deviation
                deviations[item] = deviation
            }
            for (left = 1; left <= count; left++) {
                for (right = left + 1; right <= count; right++) {
                    if (deviations[right] < deviations[left]) {
                        temporary = deviations[left]
                        deviations[left] = deviations[right]
                        deviations[right] = temporary
                    }
                }
            }
            if (count % 2 == 1) mad = deviations[(count + 1) / 2]
            else mad = (deviations[count / 2] + deviations[count / 2 + 1]) / 2
            printf "%.6f|%.4f|%.6f|%.6f", median, mad / median * 100.0,
                values[1], values[count]
        }
    ' "${partial_output_path}"
}

IFS='|' read -r silex_median silex_mad silex_minimum silex_maximum <<< "$(statistics_for SILEX_GFX_BOIDS)"
IFS='|' read -r architectural_median architectural_mad architectural_minimum architectural_maximum <<< "$(statistics_for CPP_ARCHITECTURAL_BOIDS)"
IFS='|' read -r direct_median direct_mad direct_minimum direct_maximum <<< "$(statistics_for CPP_DIRECT_BOIDS)"
silex_relative="$(awk -v value="${silex_median}" -v reference="${architectural_median}" 'BEGIN { printf "%.2f", (value / reference - 1.0) * 100.0 }')"
direct_relative="$(awk -v value="${direct_median}" -v reference="${architectural_median}" 'BEGIN { printf "%.2f", (value / reference - 1.0) * 100.0 }')"

{
    printf '# summary_silex median_fps=%s mad_percent=%s range=%s..%s relative_to_architectural_percent=%s\n' \
        "${silex_median}" "${silex_mad}" "${silex_minimum}" "${silex_maximum}" "${silex_relative}"
    printf '# summary_cpp_architectural median_fps=%s mad_percent=%s range=%s..%s relative_to_architectural_percent=0.00\n' \
        "${architectural_median}" "${architectural_mad}" "${architectural_minimum}" "${architectural_maximum}"
    printf '# summary_cpp_direct median_fps=%s mad_percent=%s range=%s..%s relative_to_architectural_percent=%s\n' \
        "${direct_median}" "${direct_mad}" "${direct_minimum}" "${direct_maximum}" "${direct_relative}"
} >> "${partial_output_path}"

mv "${partial_output_path}" "${output_path}"

printf '\n%-22s %12s %10s %23s %14s\n' 'Witness' 'Median FPS' 'MAD' 'Range' 'vs C++ arch.'
printf '%-22s %12s %9s%% %10s..%-10s %13s%%\n' 'Silex/GFX' "${silex_median}" "${silex_mad}" "${silex_minimum}" "${silex_maximum}" "${silex_relative}"
printf '%-22s %12s %9s%% %10s..%-10s %13s%%\n' 'C++ architectural' "${architectural_median}" "${architectural_mad}" "${architectural_minimum}" "${architectural_maximum}" '0.00'
printf '%-22s %12s %9s%% %10s..%-10s %13s%%\n' 'C++ direct' "${direct_median}" "${direct_mad}" "${direct_minimum}" "${direct_maximum}" "${direct_relative}"
printf '\nLog: %s\n' "${output_path}"
