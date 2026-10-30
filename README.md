# Silex Benchmarks

`Silex-Benchmarks` gathers the public performance workloads for Silex and its
packages. The repository keeps each scenario together with its protocol,
external reference implementations, and raw results when available.

This development revision requires the compiler and packages using the single
`Result` API: ordinary calls return the success value or panic, and `try call()`
keeps the `Result` for explicit error handling. Update the toolchain and
packages together before running these sources.

## Organization

All Silex benchmarks live under [`Sources/`](Sources/). They are not grouped
by package: each name directly describes the workload being measured.

A self-contained benchmark remains a direct file:

```text
Sources/RetainedCanvasGeometry.sx
Sources/RegexStreamingSearch.sx
Sources/UpdatingTextLayers2D.sx
```

A benchmark receives a directory only when it has multiple artifacts: large
sources, assets, a C++ reference implementation, a runner, a checker, or
baselines. Baselines always stay with the benchmark that produced them:

```text
Sources/Boids2D/
├── Silex.sx
├── Cpp/
├── RunComparison.sh
└── Baselines/
```

The [`Package.json`](Package.json) file defines `Sources` as the package
source root and declares every dependency required by the catalog.

## Catalog

| Benchmark | Purpose |
| --- | --- |
| `TensorStableCompute/` | separate Tensor memory/transfers and cold, hot, resident, observed, and end-to-end inference/training for primitive and neural workloads |
| `CompilationPerformance/` | separate cold compilation, shared-package misses, entry edits, and exact executable hits |
| `Boids2D/` | compare native and LLVM Silex with a C++23 implementation of the Scene2D/ECS/GPU path |
| [FallingBodies2D/](Sources/FallingBodies2D/README.md) | jointly load 2D physics, transform transfer, and rendering; explicit equal-work qualification |
| `WorldRendering3D/` | measure an instanced 3D world across several GPU and presentation profiles |
| `PhysicsWorldScale2D.sx` | measure sparse motion and body piles at several scales |
| [Physics3D/](Sources/Physics3D/README.md) | qualify 3D geometry and world behavior against pinned Jolt, then measure sparse, sphere-bin and box-column loads |
| `RetainedCanvasGeometry.sx` | compile dense retained Canvas geometry |
| `AnimatingCanvasGeometry.sx` | update animated circles and lines through reusable Canvas preparation |
| `DynamicCanvasShadows2D.sx` | compare dynamic retained Canvas placements without shadows and with analytic shadows |
| `CanvasEffects2D/` | run the final analytic, filtered, mutable, and full-screen Canvas effect gates |
| `FilteredCanvasSurfaces/` | measure static reuse, transform-only composition, bounded mutation and fullscreen GPU filtering |
| `FontRasterization/` | compare direct Canvas SDL_ttf and vector-font rasterization under identical Release workloads |
| `UpdatingTextLayers2D.sx` | update retained text layers |
| `RetainedUIInteraction.sx` | measure UI layout, selection, snapshots, and rasterization |
| `VirtualizedTextViewport.sx` | stress GFX.UI scrolling, culling, retained text tiles, and bounded CPU/GPU residency |
| `TerminalScreenRendering.sx` | measure full terminal-screen rendering and updates |
| `TerminalScaleRendering.sx` | measure Retina local edits and full-row scrolls at 80×24 and 200×60 |
| `WebViewBridgeRoundTrips/` | exercise 1,000 round trips through a WebView |
| `RegexStreamingSearch.sx` | stream-search through one million Unicode scalars |
| `NetworkFreshnessTracking.sx` | measure network freshness comparisons and trackers |
| `BehaviourTreeScheduling/` | compare root reevaluation, per-frame resumption, event scheduling, and a handwritten state machine |
| `NodeScheduling/` | compare static and moving object Nodes with direct ECS scheduling |

## Running benchmarks

Measurements are taken from Release builds. Debug runs are only used to verify
correctness and do not constitute performance results.

From the workspace root:

