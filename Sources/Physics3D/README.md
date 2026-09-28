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

The point fixture checks anchor error, support reaction, pendulum motion, and
the pendulum's horizontal position within 0.05 world units after two seconds.
It does not qualify every joint configuration or the per-iteration solver path.

`WorldQueryRun.py` checks that a world ray selects the near sphere even though
the far sphere was created first. It compares body identity and hit fraction
`0.25` with Jolt in Debug and Release. Consumer tests cover multiple hits,
compound child IDs, overlaps, exclusions, and retained results separately.
