# Boids performance baselines

This directory archives raw output from the three witnesses in
[`../Boids`](../Boids). The records are performance controls, not correctness
tests or portable timing claims.

## 2026-09-11 measurement protocol qualification

The [protocol review](2026-09-11-protocol-review.md) records two complete
captures of identical artifacts with real permutation ordering. Both are
inconclusive because retained Silex throughput and paired ratios drift beyond
the proposed 1% limit. Raw logs, identity seals and analyses are preserved;
these records do not replace the accepted historical control.

## 2026-09-10 compiler-only A/B at fixed package closure

[`2026-09-10-000541-arm64-boids-main-compiler-fixed-closure.log`](2026-09-10-000541-arm64-boids-main-compiler-fixed-closure.log)
and
[`2026-09-10-000909-arm64-boids-spec-compiler-fixed-closure.log`](2026-09-10-000909-arm64-boids-spec-compiler-fixed-closure.log)
compare Silex compiler commits `d282dcbb` (direct `main`) and `ecec3221`
(optimization Spec candidate). Both captures use benchmark commit `ed35a02d`
and the same complete package closure on the same Apple M3 Pro host.

| Compiler | Silex median | C++ architectural median | C++ direct median | Silex / architectural steady mean | Silex / direct steady mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| direct `main` `d282dcbb` | 82.447 FPS | 89.972 FPS | 87.768 FPS | 91.874% | 94.268% |
| Spec `ecec3221` | 85.620 FPS | 88.361 FPS | 86.570 FPS | 96.798% | 98.786% |

The steady means discard the first process and average the six remaining
same-position ratios. The Spec candidate gains 2.90 FPS, or 3.51%, over direct
`main` after this first-process exclusion and improves the normalized distance
to the architectural witness by 4.92 percentage points. The per-round
Silex/architectural ranges do not overlap (`90.77..92.72%` for direct `main`,
`95.78..97.80%` for the Spec), so this compiler-only improvement is not inferred
from the medians alone.

The captures also preserve a progression that their summary medians hide. The
Spec Silex witness falls from 88.172 FPS on its first process to a stable
85.095..85.908 FPS plateau over rounds 3 through 7; its rounds 2 through 7
linear slope is approximately -0.120 FPS per round. The direct-main witness
falls from 84.524 FPS to a 82.723 FPS rounds-2-through-7 mean, with an
approximately -0.363 FPS-per-round slope. C++ is more stable and remains ahead
of Silex by median in both captures.

The Spec result must not be used to erase the user-observed Boids regression.
Compared with the accepted Part 05 compiler `65471f1`, whose steady paired
Silex/architectural mean was 98.064%, the Spec candidate reaches 96.798% under
the later but fixed closure: about 1.27 percentage points remain to recover.
That difference is a regression lead for the continuation Spec, not a green
rebaseline.

Finally, the runner metadata says `rotated`, but the current implementation
runs Silex, C++ architectural, then C++ direct in that fixed order for every
warm-up and recorded round. These captures remain strong for the compiler-only
A/B because Silex occupies the same position in both campaigns, but they do
not prove a sub-percent language-to-C++ parity claim. The continuation campaign
must implement actual deterministic rotation and a stationarity rule before
issuing such a verdict.

## 2026-09-07 Part 05 fixed-workload acceptance

[`2026-09-07-170658-arm64-boids.log`](2026-09-07-170658-arm64-boids.log) is the
accepted macOS ARM64 qualification of Silex compiler commit `65471f1` with
benchmark commit `50f6dc9`. It uses the fixed 4,000-boid, 480-frame workload,
discards one warm-up process per executable, then records seven isolated
rotations. Every witness passes the workload and state-signature oracle.

| Witness | Median | MAD | Range | Relative to C++ architectural |
| --- | ---: | ---: | ---: | ---: |
| Silex/GFX | 87.165 FPS | 0.69% | 85.948-88.356 FPS | -1.37% |
| C++ architectural | 88.375 FPS | 0.20% | 88.167-89.791 FPS | reference |
| C++ direct | 87.210 FPS | 1.16% | 86.116-89.112 FPS | -1.32% |

Silex is 0.052% below the direct witness by the independently computed
medians, well inside the dispersion of both series; it is above the direct
witness in three of the seven paired rotations. The 1.37% remaining distance
to the architectural witness is almost exactly the 1.32% distance between the
two C++ witnesses and is not attributed to an unproven loop or vectorization
transformation.

The log reports dirty source repositories because the benchmark checkout was
already removing rejected historical logs and adding the two fixed-workload
qualification records. No benchmark source changed: `Silex.sx` remains
byte-identical to commit `50f6dc9`, with SHA-256
`45d3bb1f2b5fb95c5f358727a9f5ad86daea4533fa23c19d08129b1ce05fde94`.
The earlier
[`2026-09-07-141637-arm64-boids.log`](2026-09-07-141637-arm64-boids.log)
qualifies the preceding compiler commit `00f71d5` under the same protocol and
is retained as the immediate pre-candidate control.

## 2026-08-26 clean pre-fix regression control

