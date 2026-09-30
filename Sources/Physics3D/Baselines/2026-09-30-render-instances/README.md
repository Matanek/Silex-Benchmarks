# Immediate instanced rendering — local diagnostic

## Configuration and provenance

Apple M3 Pro, macOS 26.6.2 ARM64, Metal, Release. Examples candidate
`312fad5cc617a702118bcf0747a7fdbf2a628a05`, compiler `251d4ec827e15e117d945d22532290f8c19ae48c`,
physics `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
Both final binaries explicitly report immediate presentation. Each final log
records its executable SHA256. Run from the Spec Worktree group:

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig" Silex/Toolchain/zig-out/bin/silex compile Silex-Examples/Sources/Physics3D/StressScene.sx --backend native --release --nocache -o .silex/physics3d-stress-scene-release
PATH="/Library/Developer/CommandLineTools/usr/bin:$PATH" ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig" Silex/Toolchain/zig-out/bin/silex compile Silex-Examples/Sources/Physics3D/StressScene.sx --release --nocache --backend llvm -o .silex/physics3d-stress-scene-llvm
.silex/physics3d-stress-scene-release bin 2048
.silex/physics3d-stress-scene-llvm bin 2048
```

Dynamic visuals use eight Scene3D instance groups instead of 2048 ECS
entities. Pose synchronization runs after simulation or emission, and groups
whose poses did not change retain their revision. Geometry (320 triangles per
sphere), shadows, colors, physical bodies and solver settings are unchanged.
Two source tests pass: progressive emission and instance pose/revision mapping.
Both final Release builds succeed.

## Full active simulation

One bounded 42-second execution per backend, LLVM first, Native second, normal
priority, no concurrent compilation. Physics stays active. The last eight
one-second telemetry windows at 2048 emitted bodies give:

| Backend | Rendered FPS | Physics ms/step | Physics ms/frame |
| --- | ---: | ---: | ---: |
| LLVM | 192–211 | 9.78–9.99 | 2.78–3.11 |
| Native | 9.6–9.8 | 25.08–25.47 | 100.34–101.89 |

See `summary.json` and full logs for exact values and earlier phases. LLVM
maintains approximately 60 steps/s; Native performs four catch-up steps per
frame and reaches approximately 39 steps/s. All 2048 bodies remain awake.
The displayed RENDER FRAME is the complete frame interval, including physics;
it is not an isolated GPU duration. Native's active >120 FPS objective is
**not met**. The native physics cost accounts for most of its >100 ms frames.

## Exploratory isolated rendering

Temporary probes paused physics after filling 2048 bodies. These results must
not be used as active-simulation FPS. Single runs, not balanced repetitions:

- Immediate baseline, per-body visual synchronization every frame: ~115–121 FPS.
- Synchronization only after changes, individual entities: Native ~120 FPS;
  LLVM late stable range ~280–310 FPS with transient drops.
- Grouped instances: Native ~535–538 FPS in three full paused windows.
  The single LLVM probe instead plateaued at ~120 FPS, an unresolved anomalous
  observation; no isolated LLVM gain is qualified from that run.

Probe sources and executables were temporary diagnostics. Their logs are
retained for transparency, not as a portable benchmark contract. Final public
binaries have no automatic pause. The user's separate observation of LLVM
frame times near 2 ms is not substituted for these measurements.

## Interpretation limits

The shared portable program does not imply identical optimized IR: LLVM disables
`collection_view_inlining` before its lowering, while Native uses the default.
The backend comparison identifies a cost in the overall generated-code path;
it does not alone prove that the IR is optimal or isolate register allocation.
Frame-driven emission and Native's simulation backlog also prevent asserting
identical physical states in these windowed runs. Earlier fixed-work physics
controls remain the semantic comparison.

This is a local diagnostic with one final execution per backend, not a balanced
performance campaign, an X64/Windows/Linux result, or a comparison with Unity.
The sleep and penetration limitations of the frozen physics baseline remain.
