# Tracks on a finite-mass support

From the workspace root or Spec Worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedDynamicPlatformRun.py --mode both
```

Six 6 s courses at 60/120 Hz compare rest, a lateral impulse with locked tracks,
and a longitudinal impulse with locked or free tracks. The latter two cases
are repeated with a lighter platform. The 8 × 0.4 × 12 m box weighs 1000 or
200 kg and rests on a frictionless plane. A central impulse of +2M N·s at 2 s,
then −2M at 4 s, drives it. Neither its velocity nor its pose is prescribed.
The 100 kg chassis stays in neutral; six suspensions and two tracks exchange
forces with the support.

With locked tracks, the shared steady speed is `2M / (M + 100)`.
With free tracks and `K = 4 / 0.3²`, the support reaches
`U = 2M / (M + 100K / (100 + K))` and the vehicle `v = KU / (100 + K)`.
The support therefore slows under the vehicle's reaction. Total horizontal
momentum and center-of-mass displacement independently check the comparison.

This profile explicitly uses 48 velocity iterations per phase and 4 position
iterations in both engines. The SDK default remains 12. The 12/24/48 study keeps
the same protocol and budgets: profiles 12 and 24 briefly exceed 0.1 m/s error;
only 48 satisfies this qualification. This proves neither monotonic convergence
nor scene performance.

Pointwise chassis and support limits remain
0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s. Impulse balances are bounded by
0.1 N·s or N·m·s, center-of-mass drift by 0.001 m, and free-track momentum
by 0.002 N·m·s. Contacts are checked in the actual support frame.
Fixed 1 s windows compare forces, torques, loads and rotations. The 127 values
and schema undergo 152 corruptions per engine. Green qualification also requires
identical Native Debug/Release output. Raw traces and the report live under
`.silex/physics3d-oracle/`.

This proof covers these horizontal impulses, two masses and ray contacts on
this box. General rotating supports, prolonged driving, general impacts and
other execution platforms remain unqualified. See also the
[prescribed-speed support](TrackedPlatform.md).
