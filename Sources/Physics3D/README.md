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

## Ragdoll impulse and symmetric floor impact

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollDynamicsRun.py` from
the workspace or Spec group root. Three spheres (radius 0.25 m, mass 2 kg,
isotropic inertia 0.2 kg·m²) are joined at their midpoints with free swing/twist
constraints; internal collisions and damping are disabled. An off-center
±3 N·s Z impulse acts on the last member in a gravity-free world for 0.5 s.
A separate symmetric fall starts at 3 m and runs for two seconds on a
frictionless floor. Jolt uses its native Ragdoll and a box whose top is at zero;
Silex uses an infinite plane. Rates are 60/120 Hz in Native Debug/Release.

Both engines independently check the initial impulse, linear momentum, bounded
angular momentum drift, transmission to the root, anchors and floor rest.
The impact envelope allows one step of travel at 7.5 m/s plus Jolt's default
2 cm penetration slop; the final height remains 0.22–0.28 m with speed below
0.05 m/s. Each engine/mode rejects 24 corrupted observations. This qualifies
these two passive recipes, without claiming identical contact trajectories,
general ragdoll impacts, active limits or motorized pose tracking.

## Ragdoll pose motors

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollMotorsRun.py` from the
workspace or Spec group root. A fixed root and two sphere bodies (radius 0.5 m,
mass 1 kg, isotropic inertia 0.2 kg·m²) have rotated body offsets, noncommuting
rest rotations and gravity −9.81 Y. Each 13-second recipe follows one target,
reverses at four seconds, returns to neutral at eight seconds and releases
motors at twelve seconds, at 60/120 Hz. Both worlds use 12 velocity and
16 position iterations; no contacts participate. Motors use 120 N·m per axis,
400 N·m/rad stiffness and 40 N·m·s/rad damping.

The witness contains 9,368 rows per engine/mode. Independent reconstruction
checks body offsets, joint rotations, relative angular speeds and anchor gaps.
Anchor, settled target error and final speed bounds are 2 cm, 0.08 rad and
0.15 m/s or rad/s respectively. Torques stay within their budgets and vanish
after release; the passive chain must move again. Each engine/mode rejects
32 corrupt witnesses. The final half-second of each powered phase is compared
with native Jolt `Ragdoll.DriveToPoseUsingMotors` (orientation 0.03 rad,
position 5 cm, relative angular speed 0.05 rad/s). This qualifies these settled
poses, without claiming contact or full transient trajectory parity.

## Passive ragdoll twist stops

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollLimitsRun.py` from the
workspace or Spec group root. The controller verifies the pinned Jolt archive,
compiles both native engines in Debug/Release and checks every observation of
a free three-sphere chain. Each body has mass 2 kg and isotropic inertia
0.2 kg·m²; swing is locked, twist lies in −0.2/+0.35 rad. A ±0.6 kg·m²/s angular
impulse on the last member is reversed after two seconds. There is no gravity
or contact. The cases run at 60/120 Hz, in two world orientations and both signs.

The native Jolt witness uses `RagdollSettings` and `Ragdoll`, with parent frames
derived from the same rest geometry. Every output contains 8,712 rows, including
poses and velocities immediately before/after both impulses. Independent checks
cover angular momentum (0.0001 kg·m²/s), stepwise kinetic energy increase
(0.0001 J), anchor/axis geometry (0.001 m/rad), both reached stops (0.02 rad),
and settled velocity (0.01 rad/s). Transient twist crossing is bounded by one
step at the initial relative speed of 3 rad/s plus 0.005 rad. Settled twist
angles and world angular velocity components are compared within 0.02 rad/rad/s.
Parser, mechanics, event timing and parity guards reject corrupted witnesses.
The controller also supports `--check-only` to recheck retained outputs.
This qualifies an axial passive stop composition, without claiming identical
transient impact trajectories, combined swing or floor contacts.

## Bounded ragdoll targets against a floor

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollContactRun.py` from the
workspace or Spec group root. A fixed root anchors a 2 kg sphere with radius
0.25 m, isotropic inertia 0.2 kg·m² and a 1 m offset. Under gravity, three
combined swing/twist targets exceed the circular 0.6 rad cone and asymmetric
−0.2/+0.35 rad twist stops. They press downward, lift, then return; after
12 seconds motors stop and the member receives a 0.2 kg·m²/s angular impulse.
Each run lasts 14 seconds. Torque is bounded at 30 N·m per axis, stiffness is
80 and damping 15. Floor/no-floor cases, two horizontal orientations, both
lateral signs and 60/120 Hz produce 20,304 observations per native engine/mode.