```sh
silex run Silex-Benchmarks/Sources/PhysicsWorldScale2D.sx --release
silex run Silex-Benchmarks/Sources/TerminalScaleRendering.sx --release
silex run Silex-Benchmarks/Sources/VirtualizedTextViewport.sx --release
silex compile Silex-Benchmarks/Sources/DynamicCanvasShadows2D.sx --release -o /tmp/dynamic-canvas-shadows2d
/tmp/dynamic-canvas-shadows2d --baseline
/tmp/dynamic-canvas-shadows2d --analytic
Silex-Benchmarks/Sources/FilteredCanvasSurfaces/RunCampaign.sh
Silex-Benchmarks/Sources/CanvasEffects2D/RunCampaign.sh
Silex-Benchmarks/Sources/BehaviourTreeScheduling/RunCampaign.sh
silex compile Silex-Benchmarks/Sources/FallingBodies2D/Main.sx --release -o /tmp/falling-bodies-2d
/tmp/falling-bodies-2d --smoke --immediate --no-panel
silex compile Silex-Benchmarks/Sources/WorldRendering3D/Main.sx --release -o /tmp/world-rendering-3d
(cd Silex-Benchmarks/Sources/WorldRendering3D && /tmp/world-rendering-3d --benchmark)
```

Campaigns that compare multiple executables document their protocol in their
own `README.md`. They must preserve raw output, repetition count, variance,
build mode, operating system, and architecture. A local baseline is never a
portable performance guarantee.

`DynamicCanvasShadows2D.sx` runs 1,024 rotating, non-uniformly scaled Canvas
placements for 30 warm-up frames and 120 measured frames. Its two independent
cases compare the ordinary analytic drawing pipeline with the direct analytic
shadow pipeline. Each result prints the compilation target, GPU, draw calls,
pipeline and texture bindings, CPU-frame mean, variance and range. The public
renderer does not currently expose GPU timestamps, so the workload reports
that metric as unavailable rather than substituting CPU time. Filtered group
costs are measured separately by `FilteredCanvasSurfaces/` so the analytic
placement benchmark keeps its original workload and baseline.

`Boids2D/Silex.sx` is a faithful copy of the historical benchmark: its
algorithm, constants, and measurement window were not rewritten during the
migration. `FallingBodies2D` likewise preserves its spawning behavior,
asynchronous scheduler, buffers, and options. Only diagnostics reserved for
`GFX.Physics` were removed so the benchmark remains a genuine public
consumer. Any future change to these workloads requires a new baseline and an
explicit justification.

FallingBodies2D now also provides an opt-in `--fixed-work` protocol for comparing
identical step and frame counts. It preserves the ordinary interactive mode and
uses a separate baseline; see its [qualification guide](Sources/FallingBodies2D/README.md).

`VirtualizedTextViewport.sx` preloads a logical document of 5,000 unique lines
and renders only the viewport intersection through a custom GFX.UI content
view. It is a public scrolling and virtualization workload for the future
overflow/TextArea contract, not a claim that GFX.UI already provides a
scrollable `TextArea`. The logical strings remain available for future search,
selection and copy operations, while retained text tiles and Scene2D GPU blocks
are independently bounded to 128 entries.

The interactive workload supports keyboard navigation, natural or normal mouse
wheel direction, an inertial trackpad target, and a controlled vertical
scrollbar. A compiled executable accepts `--verify` for the headless structural
gate and `--profile-depth-wheel` for a bounded top/middle/bottom traversal that
revisits both ends after cache saturation. `--vector` remains a diagnostic
comparison of the underlying text renderer; it does not change the benchmark's
GFX.UI ownership.

Optimizer and backend benchmarks remain under `Silex/Toolchain/Benchmarks/`.
They are internal toolchain gates rather than public package campaigns.

Performance artifacts that intentionally inspect `package` details also
remain with their owners. This includes the Box2D oracle and fine-grained
solver profiles in `GFX.Physics`, as well as the worker-pool regression test
in `STD`: they verify an implementation, while the scenarios in this
repository cross a real package boundary.


### Boids native / LLVM / C++ comparison

[Boids2D](Sources/Boids2D/README.md) compares Silex native, Silex LLVM and
C++/Clang through the single executable entry point `RunComparison.sh`.
The script builds and verifies the Release executables before six warm-up rounds and
twelve measured rounds per variant. `--wait` pauses after verification;
`--prepare-only` builds and verifies without running the benchmark.

From the SilexProject workspace root:

```sh
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

Build preparation is contained in the script. Its three executables and one
incremental CMake build live under `.silex/benchmarks/boids-comparison` at the
workspace root. No external configuration or Spec artifacts are required.
Each capture writes one plain-text log
to [Baselines](Sources/Boids2D/Baselines/2026-09-14-092230-615615-macos-arm64.log), named
for the date, time, operating system and architecture. All three executables
must finish with code 0; a complete but nonstationary capture returns 2 from
the runner and remains available for inspection.

### Kinematic ragdoll poses and release

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/RagdollKinematicRun.py --mode both
```

