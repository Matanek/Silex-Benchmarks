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

`RotationLimit.sx` qualifies a blade turning 180° in 1/60 second, both with pure
rotation and with parallel translation of 120 units/s. The wall is overlapped
halfway through the turn while both endpoints are separated. With linear CCD,
both engines miss contact in one step; 36 subdivisions find it in these fixtures.
This is a demonstrated limitation and a mitigation, not exact rotational CCD.
Post-impact trajectories are not required to match. Gravity, damping and
friction are zero; Jolt's angular velocity limit is 1000 rad/s.

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RotationRun.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip --mode both
```

`RotationRun.py --self-test` rejects missing, duplicate, non-finite and altered
results. The runner records all four cases per mode, source hashes, Jolt's
configuration and the pinned archive digest in `rotation-qualification.json`.

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

## Hinge qualification

`Hinge.sx` and `HingeOracle.cpp` compare free rotation with an off-axis
perturbation, weight support, mutated hard stops and a pendulum. From the
workspace or Spec group root, run:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingeRun.py --mode both
```

It uses the pinned Jolt revision, one worker and 120 steps at
60 Hz, with eight samples per case and mode. Pendulum tolerances are 0.06 m
per coordinate, 0.03 rad, 0.08 rad/s and 0.5 N over these two seconds.
After stop mutation, angle comparison allows one step at 2 rad/s (0.034 rad);
speed at the lower-stop impact sample can differ, and both implementations
must be stopped at step 120. This is bounded behavioral qualification,
without a performance or long-duration trajectory claim.


## Torque-limited hinge motor qualification

Run `python3 Silex-Benchmarks/Sources/Physics3D/HingeMotorRun.py --mode both`
from the workspace or Spec group root. `HingeMotor.sx` and
`HingeMotorOracle.cpp` compare acceleration, target/reversal/motor off,
unequal dynamic inertias, powered hard stops and a pendulum with pinned Jolt.
One worker, 120 steps at 60 Hz, eight samples per case and mode: 80 samples.
Jolt uses 12 velocity and 8 position iterations; Silex uses 12 preparatory
joint sweeps for powered worlds, 12 joint/contact sweeps and 4 position sweeps.
These are behavioral settings, not a claim of equal computational work.
The motor and its anchor reaction are solved together; the torque limit
bounds the accumulated effort over the entire step.

The guard checks analytical torque/inertia acceleration, angular momentum,
active stops and coasting after motor off. Central angle comparisons allow
0.034 rad; pendulum comparisons allow 0.04 m, 0.04 rad, 0.08 rad/s, 0.8 N and
0.2 N·m. An impact sample may differ in speed only when both angles are within
0.034 rad of the same stop and speeds remain bounded by 2.001 rad/s; both must
be arrested at steps 60 and 120. Missing, duplicate, unknown or non-finite
samples and perturbed trajectories are rejected. This is a two-second
behavioral qualification of velocity motors, without a performance, position
servo, joint friction, soft stop or long-duration claim.

## Fixed attachments

Run `python3 Silex-Benchmarks/Sources/Physics3D/FixedRun.py` from the workspace
or Spec group root. Six fixtures check a static lever, explicit rotated frames
near pi, free unequal masses, disable/enable, a loaded chain and a translating
and rotating kinematic support. Both modes qualify 48 samples with independent
force/moment and momentum guards; `--self-test` corrupts evidence to check the
guards. The pinned Jolt revision and archive checksum are shared with `Run.py`.

The v2 fixture measures equilibrium and established free/kinematic motion,
with unchanged final bounds after the initial four-second fixture exposed slow
Jolt position convergence. Sampling runs up to 27 seconds at 60 Hz. It makes no
claim of equivalent large-error correction paths or convergence times. Jolt
uses 12 velocity/4 position passes; Silex uses 12 preparation/12 shared velocity/4
position passes and resumes the previous fixed impulse. Origin-local anchors
equal COM-local anchors in these fixtures; consumer tests cover shifted centers.
Raw rows and source hashes are saved with `fixed-qualification.json`.

