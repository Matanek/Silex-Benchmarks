# Tracks on a moving platform

From the workspace root or the Spec Worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedPlatformRun.py --mode both
```

Four 6 s courses at 60/120 Hz compare a stationary support, braked lateral
translation, braked longitudinal translation and free longitudinal rolling.
The 8 × 0.4 × 12 m kinematic platform starts at (0, −0.2, 0), moves at 2 m/s
between 2 and 4 s, then stops. The chassis stays dynamic; its motion is never
imposed by the application.

The automatic profile from `TrackedAutomaticRamp.sx` stays in neutral with no
throttle. Braking is 100%, except in the fourth case. Each track has inertia
2 kg·m² and 0.3 m wheel radius, with a 100 kg chassis. The independent steady
free-rolling prediction is `v = 2 × 4 / (100 × 0.3² + 4) = 0.6153846 m/s`,
compared with the platform's 2 m/s. The tracks rotate opposite to relative
platform motion.

The checker reconstructs kinematic motion, contacts on the finite top, chassis
and free-track impulse balances, rotations, friction capacity and rest on six
supports. Chassis bounds remain 0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s.
Per-step impulse bounds are 0.1 N·s and 0.1 N·m·s, rotation 1e−4 rad and
prescribed kinematic response 1e−4 m / m/s. One-second windows compare resultant
forces, torques, normal loads and rotations. Individual tangential sharing is
not claimed identical. All 127 channels and the schema are corrupted.

A green qualification requires identical Native Debug/Release outputs for each
engine. Raw outputs and the report live under `.silex/physics3d-oracle/`.
This proves horizontal translation with ray contacts on this box, without
dynamic or rotating supports, general terrain, performance or prolonged
straightness claims.
