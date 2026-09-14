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

Python 3 is the only comparison entry point. From the SilexProject workspace root:

```sh
python3 .specs/Silex-LLVM-Backend-Evaluation/Worktree/Silex-Benchmarks/Sources/Boids2D/RunComparison.py --wait
```

`RunComparison.py` resolves paths from its own location, so it also works from
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
`Protocol.py` is an internal statistics and semantic-validation module;
`Protocol.json` records its workload and stationarity thresholds.

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

Timestamped raw logs and JSON reports are written directly to `Baselines/`.
`--output PATH` overrides the log destination; the JSON report is written beside
it. Existing captures are never overwritten. Reports preserve every warm-up,
measurement, process exit code, stdout/stderr, actual order and prepared
configuration, including evidence from an interrupted or invalid capture.

[The current baseline](Baselines/README.md) is the last user capture. Its raw
files preserve the original measurement conditions; its three retained series
are descriptive and nonstationary.

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
stationarity, wait/prepare behavior, output location and baseline integrity without
running a GPU benchmark.
