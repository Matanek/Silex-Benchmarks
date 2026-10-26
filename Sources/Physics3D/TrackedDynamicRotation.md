# Measure finite-mass rotating support reactions

From the workspace or Spec worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedDynamicRotationRun.py --mode both --stable-brakes
```

Seven 6 s workloads at 60/120 Hz compare rest, both spin directions on a
1000 kg then 200 kg platform, free tracks on 200 kg and a kinematic control.
The 100 kg chassis starts 2.5 m off center. The six wheels, suspension, tracks
and materials reuse the previous tracked witnesses. The 8 × 0.4 × 12 m
platform rests on a frictionless plane.

At 2 s the dynamic support receives an angular impulse `Iy × 0.5 N·m·s`;
at 4 s the opposite impulse removes the injected momentum. Negative cases
reverse the signs. No subsequent rotation or velocity is prescribed to a
dynamic support, and the chassis receives no pose/velocity commands. The
kinematic control instead receives 0.5 rad/s from 2 to 4 s, then zero. Brakes
stay locked except in the free case during motion; that case brakes again
at 4 s. Profiles stay 48/4 for dynamic supports and 12/4 for the kinematic
control, identical between engines and inherited from their earlier fixtures.

With brakes locked, both bodies share rotational inertia. Common spin
approaches `L / (Iy_support + 100 + μ × 2.5²)`, where `μ = 100M / (100 + M)`.
The lighter support slows more than the heavier one; imposed rotation keeps
its speed. Free tracks allow relative movement and change momentum sharing.
Total horizontal center of mass stays fixed while each body moves.

The runner checks Y angular momentum using world-space inertia and orbital
terms `r × mv`. Wheel/support reactions oppose each other at the same point.
The floor may supply vertical force and X/Z torques, but no horizontal force
or Y torque. Per-step balances, momentum, center of mass, contact geometry,
rotors, mirrors and final rest independently complement Jolt comparison.
The last second requires six contacts and 981 ± 2 N support load.

Budgets fixed before observation: both-body parity 0.05 m / 0.1 m/s / 0.02 rad /
0.15 rad/s; mirror 0.005 m / 0.02 m/s / 0.005 rad / 0.02 rad/s; per-step
impulses 0.1 N·s or N·m·s; total horizontal momentum 0.1 N·s, total Y angular
momentum 0.5 N·m·s and center of mass 0.001 m. Locked relative speed stays
below 0.05 m/s, analytical spin error below 0.03 rad/s. Force windows keep
20 N / 30 N·m / 20 N / 0.1 rad budgets. The 127-value schema and branches are
protected by 146 corruptions per engine/mode. Native Debug/Release must be
byte-identical.

The required `--stable-brakes` option explicitly identifies the Jolt controller
copy with symmetric static bounds. Original sources and libraries stay intact;
patch, hashes and linkage are recorded. Separate traces/report use
`tracked-dynamic-rotation-stable-brakes` under `.silex/physics3d-oracle/`, with
fixture `tracked-dynamic-rotation-v1`. No other Jolt adaptation is involved.

This proof covers the fixed masses, geometry, impulses and ray contacts. It
does not qualify arbitrary terrain, large free overturning or a general
vehicle campaign. No CPU/FPS gain is claimed. See also [finite-mass translation](TrackedDynamicPlatform.md)
and [imposed rotating support](TrackedRotatingPlatform.md).
