# Qualify the first 3D physics foundation witness

This witness compares a native Silex program with an independently built
[Jolt Physics v5.6.0](https://github.com/jrouwe/JoltPhysics/releases/tag/v5.6.0)
oracle and an analytical result. It checks a quarter turn around Y, a solid
sphere's inertia, and a freely moving body with zero gravity and damping.
Separate fixtures below qualify bounded contact and sleep behaviors of the
Silex 3D world.

From the `Jolt-3D-Physics` Spec's `Worktree/` directory, run:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/Run.py
```

The runner needs `silex`, CMake, Make, Clang and `curl`. It downloads the
official archive for commit `e77f175595e64cb44218cc9d9d56fc365ad0e36a`,
verifies its SHA-256, builds Jolt as a separate CPU-only static library, and
compiles both programs in Debug and Release. All downloads and build outputs
stay under `Worktree/.silex/physics3d-oracle/`. The workspace link to `STD`
is confined to `Worktree/`; the runner verifies its effective origin. The
official Jolt source is not copied into the Silex package or its consumers.

To use an already downloaded copy of that exact archive:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/Run.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip
```

The current fixture is [Fixture.json](Fixture.json), schema 1. Its integer
inputs are passed unchanged to both programs. The runner checks ten named,
finite observables against the analytical solution and against the other
program with the fixture's fixed absolute tolerance. It rejects missing or
duplicate fields, non-finite output, a mismatched revision and invalid inputs.
`--self-test` exercises these guards and a deliberately altered result without
building either program. A successful full run writes machine-readable
configuration and values to `Worktree/.silex/physics3d-oracle/qualification.json`.

Jolt is used under its [MIT license](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/LICENSE).
The downloaded archive retains the license and attribution. The oracle
implements only the fixture's Jolt API calls; it does not embed Jolt into a
distributed Silex binary.

## Geometry reference cases

`GeometryFixture.json` fixes eight shape-pair cases: separated, touching and
overlapping sphere/box pairs, a sphere/sphere gap, rotated box/box gaps, and
oblique configurations. The boxes have sharp edges
(Jolt convex radius zero). Run the comparison from `Worktree/`:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/GeometryRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

The runner checks Jolt separation and ray fractions against analytical values,
then checks the Silex package's separation, normals, rays and witnesses against
Jolt and geometric invariants. Debug/Release results for both programs are
recorded in `Worktree/.silex/physics3d-oracle/geometry-qualification.json`.
Separated box faces can have many equally valid closest points; the Silex
comparison checks surface membership and separation invariants instead
of requiring identical coordinates for those witnesses. This corpus qualifies
only the listed sphere and box cases; it does not qualify a 3D physics world.

## World contact and sleep cases

`ContactRun.py` compares inelastic and elastic head-on sphere contacts with
the pinned Jolt oracle in Debug and Release. It checks outgoing velocities
and bounds positions while allowing the documented difference in when each
engine advances the response within a step.

`SleepRun.py` starts one active sphere with no gravity or damping, advances
120 steps of 1/60 second, then commands unit velocity. It compares the first
sleeping step within two steps and requires both engines to wake immediately
with the commanded velocity. The observed pinned result is step 30 in Debug
and Release for both engines. Run it from `Worktree/`:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SleepRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

These fixtures qualify their named cases, not arbitrary stacks, materials or
sleep thresholds. Results are saved under
`Worktree/.silex/physics3d-oracle/`.

## Rotated capsule against a box

`CapsuleRun.py` compares three separated, tangent and overlapping positions
of a capsule rotated 30 degrees against a sharp box. Jolt, Silex and the
analytical side-contact construction must agree within `0.0001` on separation,
normal and witness points in Debug and Release:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/CapsuleRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

This fixture qualifies the listed capsule/box feature, not all capsule pairs
or contacts during motion.

## Rigid distance and point constraints

`DistanceRun.py` compares a body suspended at a fixed length with Jolt in
Debug and Release. `PointRun.py` compares a body suspended at a coincident
anchor and a separate pendulum with an off-center local anchor. Both runs
require the pinned archive and write their measurements under
`Worktree/.silex/physics3d-oracle/`:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/PointRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

`DistanceSpringRun.py` compares four samples of a 2 Hz, damping-ratio-0.1
free oscillation against pinned Jolt in Debug and Release. Both start one
body at length 3 with target length 2 and zero gravity. The sample at 12
steps permits a 0.1-unit difference and later samples 0.05 because the
engines integrate poses at different points in the step; the measured early
values are 1.584 in Jolt and 1.669 in Silex. The fixture checks the
oscillation and decay, not identical per-step trajectories:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/DistanceSpringRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

The point fixture checks anchor error, support reaction, pendulum motion, and
the pendulum's horizontal position within 0.05 world units after two seconds.
It does not qualify every joint configuration or the per-iteration solver path.

`WorldQueryRun.py` checks that a world ray selects the near sphere even though
the far sphere was created first. It compares body identity and hit fraction
`0.25` with Jolt in Debug and Release. Consumer tests cover multiple hits,
compound child IDs, overlaps, exclusions, and retained results separately.

`SensorRun.py` checks a complete sphere passage through a fixed spherical
sensor. Both engines must emit one begin and one end, retain the overlap over
multiple steps, and leave the moving body's final position and velocity at
2 and 1 after four seconds without gravity or damping. Run it from `Worktree/`:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SensorRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

The fixture qualifies this traversal and event lifetime; consumer tests cover
mask changes, group overrides, query filtering, and recycled body identities.

## Fast linear collision and one-step sensor crossing

`ContinuousRun.py` sends a sphere from `x=-1` at 120 units/second toward a
0.1-unit wall for one 1/60-second step. Without continuous collision, the
Silex body finishes at `x=1` with no contact. With it, both engines report one
contact and stop at the near face; Jolt finishes at about `x=-0.28`, Silex at
`x=-0.30`, reflecting their different contact slop. The runner records both
Debug and Release results:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/ContinuousRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

`FastSensorRun.py` uses the same one-step speed and a spherical sensor. Both
engines preserve `x=1` and velocity 120. Pinned Jolt emits no contact event;
Silex intentionally emits a transient begin and end. The runner records this
policy difference in both modes rather than claiming exact parity.

`RotationLimit.sx` is a separate Silex diagnostic. A blade rotating 180° in
one step overlaps a fixed wall halfway through the turn but has no contact at
the endpoint. It demonstrates the documented translation-only limit; the
current continuous sweep does not claim rotation-only impacts.

## 3D world scale and contact load

`WorldScale.sx` measures only physics, with a fixed 1/60-second step and no
renderer. `sparse` places separated spheres in zero gravity, `bin` drops
spheres into a fixed floor and four walls, and `column` settles a staggered
4-by-4 tower of small boxes on a wide floor. Each run reports creation time,
total and maximum step time, contact counts, a position checksum and the
minimum body-center height. The executable rejects non-finite poses, missing
contacts in contact scenarios and bodies beyond its collision bounds.

From the workspace root or the Spec's `Worktree/` root, run the Release
campaign with the compiler selected for that checkout:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/WorldScaleRun.py \
  --silex Silex/Toolchain/zig-out/bin/silex
```

The campaign compiles once, warms six fixed workloads, then runs seven
Release processes per workload in alternating order. It verifies identical
contacts and checksums across repetitions and saves each raw result, median,
minimum, maximum and MAD to `.silex/physics3d-world-scale-campaign.json`.
The default cases are 1,024 sparse spheres; 256, 512 and 1,024 bin spheres;
and 128- and 256-box columns, each for 60 steps. Both columns must keep their
box centers above the floor guard. The campaign measures simulation time only
and makes no claim about window FPS, rendering cost or Jolt parity.

Before the column optimization, seven-run Release medians on the macOS
ARM64 host were 0.96 ms/step for 1,024 sparse spheres, 2.57/5.73/11.67 ms/step for
256/512/1,024 bin spheres, and 14.18/28.80 ms/step for 128/256 boxes. The
raw results and timing dispersion are in
`Baselines/2026-09-29-iterative-position-macos-arm64.json`. The earlier
`pre-sweep` and `sweep` records isolate the pair-search gain; the final
position solver changes contact counts and poses, so only the iterative-position record
qualifies that earlier engine revision.

### Compare the column optimization

`topple` starts from the same column, then applies an X impulse of 0.08 to
its top 16 boxes at step 60. The 240-step case covers both settlement and
motion after the disturbance. The impulse is deliberately smaller than the
interactive scene's Space impulse (0.8), which launches the light top boxes
beyond this benchmark's finite floor. Both column modes disable sleep so
the timed workload continues to solve the full population.

`ColumnCompareRun.py` compares two prebuilt Release binaries compiled from
the **same** `WorldScale.sx` source with the **same** compiler. Preserve one
binary before applying the physics change, then build the other. From the
workspace root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/ColumnCompareRun.py \
  --before .silex/column-before --after .silex/column-after \
  --silex Silex/Toolchain/zig-out/bin/silex \
  --output .silex/column-comparison.json
```

It warms both executables, alternates executable and case order over seven
repetitions, and saves binary/source/compiler hashes, every raw sample and
median/MAD statistics. It requires identical final contacts, position checksum,
minimum height and bounds across versions and repetitions. A failed run or
MAD above 5% rejects the campaign. Its two workloads are `column 256 60`
and `topple 256 240`; reported times exclude creation and rendering.

The implementation changes portable Silex geometry and solver code, with no
backend or native-provider change. Timings qualify macOS ARM64 Release only;
X64, Linux and Windows performance has not been measured.

On the measured macOS ARM64 host, the paired seven-run campaign gives:

| Workload | Before (ms/step) | After (ms/step) | Speedup |
| --- | ---: | ---: | ---: |
| Column, 256 boxes, 60 steps | 29.359 | 12.711 | 2.31× |
| Topple, 256 boxes, 240 steps | 24.306 | 11.948 | 2.03× |

The compared physics revisions are `e0dbc2d` (before) and `10096c1` (after).
Every reported non-timing observable is identical before and after, including
contact counts and the final position checksum. Raw measurements and MAD are
in `Baselines/2026-09-29-column-optimization-macos-arm64.json`. These are physics
step timings, not interactive FPS.


## Column peak, with scene sleep settings

`ColumnPeak.sx` follows the exact `StressScene column 256` setup for 600 fixed
steps (ten simulated seconds), including default sleep. It records every step's
cost, awake bodies, contacts, position checksum and minimum center height.
Unlike the short `WorldScale column` timing, this includes the collapse and
late sleep-island work. Bodies must remain finite and above y=0 within the
floor; the final minimum height must be at least 0.14. The old solver already
has transient center heights below 0.14 during collapse, which are retained
in the raw rows rather than hidden by a final-only check.

Compile a frozen baseline and candidate with the same compiler and benchmark
source, then run from `Worktree/` with no other builds or simulations running:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/ColumnPeakRun.py \
  --before .silex/column-peak-before --after .silex/column-peak-after \
  --silex Silex/Toolchain/zig-out/bin/silex \
  --output .silex/column-peak-comparison.json
```

Three alternating pairs of fresh processes preserve startup and late peaks.
The runner reports mean, p95, maximum and worst consecutive 60-step mean,
with repetition medians, MAD, binary/compiler/source hashes and raw samples.
The default requires identical non-timing observables at every step across
both versions. `--observables deterministic` instead requires exact per-version
repeatability plus the same physical bounds, for mathematically equivalent
changes that alter floating-point rounding. Use that mode only alongside
independent physical regression tests, and state the changed trajectories.
It does not assert cross-version equality or a rendered FPS improvement.
A MAD above 5% for mean, p95 or worst-60 cost rejects the campaign.

The [2026-09-29 peak campaign](Baselines/2026-09-29-column-peak-macos-arm64.json)
compares physics `10096c1` with `6419a6e`, using native compiler `fcead12`
on macOS ARM64 Release. Three alternating pairs give:

| Per-step measure | Before | After |
| --- | ---: | ---: |
| Mean | 109.13 ms | 64.63 ms |
| 95th percentile | 143.04 ms | 84.18 ms |
| Maximum (median across runs) | 158.55 ms | 94.08 ms |
| Worst consecutive 60-step mean | 132.84 ms | 82.21 ms |

This is a 40.8% mean-cost reduction; MAD is at most 2.54% for the admission
metrics. Runs are deterministic within each version and pass the same bounds;
isotropic inertia changes rounding and hence the final pile. Independent
physics tests cover rotated isotropic and anisotropic impulses, manifolds,
constraints and sleep. No compiler or backend selection changed.

The tool execution environment runs even the previously frozen binary much
slower than the earlier short benchmark campaign. These absolute timings are
therefore not directly comparable with its historical 12.71 ms or with a
foreground window's FPS. The paired campaign had no concurrent build or
other simulation started by the agent. Rendered frame rate needs its own
window measurement.

A separate [20-second window run](Baselines/2026-09-29-column-scene-macos-arm64.txt)
of example `323949d` and physics `6419a6e` measured 28.6 FPS in the initial
one-second window, then 99.0–120.7 FPS, with about 60 physical steps/s,
9.16–13.63 ms/step per reporting window and a largest observed step of
16.10 ms. The native Release scene kept rendering, shadows and 256 bodies.
These are one run's frame counts divided by measured reporting intervals,
not a repeated FPS benchmark or a guarantee for another display configuration.

To keep this diagnostic child from inheriting the agent's background priority,
it was launched with `taskpolicy -a` and moved out of `PRIO_DARWIN_BG` via
`taskpolicy -B -p <own-child-pid>`. Only that process was affected, and it was
terminated after the bounded run. No scheduler setting or scheduling code is
part of the product change. The headless paired campaign above retains its
original tool execution conditions; do not mix its absolute times with this
window run. No screenshot was captured.


## Paired column and progressive-jet qualification

`StressPeakRun.py` extends the ten-second column workload with `JetPeak.sx`:
1,024 spheres emitted at 80 bodies/s into the scene's five-wall bin, over 900
fixed steps (15 simulated seconds). The source times `world.step` only;
emission, observable checks and output are outside that interval. This is a
CPU physics benchmark, not a rendering-FPS benchmark.

Run from the workspace/group root after freezing the baseline and compiling
both configurations in Native Release. Use a separate output per scenario:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/StressPeakRun.py \
  --scenario column --before .silex/column-peak-solver-borrow \
  --after .silex/column-structural-final \
  --before-silex .silex/silex-physics-baseline \
  --silex Silex/Toolchain/zig-out/bin/silex \
  --foreground-child --output .silex/column-structural.json
```

Use `--scenario jet` and the corresponding jet binaries for the second charge.
The macOS-only foreground option changes the runner's own child processes;
it is necessary when the invoking tool inherits background priority. Keep it
identical for both versions. Do not overlap the campaign with compilation or
another simulation.

Each configuration gets one discarded warm-up, then seven fresh-process runs
in alternating order. Mean, p95, maximum and worst consecutive 60-step mean
are retained with every raw sample. Mean, p95 and worst-window MAD must each
be at most 5%. Exact mode compares awake counts, contact counts, weighted
position checksum and minimum height at every step; it does not compare each
body's complete state. Reports bind source/compiler/binary hashes and the
candidate repositories' HEADs plus tracked-diff hashes.

The progressive jet reveals an existing quality limitation: the baseline's
last minimum center height is about 0.1658 m for radius-0.2 m spheres. The cost
benchmark checks finite positions and enclosure containment, and reports
penetration separately. Passing this benchmark does **not** establish a
0.19 m minimum-center-height guarantee. Exact observable equality prevents
this optimization campaign from concealing a changed pile behind timing gains.


### 2026-09-29 structural candidate

Apple M3 Pro, 18 GiB RAM, macOS ARM64, Native Release. Seven paired fresh
processes per scenario after warm-up, identical normal child priority, no
concurrent build or simulation started by the runner. Baseline: compiler
`fcead12`, physics `6419a6e`; candidate: compiler `fd7dd83`, physics `292f340`.
All non-timing observables match exactly at every step across configurations
and repetitions. Maximum MAD across all reported metrics is 4.40%.

| Workload | Median mean ms/step | Mean-cost reduction | Median p95 ms | Worst 60-step mean ms |
| --- | ---: | ---: | ---: | ---: |
| 256-box column | 10.42 → 8.17 | 21.6% | 13.48 → 9.76 | 13.34 → 9.65 |
| 1,024-sphere progressive jet | 14.64 → 12.10 | 17.3% | 31.67 → 26.46 | 31.87 → 26.58 |

Raw [column](Baselines/2026-09-29-column-structural-macos-arm64.json) and
[jet](Baselines/2026-09-29-jet-structural-macos-arm64.json) samples retain every
step and artifact hash. These compare the cumulative compiler and broad-phase
changes, not the broad-phase change alone. The latter contributed only a small
part in exploratory isolation. The solver retains its iterations, timestep,
sleep settings and floating-point operations.

The native code generator now preserves arithmetic registers around plain
class-field transfers, distinguishes actual CFG cycles from backward inline
continuations, and removes balanced owner references around proven readers
and numeric value stores. The class/reference barriers that can change object
lifetime remain protected. [Local validation](Baselines/2026-09-29-structural-validation-macos-arm64.txt)
records the 280 physics tests and compiler check/test, optimizer gate and
qualified robustness. Distributed-target execution and sealed external
qualification remain outstanding; this host result does not establish portable
performance or full optimizer admission.

The dense jet still needs about 26.5 ms at p95. This candidate improves the
measured cost; it does not meet a 16.7 ms physics budget for every jet step.
A same-source LLVM control was roughly four times faster in exploratory runs
and retained the same aggregate observations. That control locates substantial
remaining native-code overhead; it is not a qualified cross-engine comparison,
a backend-default change, or a rendered FPS promise.


Two bounded 30-second rendered runs used the same candidate with normal child
priority. The [column log](Baselines/2026-09-29-column-structural-scene-macos-arm64.txt)
and [bin log](Baselines/2026-09-29-bin-structural-scene-macos-arm64.txt) include
all reporting windows, including startup:

- column: 114.9–120.3 FPS across 29 reported windows
- bin: 8.6–120.1 FPS across 29 reported windows

The filled bin is still unacceptable as an interactive stress demo: its late
windows reach about 9 FPS, 27–28 ms/step and four catch-up steps per frame.
The measured CPU gain is not a resolution of that rendered bottleneck. Work
continues on allocation and contact-processing cost without lowering the body
count or solver iteration count. No screenshot was captured.


### 2026-09-30 small allocations and contact traversal

Same Apple M3 Pro / 18 GiB / macOS ARM64 / Native Release configuration.
Seven paired fresh processes per scenario, one discarded warm-up per version,
alternating order and identical normal child priority. Baseline compiler
`fcead12` / physics `6419a6e`; candidate compiler `e369b1e` / physics `4cbed35`.
All per-step aggregate observables match exactly. Maximum MAD across all reported metrics: 3.44%.

| Workload | Median mean ms/step | Reduction | Median p95 ms | Worst 60-step mean ms |
| --- | ---: | ---: | ---: | ---: |
| 256-box column | 10.19 → 5.98 | 41.4% | 13.23 → 7.50 | 13.08 → 7.45 |
| 1,024-sphere progressive jet | 14.67 → 7.31 | 50.2% | 31.24 → 15.60 | 31.30 → 15.64 |

Raw [column](Baselines/2026-09-30-column-heap-contacts-macos-arm64.json) and
[jet](Baselines/2026-09-30-jet-heap-contacts-macos-arm64.json) data retain all
samples and hashes. These are cumulative gains over the retained baseline,
including the previous structural candidate; they are CPU physics times, not FPS.

The new changes reduce the initial ARM64 system-heap list reservation to
128 bytes (previously 16 KiB on macOS), retain geometric growth, cache immutable
body identities in contact snapshots, reuse previous-contact lookup results,
avoid copying warm-start points and merge ordered event snapshots linearly.
No body count, timestep, solver iteration, sleep threshold or floating operation
was changed. General inlining and inertia-function-splitting probes that did
not improve the workload were discarded.

[Local validation](Baselines/2026-09-30-heap-contacts-validation-macos-arm64.txt)
records 281 physics tests, compiler check/test, differential gate, qualified
robustness and explicit Debug/Release small-collection growth/lifetime tests.
Distributed-target execution remains outstanding; this is a macOS ARM64 result.
The baseline penetration limitation documented above remains open.


The final bounded 30-second rendered runs are retained separately:
[column](Baselines/2026-09-30-column-heap-contacts-scene-macos-arm64.txt) and
[bin](Baselines/2026-09-30-bin-heap-contacts-scene-macos-arm64.txt).
The column reports **115.6–119.5 FPS** over all 29 windows.
The progressive bin begins near 120 FPS but its last ten reporting windows
are **14.1–14.5 FPS**, with
16.40–16.83 ms/step and four catch-up steps/frame.
The late dense stage extends beyond the 900-step CPU fixture and the rendered
emitter is driven by frame time, so these are complementary workloads.

The CPU cost is substantially reduced, but the full bin is **not yet a fluid
interactive demonstration**. The remaining native solver cost and catch-up
behavior stay open; this result does not establish Unity/Godot parity. No
screenshot was captured and no renderer or simulation-quality setting was
lowered to obtain these numbers.


## Horizontal aquarium fill and settling diagnostic

`AquariumFill.sx` follows the horizontal 10 × 4 × 5 m aquarium, with 1,024
spheres emitted at 80/s, a deterministic lateral nozzle spread, and 1,800
fixed steps at 60 Hz. It checks containment each step and checks that the
final pile occupies both horizontal dimensions instead of isolated planar
stacks. Its CSV records contact and awake counts, linear/angular motion,
per-second mean step costs and the minimum center height over the entire run.
The generator uses zero angular damping as a diagnostic control.

The containment guard is distinct from the **still failing 0.19 m floor
quality gate**: transient penetration is reported rather than silently
filtered out. This scene changes the old tall-bin workload; do not compare
its numbers directly with `JetPeak` or the historical rendered bin.

```sh
silex compile Silex-Benchmarks/Sources/Physics3D/AquariumFill.sx --release \
  -o .silex/aquarium-fill
.silex/aquarium-fill
```

The sphere specialization comparison uses the same dispersed emitter and
friction reprojection on both sides. Thus the measured change isolates the
geometric fast paths, not a different fill pattern, damping or sleep threshold.
Raw measurements and binary hashes live under
[the aquarium comparison](Baselines/2026-09-30-aquarium/comparison.json).

Three balanced pairs on macOS ARM64 (Apple M3 Pro, native Release) measure
median mean cost **13.728 → 11.464 ms/step** (−16.5%) over the complete run,
and **19.636 → 16.237 ms/step** (−17.3%) over its last ten seconds.
Every sampled physical observable, including the all-step minimum height,
is identical between the corrected baseline and specialized candidate.
This is a local CPU comparison, not a rendered FPS claim or cross-platform
qualification. The full pile remains awake at 30 seconds; the settling and
floor-penetration quality issues remain open.

## Dense sphere scaling

`SpherePileScale.sx` measures 600 fixed steps at 60 Hz with 1,024, 4,096 or
8,192 initially separated spheres in an approximately eight-layer pile. The
floor area grows with the count; radius 0.2 m, gravity, zero damping and
friction 0.6 stay fixed. This is a fully populated pile, distinct from the
progressive `AquariumFill.sx` jet and from rendered FPS measurements.

From the Spec's `Worktree/` root:

```sh
Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/Physics3D/SpherePileScale.sx --release --nocache -o .silex/sphere-pile-scale
.silex/sphere-pile-scale 4096
```

CSV columns are body count, step, mean milliseconds per step over the last
60 steps, awake bodies, contacts, minimum center height over the run, current
pile height, and maximum linear speed over the run. Every step checks finite
poses and containment; the existing 0.19 m floor-height quality target remains
a separate gate. This benchmark reports penetration rather than claiming
that dense-pile quality is already qualified.

The [September 30 comparison](Baselines/2026-09-30-major-levers/README.md)
records the frozen native baseline, the sphere solver and spatial grid
candidate, raw measurements, the column control, and the rendered aquarium.
