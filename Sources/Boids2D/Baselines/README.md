# Current Boids baseline

The reference is the user's capture of 14 September 2026, starting at 07:39:50.
It replaces the previous contents of this directory, which remain in Git history.
[BaselineManifest.json](../BaselineManifest.json) selects the three retained series
and records the SHA-256 hashes of the original files.

| Variant | Median FPS | MAD FPS | Drift |
| --- | ---: | ---: | ---: |
| Silex/Natif | 92.482 | 0.302 | -1.32% |
| Silex/LLVM | 97.475 | 0.558 | -2.32% |
| C++ architectural | 91.439 | 1.503 | -3.26% |

All three series are **nonstationary** under the existing thresholds. This is a
descriptive starting point, not a qualified performance gain or regression gate.

The [raw log](2026-09-14-073950-255973-boids-fourway.log) and [complete report](2026-09-14-073950-255973-boids-fourway.log.json) were moved from the local
`Evaluations/boids-fourway/Results/` directory without changing any bytes. They
retain all 64 process records, their original configuration, four warm-up rounds,
twelve measured rounds per variant and the former C++ direct participant.
Removing that participant from the current comparison does not retroactively
change the order or conditions of this measurement.

New captures use [RunComparison.py](../RunComparison.py), three variants, six
warm-up rounds and twelve measured rounds per variant. They are written here
without overwriting earlier captures. The manifest remains an explicit reference
selection; a new run does not silently promote itself to a qualified baseline.