Silex uses 16 position passes. Native Jolt uses 12 velocity and 16 position
passes, one substep/worker, default warm start and penetration slop 1e−6 m to
compare the same contact surface height. There is no body damping, sleeping,
friction or restitution. Jolt's normal impulse is inferred from linear momentum
and joint reaction; Silex's measured contact impulse is independently checked
against that balance (0.0002 kg·m/s). A projected angular balance in established
contact windows checks the vertical joint force independently of the inferred
normal (0.0002 kg·m²/s); twist limit torque has no component on the floor
tilt axis, and swing remains inside its cone. Every step checks geometry, anchor error
(0.02 m), limit excess (0.08 rad), penetration (0.02 m) and torque (30.001 N·m).
Commands preserve poses/velocities except the declared angular impulse.

The last half-second before each 4/8/12 second command is fixed in advance.
Geometry is compared at every observation within these windows (0.04 rad,
0.05 m). Relative angular velocity vectors are averaged (0.05 rad/s); joint
and normal impulses are summed and divided by the covered duration (1 N).
Instantaneous velocity/force comparison fails near simultaneous active stops
and remains an explicit diagnostic in the qualification JSON. Increasing Jolt
velocity iterations did not remove that difference. Passing window averages
does not establish instantaneous reaction, arbitrary impact or trajectory parity.
Parser, mechanics, command timing and window-comparison guards reject corrupt
witnesses. `--check-only` rechecks retained outputs. The package consumer also
tests independent instances and recreation.

## Free ragdoll combined stops

Run `python3 Silex-Benchmarks/Sources/Physics3D/RagdollCombinedLimitsRun.py`
from the workspace or Spec group root. Three free 2 kg spheres of radius
0.25 m and isotropic inertia 0.2 kg·m² form a two-joint chain with a
0.3/0.45 rad elliptical swing cone and −0.2/+0.35 rad twist limits. The leaf
receives an oblique ±(0.2, 0.3, −0.2) kg·m²/s angular impulse at zero and its
opposite at two seconds. Each case lasts four seconds, with 60/120 Hz, two
world orientations and both signs. There is no gravity, collision, motor,
sleeping or damping. Silex uses 16 position passes; Jolt uses 24 velocity
and 16 position passes, one substep and a single-threaded job system.

Each native engine/mode emits 8,712 observations, including actual before/after
impulse snapshots. The controller independently reconstructs relative swing,
twist and anchors. Budgets are 0.01 m anchor error, 0.08 rad angular excess,
0.0001 kg·m/s linear momentum, 0.02 kg·m²/s angular momentum and 0.001 m
center drift. Passive kinetic energy may increase by at most 0.001 J per step
and 0.005 J from the phase's post-impulse state. Impulse work is checked
separately. Both joints exercise both swing directions, their cone and both
twist stops across the complete case set.

Windows [1.5, 2) and [3.5, 4] seconds compare center/momentum within these
same bounds and mean kinetic energy within 0.05 J. This qualifies global
physical balances, without claiming equal individual poses or velocities
at every limit impact. Parser, mechanics, impulse timing and parity guards
reject corrupted witnesses; `--check-only` rechecks retained outputs. The
public package consumer also checks an unaffected second instance and
destruction/recreation. General external contact composition remains open.

## Mobile ragdoll motors with floor departure and return

`RagdollMobileContactRun.py` compares three freely moving spheres, two clamped
planar swing targets and a frictionless floor. Both joints use a 0.6 rad cone
and −0.2/+0.35 rad twist bounds. The spheres have radius 0.25 m, mass 2 kg and
isotropic inertia 0.2 kg·m²; centers initially lie at X=0/1/2 m and Y=1 m,
with midpoint anchors. There is no body damping, restitution, sleep or
internal collision. Gravity is −9.81 m/s² along Y. Motors use 30 N·m per axis,
stiffness 80 and damping 15.

