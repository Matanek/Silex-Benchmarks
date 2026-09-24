# Compare FallingBodies2D at equal work

Compile from the workspace root, then run a bounded workload:

```sh
silex compile Silex-Benchmarks/Sources/FallingBodies2D/Main.sx --release -o /tmp/falling-bodies-2d
/tmp/falling-bodies-2d --stress --smoke --batch-1 --immediate --no-panel --fixed-work
```

This configuration creates 120 bodies (60 circles and 60 boxes), with seed
`0x51_1E_20_2D`, profiling enabled and sleeping allowed. It performs 60 warm-up
frames followed by 120 measured frames. Each frame submits one fixed `1/60`
physics step to the existing worker and waits for completion before collecting
its transform buffer. The ordinary ECS synchronization and renderer still run.
The final report must show 120 measured steps and 180 total steps, and includes
every body's position, rotation, velocities and awake state. Snapshot positions
and rotations are checked against the physics world before visual synchronization.

Add `--render-only` for the same frame counts without physics steps. Its final
state is a separate control, not an expected match for the simulated scene.
For interactive frame-cost diagnosis, `--no-physics-panel` hides only the
benchmark's physics metrics, and `--no-performance-panel` hides only the GFX
performance overlay. `--no-panel` still hides both. These flags leave the
body count and simulation schedule unchanged.
`--static-performance-panel` keeps that overlay visible but disables its
periodic refresh, isolating its drawing cost from text and canvas updates.

`--fixed-work` requires a stress population, a bounded smoke mode and
`--batch-1`. Longer smoke modes keep their frame counts but do not enforce a
minimum wall-clock duration. `--smoke-fast` uses five warm-up frames and twenty
measured frames. Without `--fixed-work`, the existing real-time accumulator and
asynchronous overlap are unchanged.

Check exit status, diagnostics, work counts and complete states before comparing
timings. Compare Release builds with identical options, use three warm-up runs
and seven alternating samples, and preserve raw results and binary identities.
Report worker time, transfer time and frame throughput separately. Fixed-work
throughput does not measure interactive overlap; presentation can still limit
FPS, and a sleeping scene is not an active-solver benchmark. State printing is
outside the reported measurement interval. Do not compare these results with
older real-time baselines as if they performed the same work.

The [20 September 2026 LLVM cycle traversal record](Baselines/2026-09-20-llvm-cycle-boundary/README.md)
contains a diagnosed interactive regression, its compiler correction, paired
controls, correctness evidence and presentation limits.
