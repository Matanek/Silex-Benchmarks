# Boids performance baselines

This directory archives raw output from the three witnesses in
[`../Boids`](../Boids). The records are performance controls, not correctness
tests or portable timing claims.

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

Build all three executables before starting the measurements, close other
graphical workloads, and pass `4000 480` explicitly. Each process performs one
untimed rendered frame, then measures exactly 480 rendered frames with one
simulation step of 1/60 second per frame. Discard one complete warm-up process
for each executable, then rotate between the three executables for at least
seven recorded processes each. Reject any run whose count, measured frame
count, fixed delta, initial-state summary, four-step state summary,
presentation mode, logical window, pixel dimensions, scale, or density differs
from the archived configuration. Compare medians and report median absolute
deviation (MAD) as a percentage of the median.

Logs captured before this fixed-workload protocol used five seconds of
wall-clock time and each witness's real frame delta. They remain historical
controls for their original revisions, but their absolute FPS and boid
trajectories are not acceptance evidence for the fixed-workload protocol.

The benchmark-owned runner applies this protocol and produces a timestamped log:

```text
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

Future records retain the raw sentinel lines and the commits of every
user-linked repository in the resolved package closure. This includes
transitive packages such as `GFX.Application` and manifest dependencies such
as `GFX.Physics`, because either can change the produced executable without a
direct import in `Silex.sx`. Do not archive serial numbers, hardware UUIDs,
usernames, or absolute home paths.