`HingePositionRun.py` qualifies eight position-motor cases against the pinned
Jolt reference in Debug and Release: implicit damped/oscillating trajectories,
saturation, target/mode changes, current hard limits, a loaded offset anchor,
the short path across pi and unequal free inertias. There are 192 samples per
mode over six seconds, including transients. Stiffness/damping are specified
directly in torque units; the fixture does not claim identical solver cost.
Run from the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingePositionRun.py
```

The guard self-test rejects missing, nonfinite, unknown or duplicate samples,
invalid physical bounds and perturbed trajectories. Ordinary angular/speed
comparison bounds are 0.003 rad/rad·s⁻¹; the loaded case has separate declared
bounds. At the sole sample immediately after deep hard-limit narrowing,
velocity may differ by 0.01 rad/s only if both poses are within 0.005 rad of
the new stop and both speeds are below 0.02 rad/s. This bounds a recovery phase
with different positional correction rates; it does not claim identical
recovery chronology. The qualification JSON records these bounds and sources.


`HingeFrictionRun.py` qualifies passive hinge friction at 60 Hz over six
seconds: positive/negative braking, offset inertia, unequal free bodies,
capacity mutations, motor precedence, zero-effort motor modes and static
gravity load holding/release. It checks 192 samples per Native Debug/Release
mode against pinned Jolt and independent braking/momentum/load invariants.
Run from the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingeFrictionRun.py
```

The guard rejects missing, unknown, duplicate or nonfinite evidence, effort
bound violations, friction with an installed motor and perturbed trajectories.
Ordinary pose/angle/speed bounds are 0.003; offset/load cases allow 0.01
pose/angle and 0.03 speed, with separate effort bounds in the qualification
JSON. Jolt uses 64 velocity/eight position iterations to converge separate
rows at an offset anchor; Silex uses 12 preparation/12 shared velocity/four
position passes with coupled pivot inertia. These settings and bounds are
declared before the first run; no cost or universal trajectory parity is claimed.

## Signed hinge motor torque

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingeTorqueBoundsRun.py
```

Eight cases run 360 steps at 60 Hz in Native Debug/Release, with 192 samples
per mode: positive/negative acceleration, one-sided effort and replacement,
same-sign equal bounds, offset inertia, asymmetric position control, unequal
free inertias and hard stops. Each row checks the signed effort interval and
motor priority over configured passive friction. Central trajectories and
angular momentum are also checked independently of engine comparison.

The pinned Jolt witness uses 64 velocity/eight position iterations; Silex uses
12 preparation/12 velocity/four position passes. Bounds are fixed before the
run: pose/angle/speed 0.005, motor torque 0.03 and force 0.1; the offset case
uses pose/angle 0.01, speed 0.03, torque 0.1 and force 0.2. Anchor and axis
errors stay below 0.003 and 0.002 independently. There is no phase exception
or cost parity claim. The comparator rejects missing, duplicate, unknown and
non-finite rows as well as perturbed trajectories and out-of-range effort.
Soft stops and combined position/velocity control are outside this fixture.

## Soft hinge stops

Run `python3 Silex-Benchmarks/Sources/Physics3D/HingeSoftLimitsRun.py` from the
workspace or Spec group root. The pinned Jolt oracle compares eight cases over
360 steps at 60 Hz in Native Debug/Release: damped and undamped equal bounds,
upper/lower impacts, two inertias, offset pivot, signed motor equilibrium and
spring/limit mutation with return to rigid stops. All 384 samples are compared;
implicit trajectories, unilateral effort and momentum are checked independently.
Bounds are fixed before the run; `--self-test` rejects corrupt traces.

Jolt requires angular limits to include zero. Equal positive limits are expressed
through its local normal frame and measurements are converted back to physical
angles. Impact bounds use +/-0.205 rad to avoid a floating-point equality exactly
after twelve steps. Geometry and effort bounds cover the whole trajectory, including
motion toward the opposite stop. Jolt uses 64 velocity/eight position passes;
Silex uses up to 12 preparation/12 velocity/four position passes. This is a physical
response comparison on macOS ARM64, without a cost parity claim. The oracle stays
private to benchmarks; no Jolt provider is distributed with GFX.Physics.

## Combined hinge targets

Run from the Spec group or workspace root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingeCombinedRun.py
```

Eight cases over six seconds at 60 Hz, 192 observations per Debug/Release mode:
fixed angle with velocity bias, updated sinusoidal trajectory, signed saturated
effort and reversal, position/velocity/off switches, loads on both rigid stops
with explicit pose reset, offset pivot, pi seam and two free unequal inertias.
Independent implicit recurrences and angular momentum; every sample compared.
Central bounds: .003 rad and rad/s, .03 N·m, .05 N; offset pivot: .01 rad,
.03 rad/s, .1 N·m and .2 N. Anchors .003 m, axes .002 rad. Corrupt trace and
perturbation guards are included.