After a passive fall, the chain receives neutral targets at 2 s, opposing
±0.8 rad swing targets at 4 s, reversed targets at 7 s, then motor release
and a 4 N·s upward impulse on each sphere at 10 s. The run ends at 12 s.
Commands preserve every body pose and velocity, except the declared +2 m/s
vertical launch. There are eight configurations: 60/120 Hz, both target signs
and world yaw 0/0.7 rad.

From the Spec's `Worktree/` root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RagdollMobileContactRun.py --mode both
```

Silex explicitly selects 48 velocity iterations per stage and 16 position
passes; Jolt uses 24 velocity iterations, 16 position passes, one substep,
one worker, normal warm starting and 1e−6 m penetration slop. Silex has two
velocity-solving stages within each timestep. These budgets do not imply
equivalent algorithmic work. Default Silex worlds retain 12 velocity iterations.
The initial witness at 12 was rejected: mean anchor reactions differed by up
to 1.468 N against the fixed 1 N bound despite close geometry. Increasing only
position passes did not change the output; velocity convergence required the
explicit larger budget. The rejection and convergence experiments are retained
in the Spec's Task114 evidence. No performance result is claimed.

Every step checks anchors below 0.02 m, penetration below 0.02 m, angular excess
below 0.08 rad, motor torque below 30.001 N·m per axis, finite velocities below
40 and reconstructed frames within 0.0001. Individual horizontal impulse
balances and measured Silex floor impulses have a 0.0002 kg·m/s residual bound.
Global horizontal momentum, horizontal centroid and vertical angular momentum
are bounded; a global angular balance uses the individual normal impulses.
Jolt's normals are inferred from individual linear balances using its public
anchor reactions, while Silex's are measured. The two provenances stay explicit.

The fixed half-second windows preceding 4/7/10 s compare relative orientations
within 0.04 rad, centroid-relative positions within 0.05 m, mean angular velocity
vectors within 0.05 rad/s, mean anchor forces within 1 N and total mean floor
force within 1 N. Both engines must detach every member during 10.15–10.3 s and
regain floor contact during 11.5–12 s. Per-step forces and impact trajectories
are not compared or declared equivalent. Corruption guards reject missing,
duplicate, nonfinite, inconsistent and altered observations. Results are written
to `.silex/physics3d-oracle/ragdoll-mobile-contact-qualification.json`.


## Spatial ragdoll motors on triangular supports

`RagdollSpatialContactRun.py` extends the mobile-contact recipe with a second
constraint frame yawed by 0.6 rad and body centers (0,1,0), (1,1,0), (1.7,1,0.7)
m. Anchors lie at the midpoints. Body offsets preserve initial body rotations
while the constraint axes differ. Jolt SkeletonPose rotations describe bodies;
the Silex ragdoll pose describes joint frames, so their conversion is explicit.

Each target is swing*twist. At 4 s, the first joint requests 0.4*sign rad around
(0,0.6,0.8) and 0.15*sign rad twist; the second requests -0.4*sign around
(0,0.8,0.6) and -0.12*sign twist. Targets are neutral at 2 s and reversed at
7 s. Motors stop at 10 s: each body receives (0,4,0) N·s and the leaf also
receives (1.2*sign,0,2) N·s rotated by the initial world yaw. The run ends
at 12 s. All other geometry, material, solver and motor settings match the
mobile-contact recipe above. Eight configurations cover 60/120 Hz, both signs
and yaw 0/0.7 rad, in native Debug/Release on macOS ARM64.

From the Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RagdollSpatialContactRun.py --mode both
```

The same numerical bounds apply, with angular balance measured about the center
of mass (0.02 kg·m²/s per step). Global Y angular momentum, horizontal momentum
and horizontal centroid account for the declared oblique impulse. Silex normal
impulses are measured; Jolt normals are inferred from individual linear balances.
A projected vertical position correction changes orbital momentum about a fixed
origin when the group moves horizontally, so equivalence of that orbital balance
at impacts is not claimed.

