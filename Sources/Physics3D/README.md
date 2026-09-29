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
