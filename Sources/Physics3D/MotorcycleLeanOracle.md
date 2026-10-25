# Compare motorcycles with precise small angles

Motorcycle workloads offer an explicit variant of the Jolt 5.6.0 controller
pinned to `e77f175595e64cb44218cc9d9d56fc365ad0e36a`. It replaces only the three
`acos(target·up)` angle magnitudes with `atan2(|target×up|, target·up)`, retaining
the original sign. This equivalent formulation preserves tiny angles when the
single-precision dot product rounds to 1. Gains, physics, inputs and tolerances
remain those of the existing witnesses.

From the workspace root or the Spec Worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleLeanOracleCheck.py
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleHandlingRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleDrivingRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleRampRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleCrossRun.py --mode both --stable-lean
```

Without `--stable-lean`, all four runners still use the original controller.
With this flag, trace and report names include `stable-lean` under
`.silex/physics3d-oracle/`. Reports identify the variant, original/adapted source
and binary hashes, three substitutions and linker command. Comparators,
scenarios and durations stay unchanged.

The Jolt archive and sources remain verified and intact. The runner writes a
copy of this controller alone in the cache, retaining its MIT notice and diff,
then links that object before the original Jolt library. An unexpected source
hash or substitution count fails the build. The Silex engine and distributed
applications do not link any Jolt library.

The analytical check applies ±1e−5/±1e−4 rad lean at 60/120 Hz to a motorcycle
on frictionless supports. Enabled minus disabled assistance must follow
`−stiffness × angle / inertia` on the first step. The original retains its dead
zone; the variant must recover that response within the analytical 5 % bound.
Debug/Release outputs must match. The SDK consumer test
`MotorcycleSmallLean3D.sx` independently checks the same physical law in Silex.

The original controller can drift sideways on a symmetric straight workload:
a strict spatial comparison with Silex can then fail despite valid physical
balances. Preserve those original results; do not describe them as successful
or widen tolerances to hide the difference. This variant is an identified
numerical adaptation of the oracle, not a result of the original controller.
It qualifies no additional terrain or driving regime.
