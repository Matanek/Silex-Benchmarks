# Qualifying both character modes

From the workspace root or the Spec worktree group:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/CharacterRun.py --mode both
```

The six fixed scenarios in `CharacterFixture.json` have identical inputs in
`Characters.sx` and `CharacterOracle.cpp`. A checksum rejects silent JSON edits
without corresponding consumer updates. The comparator rejects missing,
duplicate and non-finite fields and perturbations beyond the thresholds.
`--self-test` checks these rejections without compiling.

A capsule with 0.3 m radius and 0.55 m cylindrical half-height pushes a 10 kg
sphere, first weakly and then with force capped at 100 N over 0.1 s. Expected
speeds are 0.009 and 1 m/s, without rotation for this central contact. Virtual
mass of 70 kg then transfers its weight to a 10 kg support over 1/60 s,
producing −1.1445 m/s. A downward speed of 0.3 m/s establishes actual contact
on the first step in both engines; gravity remains an explicit virtual
controller input.

A 70 kg physical character meets a 30 kg sphere: the central inelastic collision
at 1 m/s produces 0.7 m/s for both bodies, with character rotations locked.
Falling and resting run for 180 steps at 120 Hz. Finally a crouched character
cannot stand under a ceiling, then preserves its feet and mass when the ceiling
is removed. The Jolt adaptation also computes the proposed center to preserve
feet and restores the pose after rejection.

Fourteen observables are compared with pinned Jolt 5.6.0 and analytical balances.
Absolute tolerances are 0.0001, except rest measurements at 0.005. Dimensions
are SI. Both engines use 12/4 iterations; Jolt uses 0.001 m slop and 0.002 m
virtual padding. Damping and restitution are zero. No tolerance is widened
after observation.

The runner verifies the Jolt archive, reuses cached Debug/Release libraries
when present, checks their configuration and records their checksums. On an
empty cache, the helper builds Jolt with one worker. Reports and executables
are stored in `.silex/physics3d-oracle/`. This qualification concerns executed
macOS ARM64 Native Debug/Release. Character encounters, moving supports,
filters, lifetimes, slopes and stairs also have GFX.Physics consumer tests;
this protocol does not claim full trajectory equivalence for chaotic scenarios.