The initial rigid crossing fixture exposed stop activation after integration
in Silex and before integration in Jolt. Its transient parity is not claimed;
the final oracle qualifies loads on stops, while package tests check crossing
in both directions. Soft stops, contacts, frame mutations and sleep are covered
by Physics consumers. The JSON records reference/archive and source hashes.
No cost parity: Jolt uses 12 velocity/eight position passes; Silex uses up to
12 preparation/12 velocity/four position passes.


## Free sliders and rigid stops

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SliderRun.py
```

Six cases, 240 steps at 120 Hz, every tenth step compared: 288 Debug/Release
observations. Free axial acceleration, signed loaded stops with an explicit
pose reset, unequal free bodies, a rotating kinematic rail, an offset anchor
and equal limits. Pinned Jolt rejects equal rigid slider bounds and recommends
FixedConstraint; the equal-limits witness explicitly uses that equivalent
attachment and maps its axial reaction. This does not claim that Jolt's slider
accepts equal rigid bounds.

Independent semi-implicit trajectories, initial momentum projection and
centrifugal motion guard both implementations. Predeclared comparison bounds:
.003 m/m·s⁻¹, .003 rad/s, .001 m/rad alignment, .1 N total force and .05 N stop
force. No widened bound or removed sample. Package tests separately qualify
crossing both stops, one-sided bounds, mutations, mass/COM, sleep, destruction
and real contacts. Impact-transient and general spatial-chain parity remain
unclaimed. No cost parity: Jolt uses 12 velocity/eight position passes; Silex
uses up to 12 preparation/12 velocity/four position passes.

## Slider velocity motor

Run `python3 Silex-Benchmarks/Sources/Physics3D/SliderMotorRun.py` from the
workspace or Spec group root, with the local CLI on PATH. The pinned Jolt
oracle and Silex execute six 240-step cases at 120 Hz in Native Debug/Release:
force-bounded acceleration, reversal and braking, two free unequal masses,
an offset anchor with compensating couple, steady constant relative speed on
a rotating kinematic rail, opposing rigid stops with explicit pose reset,
and a motor below the axial load. All 288 scheduled samples are compared;
independent mechanics guards qualify both traces before comparison.

Declared bounds: 0.003 m for positions, 0.003 m/s for speeds, 0.003 rad/s
for angular speeds, 0.001 m/rad for alignment, 0.1 N for world forces,
0.05 N for motor/limit forces and 0.1 N·m for the free couple. Jolt uses
24 velocity/eight position passes; Silex uses up to 12 preparation/12 velocity
and four position passes. The extra Jolt passes reduce offset-row convergence
residuals after braking. No cost parity is asserted.

Rotating-rail force transitions, rigid-stop impacts and general spatial
chains are not claimed equivalent by these steady/loaded witnesses.
`--self-test` rejects corrupted evidence, perturbed positions and invalid
independent trajectories. Sources, outputs, hashes and maximum errors are
saved under `.silex/physics3d-oracle/slider-motor-*`.

### Slider position servo

Run `python3 Silex-Benchmarks/Sources/Physics3D/SliderPositionRun.py` from the
workspace or Spec group root with the active `silex` on PATH. The pinned Jolt
oracle covers eight six-second 60 Hz fixtures: critical/weak damping,
saturation, target/velocity/off transitions, target projection onto limits,
axial/transverse load, unequal free masses and an offset anchor/free couple.
All 384 Debug/Release observations pass the independent implicit-Euler
recurrence and the unchanged slider-motor bounds: 0.003 m for positions,
0.003 m/s for linear speed, 0.003 rad/s for angular speed,
0.001 m/rad for alignment, 0.1 N world force, 0.05 N motor
and limit force, 0.1 N·m free couple. Jolt uses 24 velocity/eight position
passes; Silex uses up to 12 preparation/12 velocity/four position passes.
No cost, hard-impact, rotating-phase or general spatial-chain parity is claimed.
`--self-test` rejects incomplete/nonfinite/duplicate/unknown rows, perturbed
positions and mechanically invalid traces. Sources, hashes and outputs are
retained in `.silex/physics3d-oracle/slider-position-*`.

### Slider axial friction

Run `python3 Silex-Benchmarks/Sources/Physics3D/SliderFrictionRun.py` from the
workspace or Spec group root with active `silex` on PATH. Eight six-second
60 Hz cases compare signed braking, offset anchor/free couple, unequal free
masses, capacity mutation/coasting, motor precedence including zero-capacity
velocity/position commands, and load holding/release. All 384 Debug/Release
observations pass independent mechanics before comparison; no samples omitted.
Bounds declared before execution: 0.003 m position, 0.003 m/s linear speed,
0.003 rad/s angular speed, 0.001 m/rad alignment, 0.1 N world force,
0.05 N friction/motor/limit force, 0.1 N·m free couple. Jolt uses 24 velocity
and eight position passes; Silex uses up to 12 preparation/12 velocity/four
position passes. No cost, hard-impact, rotating-phase or general-chain parity
is claimed. `--self-test` rejects corrupted/missing/duplicate/nonfinite rows,
perturbed positions and mechanically invalid traces. Hashes, outputs and
qualification are stored under `.silex/physics3d-oracle/slider-friction-*`.

### Signed slider motor force bounds

Run `python3 Silex-Benchmarks/Sources/Physics3D/SliderForceBoundsRun.py` from
the workspace or Spec group root with active `silex` on PATH. Eight six-second
60 Hz fixtures compare asymmetric/one-sided reversal, equal and same-sign
imposed effort, offset anchor/free couple, signed clamped spring, unequal free
masses, load and velocity/position/off mutation restoring friction. All 384
Debug/Release observations pass independent mechanics before comparison.
Bounds declared before execution: 0.003 m position, 0.003 m/s linear speed,
0.003 rad/s angular speed, 0.001 m/rad alignment, 0.1 N world force,
0.05 N motor/friction/limit force, 0.1 N·m free couple. Jolt uses 24 velocity
and eight position passes; Silex uses up to 12 preparation/12 velocity/four
position passes. No cost, impact, rotating-transient or general-chain parity
is claimed. `--self-test` rejects corrupted/missing/duplicate/nonfinite rows,
perturbed positions and mechanically invalid traces. Sources, hashes and
qualification are stored under `.silex/physics3d-oracle/slider-force-bounds-*`.

## Slider soft stops

`SliderSoftLimitsRun.py` qualifies eight six-second trajectories at 60 Hz:
damped and undamped bilateral springs, unilateral overshoot both ways,
unequal free masses, an offset anchor, signed motor compression and spring/
limit mutations under load. Both traces pass independent mechanics before
comparison: 384 observations across Debug/Release, all at the declared bounds.
Maximum difference: 2.35e-7 m, 8.95e-7 m/s, 6.68e-6 N limit/world force and
1.08e-6 N m free couple. Pinned Jolt uses 24 velocity/eight position passes;
Silex uses 12 preparation/12 velocity/four position passes. No hard-impact,
rotating-phase, general-chain or cost parity claim.

From the workspace or isolated Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SliderSoftLimitsRun.py
```

