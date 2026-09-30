# Dense 3D physics: sphere solver and spatial pairs

## Reproduction and provenance

Measured locally on Apple M3 Pro, macOS 26.6.2 ARM64. Compiler
`251d4ec827e15e117d945d22532290f8c19ae48c`, native backend, Release,
`--nocache`. Physics baseline `1d77c5e917d9bf7df1fa1a5b9def6628dfcf60b6`;
candidate `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
Raw CSV, source and executable hashes, run ordering and statistics are in
[comparison.json](comparison.json). No other build or benchmark ran during the
measurements. Benchmark processes used normal priority, including the LLVM control.

Compile from the Spec's `Worktree/` root, with the selected Physics checkout:

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig" Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/Physics3D/SpherePileScale.sx --release --nocache -o .silex/sphere-pile-scale
.silex/sphere-pile-scale 4096
.silex/sphere-pile-scale 8192
```

Use the same command with `AquariumFill.sx` or `ColumnPeak.sx` and run without
arguments. `SpherePileScale` starts a populated pile; its floor grows with
count to maintain approximately eight layers. It is not the progressive jet
or a reproduction of a Unity/Godot video. Settings remain fixed: 60 Hz, 12
velocity iterations, 4 position iterations, original gravity and materials,
zero damping, original sleep thresholds.

## CPU results

Median of each run's mean step time, including filling/falling and settling:

| Workload | Baseline ms/step | Candidate ms/step | Change | Balanced pairs |
|---|---:|---:|---:|---:|
| Aquarium 1,024, 1,800 steps | 10.956 | 8.402 | −23.3% | 3 |
| Column 256, 600 steps | 6.340 | 6.474 | +2.1% | 2 |
| Pile 4,096, 600 steps | 59.050 | 42.615 | −27.8% | 2 |
| Pile 8,192, 600 steps | 126.882 | 88.297 | −30.4% | 1 |

The 8,192-body pair is diagnostic only; one pair does not establish variance.
The column's small cost increase is retained explicitly. All 600 sampled
column states match exactly. Dense sphere trajectories differ because the
specialized solver changes floating-point operation order. Every recorded
run passed its containment assertions. Native candidate runs reproduce the
same sampled states regardless of timing variation.

The private grid conservatively searches neighboring cells and falls back for
large or remote shapes. The sphere solver uses scalar tangent mass and zero
normal torque only for centered, isotropic spheres. Offset centers and
anisotropic inertia retain the general response. All **286 consumer tests in
52 files pass**, including analytic friction, linear/angular momentum,
anisotropic inertia, offset-center torque and exhaustive dense sphere pairs.

## Rendered aquarium

The scene is unchanged (`Silex-Examples` `82a8501`); its native Release binary
was rebuilt against the candidate. One bounded 30-second window run reports
approximately **60–64 FPS** over its final ten seconds at 1,024 spheres,
against **14–15 FPS** in the prior same-scene baseline window run. This is a
local smoke measurement, not a balanced rendered benchmark or cross-engine
comparison. See [baseline log](render-baseline.log) and
[candidate log](render-candidate.log).

Simulation remains near 60 steps/s. The reduced cost allows the loop to leave
its four-steps-per-frame catch-up regime and return to about one step/frame.
The frame-rate gain therefore exceeds the per-step CPU reduction. Almost all
spheres remain awake; no forced sleeping or reduced simulation quality explains
the gain. No screen capture was used.

## Compiler control and remaining limits

The same candidate `AquariumFill` compiled with explicit `--backend llvm`
(`PATH=/Library/Developer/CommandLineTools/usr/bin:$PATH` for the linker)
measures **2.881 ms/step overall, 4.031 ms/step in the final ten seconds** in
one diagnostic run, versus native medians 8.402 and 11.820. Every sampled
physical observable is identical to native (excluding timing columns 1/14).
This identifies generated code as a major remaining cost. The example's
default backend has not changed; this is not a claim of portable LLVM
qualification or rendered LLVM performance.

All 4,096/8,192 pile bodies are still awake at the end. Whole-island sleeping
is another structural limit: motion at the surface keeps a connected pile
active. Sleeping must be improved together with support and wake correctness,
not by suppressing dynamics to raise FPS.

The existing center-height quality target of **y ≥ 0.19 m is not met** by
baseline or candidate dense fixtures. Minimum heights (baseline → candidate):
0.181471 → 0.182296 m for the aquarium, 0.156582 → 0.168363 m for 4,096,
and 0.167849 → 0.167374 m for 8,192. Containment passes, but dense contact
stability is not qualified. At 4,096/8,192 the CPU cost remains too high;
these gains do not establish parity with the user's Unity reference.
