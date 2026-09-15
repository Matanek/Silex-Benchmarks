# Boids native / LLVM / C++ comparison

The comparison has three variants:

- Silex/Natif compiles `Silex.sx` with the native Silex backend;
- Silex/LLVM compiles that same source with the LLVM backend;
- C++/Clang uses EnTT and SDL_GPU to match the Silex/GFX Scene2D path,
  with the same drawing shader, vertex and instance layouts and one instanced draw.

Every variant preserves the quadratic algorithm, one flock snapshot per frame,
the same simulation constants, a 960 × 640 logical window with a high-density
framebuffer, and immediate presentation without VSync. Each process performs
one untimed warm-up frame followed by 480 measured frames with 4,000 boids at a
fixed simulation delta of 1/60 second.

## Build and run the comparison

Run the executable script directly from the SilexProject workspace root:

```sh
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

`RunComparison.sh` resolves the workspace from its own location, so it also
works from another current directory. It builds both Silex Release executables
with the workspace compiler and the C++ Release executable with CMake/Clang.
All preparation and configuration live in the script; no evaluation directory,
Spec artifact, or external configuration file is required.

The compiler defaults to `Silex/Toolchain/zig-out/bin/silex`; build it with
`./silex-dev build`, or select another executable with `SILEX_BIN`. `CXX` may
select Clang++. If the default Xcode compiler cannot run, the script tries the
installed macOS Command Line Tools and reports that choice. Explicit `CXX` or
`DEVELOPER_DIR` selections are honored. The C++ Release flags are explicitly
`-O3 -DNDEBUG`, with no additional cached global C++ flags; an incomplete CMake
configuration cannot silently leave this variant unoptimized.

The three binaries and one incremental CMake build occupy
`SilexProject/.silex/benchmarks/boids-comparison`. Subsequent launches update this
same directory, and Silex compilation uses the shared workspace cache. The
script records hashes of the current inputs, tools, binaries, shaders, repository
commits, and local tracked edits. Changes during preparation, the waiting period,
or measurement invalidate the comparison. Local edits present before preparation
are allowed and remain unchanged.

`--prepare-only` builds and verifies readiness without launching any Boids
process. `--wait` prepares the executables, waits for Return, then verifies again
before launching. All measurements start after compilation finishes. The POSIX
shell script uses CMake, Clang++, `shadercross`, Git, `awk`, `cmp`, and
`shasum` or `sha256sum`; it requires neither Python nor `jq`. Temporary validation
data is removed on completion or interruption.

## Measurement and validity

The default run has six warm-up rounds and twelve measured rounds per executable.
Every six-round cycle runs all six permutations of the variants: each occupies
each position twice, and each ordered pair appears twice within rounds. Both
windows are independently balanced. `--warmups` accepts nonnegative multiples
of six; `--runs` accepts multiples of six, starting at six.

All three executables must exit with code 0, emit no stderr, and report exactly
one valid state witness. The runner checks the workload, fixed delta, initial
and final state, presentation mode and display dimensions. Native and LLVM
Silex state fields must match exactly, excluding FPS; C++ uses the existing
floating-point tolerance. A failure invalidates the capture.

Each measured series retains every sample. A series is stationary only if its
median absolute deviation is at most 1% of its median, its range at most 4%,
its fitted drift at most 1%, and its shift between half-series medians at most 1%.
The runner returns 0 for a complete stationary capture, 2 for a complete but
nonstationary capture, and an error for invalid or interrupted execution.
Stationarity alone does not establish an LLVM adoption decision or cross-platform
correctness.

## Report

Each capture writes **one plain-text `.log` file** directly to `Baselines/`, named for
its date, time, operating system and architecture, for example
`2026-09-14-073950-macos-arm64.log`. `--output PATH` overrides the destination;
an existing file is never overwritten. There is no accompanying JSON or summary file.

The report leads with mean, minimum, maximum and population standard deviation
of the FPS reported by each measured process, followed by differences between
variants in FPS and percent. These are statistics across repeated runs, not
per-frame extrema. Warm-ups are excluded from these calculations.

Aligned columns retain the individual FPS and execution order in the same file,
with brief capture context. Display dimensions and application state are checked
internally and omitted from the report. An invalid or interrupted run leaves
one partial report with an error, without a completed comparison table.

[The initial reference](Baselines/2026-09-14-073950-macos-arm64.log) and
[the latest user capture](Baselines/2026-09-14-092230-615615-macos-arm64.log)
preserve the measured FPS and execution order without rerunning either campaign.
Both remain descriptive and nonstationary. The original raw capture for the
initial reference remains in Git history at `245b9a9`.

## C++/Clang build

The C++23 executable requires SDL3 development files and `shadercross` discoverable
by CMake. CMake uses an installed EnTT 4 package or fetches the pinned EnTT commit
`85c6bba014049b5de8fad49d25424df2f1f6a8c1`. It compiles the sibling
`Packages/GFX.Scene2D/Shaders/Drawing.hlsl` source shared with Silex.
For a manual C++ build from the SilexProject workspace root:

```sh
cmake -S Silex-Benchmarks/Sources/Boids2D/Cpp \
    -B .silex/benchmarks/boids-comparison/cpp -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER=clang++
cmake --build .silex/benchmarks/boids-comparison/cpp --config Release
```