### Combined slider position and velocity

Run `python3 Silex-Benchmarks/Sources/Physics3D/SliderCombinedRun.py` from the
workspace or Spec group root. Eight cases compare fixed/moving targets, signed
saturation, mode mutations, equal soft stops, load, unequal free masses and
offset anchors against pinned Jolt and an independent recurrence. Native
Debug/Release each retain all 192 samples. Bounds are fixed before execution;
`--self-test` rejects malformed, missing, duplicated, nonfinite and perturbed
evidence. No hard-impact, rotating-rail or spatial-chain parity or cost claim.

## Path guidance

Run `python3 Silex-Benchmarks/Sources/Physics3D/PathRun.py` from the Spec
group (or use `--self-test` for evidence guards). Fourteen cases run for
120 steps in Debug and Release: 108 sampled observations per mode compare
line guidance, drives, friction, orientations, a rotated frame and a free
loop; 18 observations retain two measured reference boundaries. On a 2m
segment the pinned position servo scales its error by segment fraction.
Curved follow mode omits angular frame transport from velocity. Independent
metric-servo recurrence and curvature/inertia witnesses qualify those Silex
behaviors. They are not included in a false all-case parity claim.

## Loaded spatial hinge

From the workspace or Spec worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/LoadedHingeRun.py --mode both
```

Seven cases retain every step at 60/120 Hz: gravity/free motion, floor
present/absent, offsets ±1 m and centered, speed reversal at 1.5 s.
The sphere mass is automatic (density 1, radius 0.5), with a 2 kg payload
and isotropic inertia 0.2. The whole run checks anchors, angular attachment
error and the per-step motor budget. Comparison with pinned Jolt is limited
to 2.5–3 s with the original numeric bounds, and the final free-motion
sample checks complete pivot inertia analytically. The report retains the
rejected full-trajectory comparison and its maximum errors; initial
correction and contact phase parity are not claimed.

## Rack servo with finite stroke

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RackServoRun.py
```