Three offset members rotate/translate, then a coherent translated chain resumes
simulation with its current velocity. A kinematic member pushes an external
sphere. At 60/120 Hz, five fixed samples compare mass centers, quaternions and
linear/angular velocities with analytic values and pinned Jolt’s
`DriveToPoseUsingKinematics`. Jolt is explicitly stopped after one second to
match Silex’s finite-duration target. Contact onset and instantaneous impulses
are excluded; tolerances and negative guards live in `RagdollKinematicRun.py`.

### Four wheel suspensions

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleSuspensionRun.py --mode both
```

A 100 kg chassis drops on four 10000 N/m, 1000 N·s/m suspensions, jumps after a
500 N·s impulse and returns to rest. A second recipe exercises compression stops
under a sustained 20000 N load. Pinned Jolt uses its real `VehicleConstraint`,
ray collision tester and zero-traction wheeled controller. Both engines use
12 velocity / 4 position iterations at 60/120 Hz. Geometry, trajectories,
phase mean support forces and independent linear/angular impulse balances are
checked; loaded hard-stop instantaneous trajectories are excluded. The harness
records complete samples, input settings, tolerances and corrupt-witness guards.

### Passive tire rolling and lateral grip

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleTiresRun.py --mode both
```

Six recipes exercise forward and rotated rolling, lateral and diagonal drift,
free wheel damping and a jump while moving. Pinned Jolt uses the real wheeled
controller with zero engine torque and a neutral manual transmission. Both
engines use 12 velocity / 4 position iterations, one worker, no substeps and
60/120 Hz; Silex retains its pre/post-integration solver passes. Each engine
produces 3072 observations in each native Debug/Release mode. Every step checks
chassis/wheel impulse balances, force caps and angular integration. Trajectories
and rotations have fixed per-observable tolerances. Slips are independently
recomputed, compared instantaneously above 0.1, and compared by phase means
near zero; instantaneous near-zero slip parity is not claimed. All 49 numeric
channels plus missing, duplicate and nonfinite rows have corruption guards.
This is correctness evidence, without performance or full driving claims.

### Steering and wheel brakes

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleControlsRun.py --mode both
```

Eight recipes exercise weak braking, locking in both travel directions, rear
handbraking, mirrored turns, a rotated chassis with steering/braking, and free
rotors slowed in flight. Jolt uses its real wheeled controller with zero engine
torque and a neutral transmission. Both engines use 12 velocity / 4 position
iterations, one worker, no substeps and 60/120 Hz; Silex retains pre/post-integration
passes. Each native mode produces 5416 observations per engine and 60 corrupt
witness guards. Wheel/chassis impulse balances, torque and friction caps,
steering signs, symmetry and free-flight analytic rotation are checked.

The Jolt brake torque column is inferred from public rotor velocities and
longitudinal impulses; it is not an independently measured torque. Slips are
recomputed within each engine. Contact slip velocities retain the predefined
velocity tolerance; ratio/angle comparisons and phase means apply only when
their denominators exceed that tolerance. Near-stop instantaneous or mean slip
ratio parity is not claimed. Full samples and conditioning counts are retained.
This is correctness evidence, without powertrain or performance claims.

### Engine, clutch and transmission

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehiclePowertrainRun.py --mode both
```

Eleven recipes cover analytic free rotors, neutral and open clutch, powered
forward/reverse travel and braking, a rotated steering chassis, open/limited
axle and center differentials, automatic shifts/reversal, and wheels back-driving
an engine from a faster initial roll. Each native mode produces 8302 samples
per engine and 61 corruption guards. Both use 12 velocity / 4 position iterations,
one worker, no substeps and 60/120 Hz. Silex retains pre/post integration passes.
An independent dense coupling solve checks the engine/wheel residual; body
impulse balances and analytic flight complement actual Jolt observations.
Wheel drive/brake torques are not exposed directly by Jolt and are not invented
as raw observations; Silex consumer tests check those snapshots independently.

Chassis/wheel trajectories and RPM retain fixed instantaneous tolerances.
Slip formulas are recomputed for all samples. Contact velocity components are
compared instantaneously while both contacts move above the predefined velocity
scale, and as paired one-second phase means everywhere, including near rest.
Near-rest instantaneous contact velocity parity is not claimed. Raw maxima and
conditioning counts remain available. Slip ratios retain their speed-conditioned
comparison. Angular comparison uses a speed scale derived from velocity accuracy
and the required angle accuracy; lower-speed angles retain formula checks only.
These are correctness fixtures, without performance claims or complete coverage
of the other vehicle families.


