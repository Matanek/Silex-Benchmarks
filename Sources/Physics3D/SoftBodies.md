# Qualify 3D soft bodies

Compare independent constraints before composite scenes. The reference is
Jolt 5.6.0 at commit `e77f175595e64cb44218cc9d9d56fc365ad0e36a`, with eight
substeps and sleeping disabled. `SoftBodyOracle.cpp` uses the existing pinned
Physics3D archives; no foreign physics library is integrated into the Silex package.

## Corpus and thresholds

The five primitives are compliant distance, tetrahedral volume, dihedral bend,
pressure and long-range attachment. After twelve steps at 60 Hz without gravity
or damping, positions and velocities must differ by at most 0.0002 absolute.
Bending allows 0.002 because Jolt uses an approximate acos. Parameters and
indices are identical, with no tuning based on measured results.

A tetrahedral cube on a plane, suspended cloth and cloth draped over a sphere
then check common physical invariants: relative cube volume between 0.9 and
1.1, stretch below 1.2, vertex penetration below 0.0001 m and downward cloth
movement. Volume computed over an open surface has no physical meaning and
is not compared. Jolt reorders constraints with `Optimize`; cloth trajectories
need not be identical between solvers.

The Silex public consumer also checks moving anchors, attached rigid-body
removal, partial pose and backstop, momentum transfer, snapshots, pause and
revised Scene3D geometry. It compares 256 instances at one/four workers with
exact position and velocity equality at every step. Repeated program runs
must retain identical observations. Ten invalid inputs check indices, masses,
triangles, tetrahedra, pressure, radius, ownership, pose, anchors and stale handles.

The five tests in `SoftBodyContacts3D.sx` add off-centre impact and inertia,
friction torque balance, filter/sensor/disabled-body behavior, a fast vertex
against a thin wall and deterministic impulse gathering into the same rigid body.
Partial pose control also covers connected cloth: moving guided vertices,
free vertices under gravity, then removal of pose control.

## Run qualified binaries

From the SilexProject root, or a Spec Worktree group root:

```sh
silex compile Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodies3D.sx --backend native --debug -o /private/tmp/soft-body-silex-debug
silex compile Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodies3D.sx --backend native --release -o /private/tmp/soft-body-silex-release
silex test Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodyContacts3D.sx --backend native
```

Build Debug/Release oracles with the pinned configuration and archive in the
[Physics3D protocol](README.md), passing `SoftBodyOracle.cpp` to `Run.py`'s
`build_oracle` helper. Then:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VerifySoftBodies.py --silex /private/tmp/soft-body-silex-debug --jolt /private/tmp/soft-body-oracle-debug --mode Debug --output /private/tmp/soft-bodies-debug.json
python3 Silex-Benchmarks/Sources/Physics3D/VerifySoftBodies.py --silex /private/tmp/soft-body-silex-release --jolt /private/tmp/soft-body-oracle-release --mode Release --output /private/tmp/soft-bodies-release.json
```

Reports retain outputs, return codes, numerical errors, configuration, platform
and binary hashes. They establish correctness of these scenarios, without a
speedup, 60 FPS, soft/soft collision or self-collision claim.

## Surfaces and the negative CCD control

Additional oracle controls check convex inclusion recovery and shallow backing
penetration on triangles/meshes. The isolated one-vertex fixture at 120 m/s,
a 1/60 s step and one substep crosses the triangle in original Jolt in both
configurations. This result is retained as a limitation of that reference
fixture, without modifying Jolt or widening a tolerance. Silex retains explicit
CCD protection: a front approach stops at +0.03 m, while a back approach passes
freely. Analytical surface tests validate both cases.
