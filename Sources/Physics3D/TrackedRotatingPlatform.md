# Carry a tracked vehicle on a rotating platform

From the workspace root or Spec Worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedRotatingPlatformRun.py --mode both
```

Four 6 s courses at 60/120 Hz compare rest, rotation around +Y and −Y with
locked brakes, and +Y rotation with free tracks. The kinematic support measures
8 × 0.4 × 12 m and keeps its center at (0, −0.2, 0). Its angular velocity is
±0.25 rad/s between 2 and 4 s, then zero; its final angle is ±0.5 rad.
The chassis starts at (1, 1.15, 0), offset from the pivot. Neither chassis pose
nor velocity is prescribed during simulation.

The vehicle retains the translating-support profile: six rays, a 100 kg chassis,
2 kg·m² track inertias and neutral transmission. Brakes provide 1500 N·m per
track except in the free case. Both engines keep 12 velocity iterations and
4 position iterations.

With locked tracks, chassis velocity must approach support velocity at its
center: `ω × (chassis_position − support_position)`. Chassis yaw must follow
the support. Free tracks rotate and allow relative motion, which must differ
from locked brakes. Opposite-direction symmetry independently checks Jolt parity.

Pointwise chassis parity remains bounded by
0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s; prescribed support motion is checked
to 1e−4. Mirror limits are 0.005 m / 0.02 m/s / 0.005 rad / 0.02 rad/s.
Per-step impulse balances remain at 0.1 N·s or N·m·s; free-track momentum
at 0.002 N·m·s. Geometry, wheel-angle integration and contacts in the rotated
frame are checked. Fixed 1 s windows compare forces, torques, loads and
rotations. The last second requires six supports, 981 ± 2 N and rest.

The 127 values and schema undergo 143 corruptions, including free, stationary
and mirror branches. Green qualification requires identical Native
Debug/Release traces. Raw outputs and the report live under
`.silex/physics3d-oracle/`.

The initial 12/24/48/96 study isolated a static-friction asymmetry near rest;
extra iterations did not remove it. Locked wheels now bound their accumulated
impulse in both directions, retaining friction capacity and maximum brake
torque. Combined adhesion applies both candidate components together, including
candidates already inside the friction ellipse. The reduced SDK mirror test distinguishes this correction from merely
increasing iterations.

This proof covers this kinematic support, these speeds and ray contacts.
General dynamic rotation, general terrain and prolonged straight driving remain
unqualified. See also the [finite-mass support](TrackedDynamicPlatform.md).

## Combine translation and rotation

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedRotatingPlatformRun.py --mode both --combined --stable-brakes
```

This variant adds ±2 m/s along Z to the ±0.25 rad/s rotations around Y from2 to4s.
The support ends at(0,−0.2,±4), rotated by±0.5rad. Control0 stays stationary.
Case3 frees the tracks only during the2..4s motion and explicitly brakes them
again from4s to test stopping. Without the flag, historical case3 remains free
throughout the workload. Both engines receive exactly the same recipe per variant.

The expected velocity at the chassis center combines both terms:
`v_support + ω_support × (chassis_position − support_position)`.
Contact points are checked in the support's translated and rotated frame at the
beginning of the step. Chassis impulse balances stay in world space. Mirror,
braking/rolling, force windows and final rest retain the bounds above; this
composition increases no tolerance.

The prefix and fixture identity become `tracked-combined-platform-v1` (the raw
prefix omits `-v1`). Separate traces and report are stored under
`.silex/physics3d-oracle/tracked-combined-platform-*`. Schema and comparators
are shared with pure rotation, without a second copy of the physics. The
explicit `--stable-brakes` variant changes only the locked-track accumulated
friction bounds in a separately identified controller copy. The pinned archive,
controller and libraries stay intact; capacities, torques and free tracks are
unchanged. Without this flag, the original combined reference fails its stopping
mirror. Variant outputs use a separate `-stable-brakes` suffix and record patch,
hashes and linkage. The motorcycle tiny-angle adaptation is not involved. This variant qualifies the fixed kinematic composition,
without claiming finite-mass rotating supports or arbitrary terrain.

An independent analytical check uses the required centripetal resultant
`100 · ω × (ω × r)` with a2N mean force budget,981±2N support load and2Nm
mean resultant torque budget. It also checks contact-point slip and locked
belts. The [brake corpus](TrackedBrakeCorpus.md) exercises the previous
tracked fixtures with the same explicit variant.