Run from the workspace or Spec group root. Three fixtures at 60/120 Hz use a
hinge, slider and rack transmission with 12 N·m, stiffness 15 and damping 8:
historical ±2 rad against rail ±1.1 m, reachable free ±1.5 rad, and ±1.5 rad
against rail ±0.6 m. Jolt explicitly binds its rack position correction to the
hinge and slider. Bodies do not collide; mass is 2 kg and inertia 0.4 kg·m².

Debug/Release retain every step, fixed comparison tolerances and independent
finite-step advance, torque/speed and static reaction checks. The original
all-step phase limit 0.002 rad remains rejected for historical 120 Hz and
rail-stop 60 Hz in both engines. Full trajectory comparisons retain their
failures for those cases; all settled samples after 2.5 s per command pass the
same comparison bounds. Other cases have full trajectory parity within the
recorded bounds. The manual rail-stop recipe uses 120 Hz. No general spatial
chain or exact contact-phase claim follows from this qualification.

## Hinge stop impulse and activation

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingeImpactRun.py
```

Run from the workspace or Spec group root. Seven recipes at 60/120 Hz and both
signs retain 6120 observations per engine and Native Debug/Release mode:
center approach, off-grid near-stop approach, initially active stop, release,
free-axis control, motor-only control and driven stop reversal at three seconds.
The fixed-pivot rotor has mass 1 kg, axial inertia 0.1 kg·m², no gravity,
damping, sleep or collisions. Stops are ±0.3 rad; the position motor requests
±0.8 rad with 10 N·m, stiffness 1.6 and damping 0.08.

Every step checks `I Δω = λ_motor + λ_limit`, dissipative stop work, motor
budget, frame errors and a bound based on free advance. The passive cases
also verify immediate active-stop braking, release and final rest. Motor-only
angles and speeds are compared within 0.0001; 11 corrupt witnesses must fail.
All output, first stop impulses and before/after states are retained. Phase
parity is not claimed: Silex anticipates stops and reevaluates after movement;
Jolt activates from the beginning-of-step angle. Driven rest below 1e-5 rad/s
after three seconds is reported separately and remains unqualified; Jolt can
retain about 7.28e-5 rad/s at 120 Hz. Original rigid-impact comparison failures
and tolerances remain unchanged.

## World impulses on a rotating rail

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RotatingRailRun.py
```

Run from the workspace or Spec group root. A 2 kg carriage starts 1 m from
the origin, on a kinematic rail rotating at 0 or ±0.2 rad/s. At 60/120 Hz,
free and force-bounded motor recipes retain 2160 observations per engine and
Native Debug/Release mode. The motor requests 0.6, -0.6 and 0 m/s, with 2 N
capacity, over two seconds. There is no gravity, damping, friction or collision.
Jolt uses 24 velocity and 8 position passes for the oracle; no iteration-cost
parity is claimed.

Every step checks world impulse against `mass * velocity_change`, motor
capacity and frame geometry. The fixed driven case follows a bounded velocity
recurrence; the free rotating case follows `r=cosh(omega*t)` and
`radial_speed=omega*sinh(omega*t)`. A kinematic rotating support supplies work,
so carriage energy alone is not conserved. Thirteen corrupt witnesses must fail.

Jolt's local multipliers are converted with the beginning-of-step frame in
which its rows applied impulses. A separate final-frame projection is retained
as a negative witness: it does not reproduce the applied world impulse.
Silex directly accumulates world impulses across its passes. All raw rows and
fixed mechanical tolerances are preserved. The original 0.05 N effort parity
gap at 120 Hz step 70 remains rejected; the report includes every additional
phase gap in the expanded matrix. Neither a solver change nor phase parity is
claimed.

## A hinged dynamic rail carrying a moving carriage

```sh
python3 Silex-Benchmarks/Sources/Physics3D/HingedRailRun.py
```