[`2026-08-26-101358-arm64-boids.log`](2026-08-26-101358-arm64-boids.log) is a
user-run capture made after waiting for competing workloads. Its repository
metadata was clean and it follows the package runner's complete seven-round
protocol. It records the state immediately before restoring the immutable
Canvas fast path in Scene2D, and is retained as the regression control for that
change.

| Witness | Median | MAD | Range | Relative to C++ architectural |
| --- | ---: | ---: | ---: | ---: |
| Silex/GFX | 83.468 FPS | 0.69% | 82.889-84.631 FPS | -3.67% |
| C++ architectural | 86.645 FPS | 0.27% | 86.150-87.109 FPS | reference |
| C++ direct | 85.751 FPS | 0.15% | 85.610-86.741 FPS | -1.03% |

This control demonstrates the regression under an uncontended capture; it is
not the post-fix acceptance result. A matching capture from the corrected
revision must be compared with it before accepting the recovered performance.

## 2026-08-26 clean post-fix control

[`2026-08-26-110454-arm64-boids.log`](2026-08-26-110454-arm64-boids.log) is the
first clean seven-round capture of Scene2D commit `4d52dbd`, after restoring
the immutable Canvas fast path. The host had waited for competing workloads,
and every recorded configuration field matches the pre-fix control above.

| Witness | Median | MAD | Range | Relative to C++ architectural |
| --- | ---: | ---: | ---: | ---: |
| Silex/GFX | 83.548 FPS | 0.21% | 83.370-84.035 FPS | -3.13% |
| C++ architectural | 86.250 FPS | 0.12% | 85.951-86.952 FPS | reference |
| C++ direct | 85.646 FPS | 0.13% | 85.454-85.766 FPS | -0.70% |

This result is stable but remains below the earlier 87-88 FPS observations.
It therefore freezes the corrected revision under this machine state without
claiming that the wider Scene2D performance gap has been resolved.

## 2026-08-26 compact-packing candidate observation

[`2026-08-26-144618-arm64-boids.log`](2026-08-26-144618-arm64-boids.log) was
captured after a deep-sleep wake, with the compact instance-packing working
tree later committed as `12ce794`. The runner reports dirty source repositories,
so this is an exploratory control rather than clean acceptance evidence.

| Witness | Median | MAD | Range | Relative to C++ architectural |
| --- | ---: | ---: | ---: | ---: |
| Silex/GFX | 88.591 FPS | 0.37% | 84.277-88.919 FPS | -2.19% |
| C++ architectural | 90.575 FPS | 0.80% | 88.105-91.426 FPS | reference |
| C++ direct | 88.926 FPS | 2.05% | 85.924-90.963 FPS | -1.82% |

The higher absolute values across all three witnesses are consistent with host
state materially affecting throughput. The relative ordering still leaves C++
architectural ahead of Silex, while the wide Silex and C++ direct ranges make
small cross-process differences unsuitable as acceptance criteria.

## 2026-08-26 contended macOS ARM64 observation

[`2026-08-26-arm64-boids.log`](2026-08-26-arm64-boids.log) compares the three
4,000-boid executables on the same Apple M3 Pro host. All programs used
immediate presentation, a 960 x 640 logical window, a 1920 x 1280 framebuffer,
and a five-second measurement interval. One warm-up process per executable was
discarded, then seven isolated processes per witness were recorded in rotating
Silex, C++ architectural, C++ direct order.

The Codex agent remained active during this capture. A later user-run Silex
process reached 84.7 FPS, while a one-round runner smoke reached the expected
higher C++ ranges. This file is therefore retained as evidence of scheduling
sensitivity and raw historical output, not as the accepted performance
baseline. Replace its acceptance role with a capture produced from an external
terminal after closing Codex and other competing workloads.

| Witness | Median | MAD | Range | Relative to C++ architectural |
| --- | ---: | ---: | ---: | ---: |
| Silex/GFX | 81.664 FPS | 0.14% | 81.265-81.776 FPS | -3.66% |
| C++ architectural | 84.763 FPS | 0.11% | 84.535-85.065 FPS | reference |
| C++ direct | 84.110 FPS | 0.04% | 84.019-84.299 FPS | -0.77% |

The architectural C++ witness is the primary comparison because it matches
the ECS, SDL_GPU, shader, instancing, presentation, and data-layout costs of
the public Scene2D path. The direct SDL_Renderer witness exercises a different,
lower-level path and is retained only as a secondary throughput control.

The Silex median is 2.28% below the 83.573 FPS median archived by the
GFX.Physics Spec 13 acceptance session on the same host and compiler revision.
Because this capture had a competing workload and that older session used
another Scene2D revision, the difference does not by itself establish a code
regression.

## Capture protocol

New captures use the deterministic permutation and fixed-window stationarity
rule documented in [`../README.md`](../README.md#comparison-protocol) and
`../Protocol.json`. Historical captures above retain their original protocol
and acceptance status. Do not reinterpret their seven fixed-order processes as
new twelve-round stationary captures.

Each new record retains the raw log, `.log.json` analysis and `.log.seal.json`
artifact identity. Archive inconclusive records with their failure reasons;
never replace the accepted historical control with a more favorable threshold.
Do not archive serial numbers, hardware UUIDs, usernames or absolute home paths.
