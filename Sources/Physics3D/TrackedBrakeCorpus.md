# Check tracked workloads with symmetric static friction

From the workspace or Spec worktree group root:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedBrakeCorpusRun.py --mode both --stable-brakes
```

This campaign requalifies seven existing tracked contact workloads: ground
driving, ramp, automatic transmission, automatic ramp, translating kinematic
support, finite-mass support and rotating support. It reuses their programs,
geometry, commands, durations, rates, qualifiers, mirrors, corruptions and
comparators. Profiles stay12/4, except the finite-mass support which keeps48/4.
Native Debug/Release traces must be identical per engine. The ground height
perturbation check is preserved. Air workloads do not exercise this contact
friction branch and retain their original qualification.

The required `--stable-brakes` option identifies a pinned Jolt variant: a copy
of `TrackedVehicleController.cpp` bounds the accumulated locked-track impulse
in both directions. Capacity stays `min(brake, friction)`. Torques, contacts,
free tracks and solver are unchanged. The original source hash is checked;
the archive and libraries stay intact. The copied object precedes the original
archive at linkage, with full provenance. No historical original result is
replaced or relabelled as adapted.

Traces and report use `tracked-brake-corpus-*-stable-brakes-*` under
`.silex/physics3d-oracle/`. The report hashes both controller sources, patch,
libraries and binaries and records the linkage command. Historical runners
keep their original oracle. The new [combined transport](TrackedRotatingPlatform.md#combine-translation-and-rotation)
using this variant adds centripetal laws and contact slip measured independently
of the other engine.

This campaign does not qualify arbitrary terrain, general rotating finite-mass
supports or prolonged straight driving. No CPU/FPS gain is claimed, and no
consumer binary links Jolt.