Run from the workspace or Spec group root. The rail is dynamic, fixed at its
center by a Z hinge: mass 2 kg, isotropic inertia 0.4 kg·m². A radial carriage
starts at 1 m with mass 1 or 2 kg and isotropic inertia 0.2 kg·m². Both start
at ±0.2 rad/s with consistent tangential velocity. The slider requests 0.6,
−0.6 and 0 m/s, switching after 2/3 and 4/3 s, with capacity 2 N. The hinge
is free or requests its initial speed with capacity 0.4 N·m. Sixteen recipes
at 60/120 Hz over two seconds produce 2880 observations per engine and
Native Debug/Release mode. Gravity, damping, sleep, friction, stops and
collisions are disabled. Jolt uses 24 velocity and 8 position passes;
Silex uses its existing preparation, contact sweep and position passes.

Each step checks carriage and total world linear impulses, carriage spin
impulse, both motor budgets, frame geometry and state continuity. Total angular
momentum includes spin and orbital terms for both dynamic bodies. Its change
matches external hinge motor torque within 0.0001 N·m·s per step and
0.002 N·m·s cumulatively; integration, anchor errors and pose corrections affect orbital momentum.
The free rail slows as radius grows; the driven rail recovers its target.
Radial reversal and final stopping must occur. Twenty corrupt witnesses per
engine must fail. World and spin impulse tolerances are 2e−6 N·s or N·m·s.

Jolt's slider force uses the frame in which impulses were applied, captured
before the step. Both engines independently satisfy the same mechanical
bounds. Transient scalar torques and forces differ: all raw outputs and measured
phase differences are retained, without phase or cost parity claims. This
planar witness does not replace qualification of spatial chains or contacts.

## A held rail under gravity with axial contact and release

```sh
python3 Silex-Benchmarks/Sources/Physics3D/LoadedRailRun.py
```

Run from the workspace or Spec group root. A dynamic rail (2 kg, isotropic
inertia 0.4 kg·m²) is held at its center by a Z hinge requesting zero rad/s
with capacity 30 N·m. The spherical carriage (radius 0.25 m, mass 1 or 2 kg,
inertia 0.2 kg·m²) starts at rest at X=±1 m. Gravity is −9.81 Y. Its slider
requests ±0.6 m/s outwards, reverses after 2/3 s, and brakes at zero after
4/3 s, with capacity 2 N. An optional inward-facing plane at signed X=1.4 m
stops the carriage near signed X=1.15 m. Only carriage–wall collisions are
enabled. Friction, restitution, damping and sleep are disabled; there are no
joint stops. Two masses, two sides, 60/120 Hz and wall/no-wall give 16 recipes,
2880 observations per engine and Native Debug/Release mode. Jolt uses 24
velocity and 8 position passes; Silex's existing passes remain unchanged.

Each step checks rail impulse, carriage spin, geometry, motor capacities,
horizontal holding and continuity. Vertical carriage impulse is checked in
both engines. Silex also independently checks full carriage impulse against
measured contacts. Jolt does not publicly expose post-solve contact impulses:
the normal impulse is inferred, labelled with `measured=0`, and is not used
to validate its own normal balance. `WereBodiesInContact` independently
confirms contact. A wall recipe must produce contact with an impulse over
0.1 N·s, reverse and release it; erasing contacts must reject the witness.
At final rest, reactions must carry the weights and hinge torque must balance
their signed moment arms, including the rail's small positional error.

Frozen bounds: linear/spin impulse 1e−5 N·s/N·m·s; geometry 0.003 m/rad;
angle 0.02 rad; final linear/angular speed 0.005 m/s/rad/s; final gravity
force/torque error 0.05 N/N·m; penetration 0.003 m. Twenty-one corrupt
witnesses per engine and mode must fail. Raw traces, provenance flags and
transient differences are retained. Contact timing and inferred/measured
normal impulses are not claimed identical. This planar qualification does
not establish phase parity, equal solver cost or general spatial chains.