In the half-second windows preceding 4/7/10 s, both engines must settle below
0.15 m/s and rad/s. Geometry is compared after centering and expressing it in
the root body's frame; mean angular velocity and anchor reaction vectors use
the same frame. Bounds remain 0.04 rad, 0.05 m, 0.05 rad/s and 1 N, with total
mean normal force within 1 N. Each joint must exercise twist above 0.03 rad
and both swing quaternion components above 0.025. Contact departure/return,
commands that do not place bodies and 42 evidence-corruption guards are checked.

The initially collinear support was rejected: both engines retain a slow mode
in the proposed resting windows. Its evidence is retained in the Spec; passing
the triangular fixture does not qualify that rejected fixture. There is no
performance comparison or general trajectory/impact claim. Results are stored
in `.silex/physics3d-oracle/ragdoll-spatial-contact-qualification.json`.


## Cylindrical wheel contacts and width

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleCylinderContactsRun.py --mode both
```

The real pinned Jolt `VehicleCollisionTesterCastCylinder` uses sharp cylinders
(convex radius fraction zero). Each engine/mode emits 42 geometric contacts
and 2,164 dynamic states at 60/120 Hz: width reach/miss, corner, camber,
steering, transformed/inclined faces, filters, compound and initial overlap,
then flat-floor jump and four wide wheels on a narrow support. The 100 kg
chassis has isotropic inertia 100, no damping/sleeping, four radius-.3 m,
width-.4 m wheels at x=±.6/z=±1, lengths .2/.6 m and springs 10000/1000;
both engines use 12/4 iterations, one worker and no substeps.

Tolerance: geometry/boundaries 2e-4, position .01 m, velocity .05 m/s,
quaternion .005, suspension .01 m, impulse balances .05 N·s/N·m·s, rest
height .002 m and mean weight 1 N. Contact-line points need not be identical:
each is checked on both boundaries. Angular velocity compares fixed
quarter-second means at .05 rad/s; instantaneous landing differences are
retained and not qualified. All per-step balances use actual observed points,
normals and forces. Jolt’s rotated infinite-plane point is off-plane; an
equivalent tilted box proves the physical point. Jolt’s sharp-corner normal
has about .011 radial error; Silex’s analytic normal and both contact
boundaries remain checked at the original tolerance. The raw Jolt value is
retained without claiming normal parity for that corner. Missing, duplicate,
non-finite and channel-corrupted witnesses must be rejected. No FPS or whole
vehicle-family qualification is implied.


## Paired anti-roll suspension bars

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleAntiRollRun.py --mode both
```

The pinned Jolt VehicleConstraint couples two disjoint wheel pairs after
contact detection. Five recipes compare absent, zero-stiffness and 1000 N/m
bars: heave/jump, opposite 40 N·m roll loads, a free dynamic support and
missing left contacts. At 60/120 Hz each engine/mode emits 10,425 states.
The 100 kg chassis has isotropic inertia 100 kg·m² and four radius-0.3 m
wheels at x=±0.6/z=±1 m, travel 0.2/0.77985 m, springs 1200 N/m and
damping 160 N·s/m.
Both engines use 12 velocity/4 position iterations, one Jolt worker, no
substeps, sleep, chassis damping or tires.

Every step checks unilateral support forces, contact points on the wheel
rays, the actual implicit spring/bias law and linear/angular impulse balance
(.05 N·s/N·m·s); dynamic total momentum and reactions are bounded by 0.01.
Pose/velocity/rotation/angular velocity/suspension parity bounds are
.02 m/.08 m/s/.015 rad/.08 rad/s/.02 m; fixed one-second window force means
compare within 10 N, rest height within .003 m and total mean support within 2 N.
Opposite loads must mirror and bars must reduce loaded roll by at least 20%.
Zero stiffness and missing support preserve all fields within 1e-6.

