# Tracks: automatic shifting on the ground

From the workspace root (or the Spec Worktree group root):

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticRun.py --mode both
```

Four16s recipes at60/120Hz compare pinned Jolt with the public Silex consumer:
forward and reverse acceleration, opposing tracks supported without grip,
and airborne tracks without gravity. After2s settling,4s at80% throttle are
followed by10s of moderate4% braking. The first two cases must shift1/2/3 then
2/1/neutral, with negative gears in reverse. Both controls must exceed the
upshift RPM threshold while remaining in first gear.

The vehicle retains100kg/isotropic inertia100, six.3m wheels, track inertia2,
differential6,15Nm engine,10000/1000 suspensions and plane ray contacts.
Ratios are2/1.4/1 and−2/−1.4/−1; thresholds1800/1200RPM, idle1000RPM,
maximum6000RPM, switch.5s, engagement.3s and latency.5s. The counter-rotation
control removes tangential friction to isolate the gearbox gate; it does not
qualify a prolonged loaded pivot.

The checker reconstructs engine RPM and the clutch state machine each step
from each engine's own observations. It checks tracks, wheel angles, ray
geometry, impulses, friction capacity and final rest. Shift sequences must
match, with event times differing by at most.05s. Chassis bounds remain
.05m/.1m/s/.02rad/.15rad/s; resultant forces, torques, normal loads and wheel
rotation increments are compared over1s windows. Individual tangential force
sharing is not unique and no parity is claimed for it. All114channels are
corrupted individually, alongside schema and finite-value guards.

Raw outputs and the report are written under `.silex/physics3d-oracle/`.
A green qualification covers these recipes with identical Native Debug/Release
outputs. It does not qualify automatic ramp driving, linked track geometry,
general terrain or performance budgets.