## Loaded spatial chain with perpendicular hinges

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SpatialHingesRun.py
```

Run from the workspace or Spec group root. A fixed pivot holds an arm of
mass 2 kg and isotropic inertia 0.4 kg·m², centered at (0.5,0,0), through
a Z hinge at the origin. An X hinge at (1,0,0) attaches a payload centered
at (1,0,±0.8), mass 1 or 2 kg and isotropic inertia 0.2 kg·m². Initial
rotations are identity and velocities zero; gravity is −9.81 Y. Both motors
hold zero speed with capacities 60/40 N·m, or the second requests ±0.2 rad/s,
reverses after 2/3 s and brakes after 4/3 s. Two masses, offsets, rates
60/120 Hz and modes give 16 two-second recipes, 2880 observations per engine
and Native Debug/Release mode. Collisions, damping, sleep and stops are
disabled. Jolt uses 24 velocity/8 position passes; Silex passes are unchanged.

Every step checks each body's linear impulse and spin impulse including
anchor-force moments. Total world angular momentum includes spin and orbital
terms for both bodies and integrates pivot torque and gravity moments. The
pivot torque includes locked X reaction as well as Z motor effort. Jolt's
rotation multipliers use the basis from pinned HingeRotationConstraintPart:
`b = axis2.GetNormalizedPerpendicular()`, `c = axis2.Cross(b)`, applied torque
`(b.Cross(axis1)*lambda[0] + c.Cross(axis1)*lambda[1] + axis1*motor)/dt`.
Axes come from pre-step poses, where velocity impulses were applied, rather
than the end pose after position correction. End-pose angles, axes, anchors
and relative speed are independently reconstructed and checked.

Frozen bounds: linear impulse 1e−5 N·s; spin and total angular impulse
0.001 N·m·s per step; total angular residual 0.01 N·m·s cumulatively;
geometry 0.005 m/rad; root/held angles 0.02 rad; final speed 0.005 m/s/rad/s;
final weight/torque error 0.05 N/N·m; motor projection error 0.01 N·m.
Driving must exceed 0.08 rad and reverse beyond ±0.15 rad/s. Nineteen corrupt
witnesses per engine/mode must fail. Raw traces and transient differences
are retained. Both engines satisfy the same mechanical bounds independently;
no phase/cost parity, exact discrete conservation or spatial-contact claim.

## Spatial hinge chain contacting and releasing a floor

```sh
python3 Silex-Benchmarks/Sources/Physics3D/SpatialContactsRun.py
```

Run from the workspace or Spec group root. The perpendicular Z/X chain above
uses a payload sphere of radius 0.15 m and an optional infinite floor at
Y=−0.22 m. Only payload-floor collisions are enabled; friction, restitution,
damping, sleep and stops are absent. Both modes drive the second motor,
reverse at 2/3 s and brake at 4/3 s. Two masses, signed offsets, rates 60/120
and floor/no-floor yield 16 recipes, 2880 rows per engine/mode. Native
Debug/Release checks 11 520 observations and rejects 28 corrupt witnesses
per engine/mode, including erased contacts, motion, points and lever arms.

Silex contact snapshots provide solved impulses and the fresh midpoint.
The sphere-plane lever is vertical `(0,-radius-separation/2,0)` at the
contact solve; end poses may already include corrections. Jolt's listener
captures the pre-solve midpoint of its two surface witnesses and its lever
to the payload center, matching pinned ContactConstraintManager. Cached
contacts may produce a small noncentral lever. Its normal impulse is inferred
from payload momentum and hinge impulse: no independent normal or contact
angular balance claim. Both spin and total angular balances include the actual
contact moment; Jolt's inference remains labeled in the qualification file.

Frozen bounds: linear impulse 1e−5 N·s; spin 0.001 N·m·s; total angular
impulse 0.003 per step, 0.03 cumulatively; geometry 0.005 m/rad; root angle
0.02 rad; penetration 0.003 m; final speed 0.005 m/s/rad/s; final weight and
torque errors 0.05 N/N·m; motor projection 0.02 N·m. Contact paths require
peak impulse >0.1 N·s, excursion >0.07 rad, both speed signs beyond 0.15
rad/s and released contact at final rest. Reaction budgets remain 60/40 N·m.
Raw traces and phase differences are retained; no threshold is widened to
fit output. These bounds include integration and pose corrections without
claiming exact discrete conservation, phase/cost parity or arbitrary chains.

## Sustained spatial contact pressure

Run `python3 Silex-Benchmarks/Sources/Physics3D/SustainedSpatialContactsRun.py`
from the workspace root or the owning Spec group. Two perpendicular hinges carry
a sphere against a horizontal floor for three seconds: 16 recipes with/without
the floor, masses 1/2 kg, offsets ±0.8 m, steps 60/120 Hz, zero friction and
restitution. Root velocity is zero with 60 N·m capacity; secondary velocity is
±0.2 rad/s with 40 N·m capacity, braking only near the free target ±0.2 rad.
The floor must stall motion near ±asin(0.07/0.8); no floor must reach the target.
Native Debug/Release Silex and pinned Jolt retain the previous impulse, spin,
angular momentum, geometry and penetration bounds. Final force and torque
balances include the floor; 28 corrupted witnesses are rejected per engine/mode.
Jolt normal impulse remains inferred and is not an independent contact-force
proof. This does not claim arbitrary-chain, phase or cost parity.

## Spatial hinge with a vertical slider

Run `python3 Silex-Benchmarks/Sources/Physics3D/SpatialRailRun.py` from the
workspace root or owning Spec group. Sixteen two-second recipes combine a held
Z hinge with a vertical Y slider, payload masses 1/2 kg, lateral offsets ±0.8 m,
steps 60/120 Hz and with/without a frictionless floor. Root capacity is 60 N·m;
slider capacity is 40 N, speed −0.2 m/s, reversal at 2/3 s and braking at 4/3 s.
Vector balances retain the spatial-contact bounds, moving-point slider lever,
measured contact points and inferred Jolt normal impulse. Minimum descent is
0.07 m with the floor or 2/15 m without it, within 0.005 m. Contact must release,
final reactions support weight, and 28 corrupted witnesses are rejected per
engine/mode. No arbitrary-chain, phase or cost parity claim.


## Simultaneous loaded swing/twist servos

Run `python3 Silex-Benchmarks/Sources/Physics3D/LoadedSwingTwistRun.py` from the
workspace or Spec group root. The offset body has mass 1/2 kg, isotropic
inertia 0.4 kg·m², gravity −9.81 Y, rotated body and constraint frames, and
30 N·m motor budgets. Three position targets reverse after three seconds and
recenter after six; eight recipes run for nine seconds at 60/120 Hz.

The runner checks full state coverage and continuity, quaternion geometry,
world force and angular momentum balances, anchors, motor budgets and projection,
reversal and finite-spring equilibria. Steady states are compared against the
pinned Jolt witness at the end of each phase; transient differences are measured
without claiming equality. Each engine/mode rejects 15 corrupted witnesses.
No contact, mixed dynamic chain or performance result is claimed.

Jolt resolves its point lever before pose advancement. Silex resolves before
and after it. The runner qualifies a single-lever local spin balance only in
Jolt, and the full world angular momentum balance in both engines. An additional
split-phase Silex diagnostic confirmed the original 0.001 local-spin bound with
unchanged normal outputs; it is preserved in the Spec evidence. Applying the
entire averaged force at one initial lever is an invalid local-spin witness.

## Articulated shoulder and elbow pose

Run `python3 Silex-Benchmarks/Sources/Physics3D/ArticulatedPoseRun.py` from
the workspace or Spec group root. Eight twelve-second recipes combine a
three-axis swing/twist shoulder with a position-driven Z hinge elbow, upper
mass 2 kg, lower mass 1/2 kg, isotropic inertias 0.4/0.2 kg·m², offset anchors,
rotated frames and gravity −9.81 Y. Targets reverse at four seconds and recenter
at eight seconds, at 60/120 Hz. Budgets are 60 N·m per shoulder axis and 40 N·m
at the elbow. No contacts participate.

The runner checks continuity, geometry, per-body linear momentum, per-step
world angular momentum residual, motor projection and budgets, reversal and
finite-spring equilibria. Each engine/mode rejects 28 corrupted witnesses.
Steady states are compared with pinned Jolt; transient differences are measured.
Jolt additionally checks per-body spin with its single pre-pose lever. Silex
requires the separate split-phase spin diagnostic retained in the Spec.
The raw cumulative world residual is measured, with no exact-conservation claim:
the initial 0.03 bound was disproved by Jolt too and remains preserved. No
threshold was enlarged to hide the moving-hinge torque defect. Public motor
projection and steady parity bounds remain those defined before the correction.

## Ragdoll hierarchy and poses

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollHierarchyRun.py` from
the workspace or Spec group root. A three-part hierarchy with noncommuting
quarter turns and rotated body offsets is instantiated twice, then moved to
a second root pose. Both engines check twelve joint/body pose rows against
closed-form positions and quaternion compositions. Jolt uses its native
`RagdollSettings`, skeleton and `Ragdoll.GetPose/SetPose`; its shape origins
are converted to joint frames using the known offsets.

Two overlapping Silex sensor assemblies expose one permitted internal pair
and nine pairs across instances. These counts are compared with the actual
Jolt ragdoll collision-group permissions. This is a filtering witness, not
a contact-dynamics parity claim. Both native modes also exercise Silex world
lifetime, repeated destruction and analytical free fall at 60/120 Hz.
Each engine/mode rejects twenty corrupted pose or filter witnesses.
