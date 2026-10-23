# Tracks: cross a finite ramp with automatic shifting

From the workspace root or the Spec Worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticRampRun.py --mode both
```

Two 16 s recipes at 60/120 Hz retain the vehicle from `TrackedAutomatic.sx`
and compare a plane with a finite ramp. After 2 s settling, 4 s at 80% throttle
are followed by 10 s at 4% braking. The ramp course must show ascent, loss of
all six supports, flight, landing and rest. The gearbox retains ratios 2/1.4/1,
1800/1200 RPM thresholds, 0.5 s switch, 0.3 s engagement and 0.5 s latency.
The 15 N·m engine, suspensions and tracks match the plane qualification.

The ramp is an 8 × 0.4 × 6.03 m box centered at (0, 0.1, 15), tilted by
−0.1 rad around X with friction 1. The six ray contact points and normals must
belong to the plane or the finite top of this box. The checker reconstructs
RPM, gears, clutch, track speeds and wheel rotations from each engine's own
observations. It checks impulse balances and 1 s windows of resultant forces,
torques, normal loads and rotation increments.

Chassis bounds remain 0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s. Shift sequences
must match between engines, with event times differing by at most 0.05 s.
Final velocity can be revised after pose integration under contact, so exact
position integration is checked in flight. Individual tangential force sharing
is not unique and no parity is claimed for it. All 114 channels and the schema
are corrupted individually.

Raw outputs and the report live under `.silex/physics3d-oracle/`. A green
qualification also requires identical Native Debug/Release outputs for each
engine. It covers these recipes, without general terrain, linked tracks,
volumetric contacts, prolonged straightness or performance claims. Upshift
inhibition controls in `TrackedAutomaticRun.py` remain separate: already being
in top gear during flight does not establish that gate.
