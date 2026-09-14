# Boids native / LLVM / C++ comparison

The comparison has three variants:

- Silex/Natif compiles `Silex.sx` with the native Silex backend;
- Silex/LLVM compiles that same source with the LLVM evaluation backend;
- C++ architectural uses EnTT and SDL_GPU to match the Silex/GFX Scene2D path,
  with the same drawing shader, vertex and instance layouts and one instanced draw.

Every variant preserves the quadratic algorithm, one flock snapshot per frame,
the same simulation constants, a 960 × 640 logical window with a high-density
framebuffer, and immediate presentation without VSync. Each process performs
one untimed warm-up frame followed by 480 measured frames with 4,000 boids at a
fixed simulation delta of 1/60 second.

## Run the prepared comparison

Run the executable script directly from the SilexProject workspace root:

```sh
.specs/Silex-LLVM-Backend-Evaluation/Worktree/Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

`RunComparison.sh` resolves paths from its own location, so it also works from
another current directory. It reads the prepared configuration at
`Evaluations/boids-comparison/Configuration.json` under the Spec's `Worktree/`.
Use `--config PATH` to select another prepared configuration. The three Release
executables and their build provenance must already exist; the runner verifies
their hashes, source repository commits and tracked working-tree state.
After rebuilding or changing inputs, prepare a new configuration from the verified
artifacts and their build provenance before running again. Never just update a
hash to bypass an unexplained mismatch.

`--prepare-only` verifies readiness without launching any Boids process.
`--wait` performs that verification, waits for Return, then verifies again before
launching. There is no automatic switch to another compiler or comparison script.
The script embeds its checks, statistical policy and report generation. It requires
Python 3 (standard library only), with no separate Python runtime modules or
additional commands to launch.

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

Each capture writes **one Markdown file** directly to `Baselines/`, named for
its date, time, operating system and architecture, for example
`2026-09-14-073950-macos-arm64.md`. Generated names include fractional seconds
to avoid collisions. `--output PATH` overrides the destination; an existing
file is never overwritten. There is no accompanying log, JSON or summary file.

The report leads with mean, minimum, maximum and population standard deviation
of the FPS reported by each measured process, followed by differences between
variants in FPS and percent. These are statistics across repeated runs, not
per-frame extrema. Warm-ups are excluded from these calculations.

Foldable sections retain the individual FPS, execution order and brief capture
context in the same file. Display dimensions and application state are checked
internally and omitted from the report. An invalid or interrupted run leaves
one partial report with an error, without a completed comparison table.

[The current baseline](Baselines/2026-09-14-073950-macos-arm64.md) reformats the
last user capture without rerunning it. Its three retained series are descriptive
and nonstationary. The original raw capture remains in Git history at `245b9a9`.

## C++ architectural build

The C++23 executable requires SDL3 development files and `shadercross` discoverable
by CMake. CMake uses an installed EnTT 4 package or fetches the pinned EnTT commit
`85c6bba014049b5de8fad49d25424df2f1f6a8c1`. It compiles the sibling
`Packages/GFX.Scene2D/Shaders/Drawing.hlsl` source shared with Silex.
From the Spec's `Worktree/` root:

```sh
cmake -S Silex-Benchmarks/Sources/Boids2D/Cpp \
    -B Evaluations/boids-comparison/cpp -DCMAKE_BUILD_TYPE=Release
cmake --build Evaluations/boids-comparison/cpp --config Release
```

## Runner checks

From the benchmark repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s Sources/Boids2D -p 'Test*.py'
```

These checks exercise scheduling, input verification, invalid execution,
stationarity, direct shell execution, wait/prepare behavior, platform naming,
output location and statistics without
running a GPU benchmark.