Symmetric heave preserves pose and ordinary fields within 1e-6, with a
separate 1e-3 N bound only for wheel forces: single-precision left/right
length differences around 1.4e-7 m produce a real bias response below .00045 N.
The independent spring law and all original balance/parity bounds remain
unchanged. 67 corrupt/missing/duplicate/nonfinite evidence checks per engine
and mode protect the qualification. This reproduces Jolt's spring bias, whose
effective transfer also depends on damping and time step; it does not claim
a time-step independent torsion spring, general tire-contact parity, maximum
body-angle limitation or a performance gain.

## Vehicle tilt cone

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleTiltLimitRun.py --mode both
```

Eleven recipes compare free and limited vehicles at 60/120 Hz: mirrored and
diagonal flight, free yaw, runtime limits, rotated then zero gravity, local up,
near and exact inversion, remembered-axis recovery, and suspension/anti-roll
coupling from a level start under a 40 N·m load followed by a jump, with a
.0025 rad cone to isolate the supported angular row. The fresh exact antipode is
characterized as a Jolt singularity, not advertised as automatic self-righting.
The combined fixture excludes large free toppling after a 500 N·m load, whose
stop-impact velocity parity remains unqualified.

Free-flight linear momentum and unilateral angular projection are checked
independently. Fixed tolerances distinguish free flight from the composed contact
case; corrupt, duplicate, missing and non-finite rows must fail. Position and
velocity are compared per step in both native modes. This campaign does not
establish all vehicle impacts or a motorcycle balance controller.

## Powered incline with constant tire friction

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleInclineRun.py --mode both
```

The fixture compares uphill propulsion and braking on mirrored 0.2 rad slopes,
with ray, sphere and 40 cm cylinder contacts at 60/120 Hz. It uses a 100 kg
chassis, 100 kg·m² inertia, a 40 N·m engine, manual forward/reverse gearing and
four driven wheels. Both engines use 12 velocity and 4 position iterations,
one worker and no substeps, sleep or chassis damping. Each run receives two
seconds with brakes, three seconds at 80% throttle uphill, then three seconds
with brakes. The soft preset uses 1200 N/m, 160 N·s/m and .77985 m travel;
the firm preset uses 10000 N/m, 1000 N·s/m and .6 m travel.

Tire coefficients are explicitly constant 1 or 0. The 48 configurations produce
34,608 states per engine and native mode. The plane normal is stored in the
primitive with an identity floor body, avoiding the rotated-plane cast-point
limitation of the pinned Jolt version. Contact points and normals are checked
against this analytic plane.

Independent checks cover chassis linear/angular impulses, a dense five-variable
engine/rotor balance, wheel-angle integration, gravity-only sliding without grip,
uphill progress, stopping, four recovered supports, suspension height and mean
normal weight. Bounds are .1 N·s/N·m·s per step, .002 m/s and .005 m for the
gravity analytic, .05 m/s stopped speed, .003 m resting height and 2 N normal
weight. Mirrored runs use the same comparisons. Each engine/preset/mode rejects
26 missing, duplicate, nonfinite, corrupt or incorrectly calibrated witnesses.

Without grip, pose/velocity/orientation/rotor comparisons are per step, except
cylindrical angular velocities: a line of valid contact points requires
quarter-second means, bounded by .05 rad/s. With grip, orientation is compared
per step; one-second windows aligned on the commands compare displacement,
mean linear/angular velocity, mean rotor velocity and unwrapped wheel-angle
increments. Their bounds are .05 m, .1 m/s, .15 rad/s, .25 rad/s and .1 rad;
orientation uses normalized quaternion angular distance bounded by .02 rad.
Instantaneous differences remain in the report.

This fixture does not qualify variable friction curves near a braked stop.
The original curve with zero friction at zero slip showed sensitivity even
between two Jolt runs with a one-micrometre initial-height perturbation.
General terrain, strict instantaneous braking parity and vehicle cost campaigns
remain separate qualifications.

