# Extended tracked driving

From the worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticLongRun.py --mode both
```

The20s workload uses2s settling,8s at80% throttle and10s at4% brake. Four cases
cover forward/reverse launch, no friction and a gravity-free control. Both
engines use60/120Hz, one substep and48velocity/4position iterations. A100kg
chassis has six ray wheels and two I=2 tracks,0.3m drive radius,15Nm engine and
an automatic1/2/3/2/1/neutral sequence. Loaded travel is about176m, peaking near
25m/s. There is no heading correction.

The48/4 profile is explicit. The original12/4 counterexample remains unqualified:
roughly7.04cm inter-engine position error exceeds the unchanged5cm budget.
The12/24/48/96 convergence study reduced absolute lateral drift in both engines
to below0.14mm at48iterations. This does not change world defaults or qualify
this route at12iterations. Earlier short witnesses remain unchanged. The SDK
is unchanged.

The oracle pins Jolt e77f175595e64cb44218cc9d9d56fc365ad0e36a with the explicit
[stable-brakes](TrackedBrakeOracle.py) accumulated static-friction bound variant.
Original sources and archives stay intact; no additional Jolt patch is used.
The report records commands, source hashes and solver settings.

Parity budgets stay5cm/0.1m/s/0.02rad/0.15rad/s, shift timing50ms and1s windows
20N/30Nm/20N/0.1rad. Checks cover impulse/rotor balances, normals, contacts and
six recovered supports at rest. Loaded cases additionally check absolute
straightness within5mm/0.0001rad. Each engine/mode has14408states and121corruptions;
Debug/Release outputs must match exactly per engine.

Raw traces and `tracked-automatic-long-qualification.json` live in the root
`.silex/physics3d-oracle/` cache. This workload does not qualify high-speed turns,
arbitrary terrain or volumetric track contacts.