## Spherical wheel contacts

From the workspace or Spec group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VehicleSphereContactsRun.py --mode both
```

The real pinned Jolt `VehicleCollisionTesterCastSphere` supplies 38 geometric
observations per engine/mode: flat and tilted supports, edge/corner reach,
sphere/capsule supports, filtering, initial overlap and compounds. Four
`VehicleConstraint` recipes add 3,788 dynamic observations at 60/120 Hz:
flat drop/jump, hard loading, bare edges, and the same edges with lateral grip.
Actual wheel normal and lateral impulses close independent linear/angular
balances; 12 geometry and 68 motion corruptions are rejected per engine/mode.

Full trajectory comparison covers soft flat support and gripped edges. Hard
stops use geometry and phase means, as in the ray witness. Bare-edge symmetry
is unstable even in Jolt after a 1e-6 m perturbation: only the initial 1.5 s
trajectory is compared, while full impulse balances remain checked. The pinned
Jolt infinite-plane implementation returns an off-plane contact point when
rotated; that recipe compares length and normal, and an equivalent tilted box
face qualifies the physical point. Raw points remain preserved. This fixture
does not claim tire-width/cylinder support or performance parity.


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

## Automatic tracked shifting

[Automatic tracked shifting](Sources/Physics3D/TrackedAutomatic.md) compares
forward/reverse gear changes, braking to neutral and supported/airborne
upshift inhibition against pinned Jolt.
[Protocole français](Sources/Physics3D/TrackedAutomatic.fr.md).

## Automatic tracked ramp traversal

[Automatic tracked ramp traversal](Sources/Physics3D/TrackedAutomaticRamp.md)
compares ascent, flight, landing and gear changes on a finite box with the
matching flat control. [Protocole français](Sources/Physics3D/TrackedAutomaticRamp.fr.md).

## Tracks on moving platforms

[Moving-platform qualification](Sources/Physics3D/TrackedPlatform.md) compares
stationary support, lateral/longitudinal carrying and free track rolling.
[Protocole français](Sources/Physics3D/TrackedPlatform.fr.md).

- [Tracks on a finite-mass support](Sources/Physics3D/TrackedDynamicPlatform.md) · [Français](Sources/Physics3D/TrackedDynamicPlatform.fr.md) — reciprocal impulses, two masses and free rolling.

## Tracks on rotating platforms

[Rotating-platform qualification](Sources/Physics3D/TrackedRotatingPlatform.md) compares opposite yaw transport, locked tracks and free rolling. [Protocole français](Sources/Physics3D/TrackedRotatingPlatform.fr.md).

[Precise motorcycle lean oracle](Sources/Physics3D/MotorcycleLeanOracle.md)
documents the explicit `--stable-lean` variant, original-reference provenance
and independent small-angle torque check.
[Guide français](Sources/Physics3D/MotorcycleLeanOracle.fr.md).

[Combined support motion](Sources/Physics3D/TrackedRotatingPlatform.md#combine-translation-and-rotation)
adds simultaneous translation and rotation through the explicit `--combined`
protocol, preserving the pure-rotation witness and its limits.

- [Tracked brake corpus](Sources/Physics3D/TrackedBrakeCorpus.md) / [Corpus des freins chenillés](Sources/Physics3D/TrackedBrakeCorpus.fr.md) : seven historical contact fixtures with the explicit stable-brakes Jolt variant.

- [Finite-mass rotating support](Sources/Physics3D/TrackedDynamicRotation.md) / [Réaction du support tournant](Sources/Physics3D/TrackedDynamicRotation.fr.md) : angular momentum exchange, orbital inertia, mirrors and locked/free tracks.

[Extended tracked driving](Sources/Physics3D/TrackedAutomaticLong.md) · [Conduite chenillée prolongée](Sources/Physics3D/TrackedAutomaticLong.fr.md): explicit48/4 convergence profile,176m launch/braking, original12/4 limit retained.

The [character mode qualification](Sources/Physics3D/Characters.md) compares the physical and virtual SDK modes against pinned Jolt and analytical balances.

[Soft bodies and cloth](Sources/Physics3D/SoftBodies.md) qualify five CPU constraint families and deformable surfaces against pinned Jolt, with public-consumer lifetime, rendering and worker checks. [Protocole français](Sources/Physics3D/SoftBodies.fr.md).