## Track coupling in flight

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedVehicleRun.py
```

`TrackedVehicleOracle.cpp` exercises the pinned Jolt `TrackedVehicleController`
with two tracks and six suspended wheels in zero gravity, without ground.
Sixteen cases at 60/120 Hz cover equal/different side ratios, counter-rotation,
reverse gear, neutral/open clutch, finite and strong braking, overspeed,
zero engine idle, unequal wheel radii, automatic forward/reverse engagement,
a mid-run ratio reversal and unequal track brakes. Each mode emits 5,792 states.

The Python checker evaluates scalar step recurrences and separate invariants:
stationary chassis, common linear belt speed, wheel angle integration before
motor torque, engine/clutch bounds and a finite-torque stopping bound. It rejects
37 corrupt witnesses per mode and compares Debug/Release output. The angular
step residual is bounded by 0.0001 rad/s, wrapped wheel angle residual by
0.0001 rad and engine RPM error by 0.02. These are step checks against the
preceding observed state, rather than a claim about accumulated roundoff.

The ideal track controller uses its own inertia-weighted synchronization and
sets connected engine RPM from the tracks. It is not the automotive implicit
clutch model; no general engine/rotor energy conservation is asserted. A zero
idle engine with stationary tracks does not start this ideal coupled system.
The strong-brake case must stop within `max_initial_speed * max_inertia /
minimum_brake_torque`, here 0.16 s. This is a bound for these equal positive
side ratios and a zero-throttle airborne fixture.

This is a **Jolt reference qualification**. It does not establish a Silex track
API, ground driving, contact behavior or a visible vehicle demo. Those require
the corresponding Silex consumer and contact witnesses.

## Silex tracked driving against Jolt

From the group/workspace root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedGroundRun.py --mode both
```

`TrackedAir.sx` adds the public SDK counterpart of the sixteen airborne cases.
`TrackedGroundOracle.cpp` and `TrackedGround.sx` add six plane/ray-contact cases:
forward, reverse, mirrored skid steering, counter-rotating pivot and zero grip.
The 100 kg chassis has six 0.3 m wheels and two 2 kg·m² tracks, differentials 6,
a manual ±1 gearbox, constant 15 N·m engine torque and 1500 N·m track brakes.
Grip is longitudinal 1 and lateral 0.15 (or zero), support friction 1. Each
8 s case lands with brakes for 2 s, drives at 80% for 2 s, then brakes for 4 s.
Higher torque can overturn this reference itself; no contact-free stopping is
claimed. Both engines use one worker, one substep and 12/4 solver iterations.

The runner rebuilds both engines in Native Debug/Release, checks 5,792 air and
8,652 ground states per engine/mode, and rejects 37 airborne plus 121 ground
corruptions per engine/mode (632 total). It retains raw rows and hashes, applies
independent step balances and commands, compares the main chassis pointwise at
0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s, and requires recovery to six supports,
163.5 N per wheel, 981 N total and 0.88365 m chassis height. A Jolt initial
height perturbation of 1 µm must pass those same main comparison bounds first.
Ground impulse residual limits are 0.1 N·s and 0.1 N·m·s; angular/belt recurrence
limits are 1e-4 and engine RPM 0.02. Over command-aligned one-second windows,
resultant force/torque bounds are 20 N/30 N·m, mean normal load per wheel 20 N,
and wheel rotation increments 0.1 rad. Opposite curves check pointwise pose
and mean velocities at the same velocity bounds: contact-order conditioning
in Jolt itself exceeds the instantaneous velocity limit. Main Silex/Jolt parity
still checks all four chassis channels pointwise. Raw individual tangential
load differences are retained, but such sharing is not unique and not qualified.

Jolt refreshes wheel speed during contact solving only for supported wheels;
unsupported observations retain its post-collision/pre-contact value. The SDK
publishes final belt speed for every wheel instead. The checker verifies each
observation at its actual boundary. Angles in both engines integrate the old
track speed. Shortest lossless Silex and nine-digit C++ outputs are decoded
back into binary32 before recurrence checks, avoiding a float64 text-decoding
artifact. No numerical tolerance was raised for either distinction.

Debug/Release raw outputs are byte-identical for these cases. The scope is
macOS ARM64, ideal two-track coupling, ray contacts and a plane; this campaign
does not qualify articulated track links, volumetric track contacts, every
terrain, anti-roll/tilt combinations or performance. Output report:
`.silex/physics3d-oracle/tracked-driving-qualification.json`.
