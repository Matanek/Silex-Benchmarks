# Silex Benchmarks

`Silex-Benchmarks` gathers the public performance workloads for Silex and its
packages. The repository keeps each scenario together with its protocol,
external reference implementations, and raw results when available.

## Organization

All Silex benchmarks live under [`Sources/`](Sources/). They are not grouped
by package: each name directly describes the workload being measured.

A self-contained benchmark remains a direct file:

```text
Sources/RetainedCanvasGeometry.sx
Sources/RegexStreamingSearch.sx
Sources/UpdatingTextLayers2D.sx
```

A benchmark receives a directory only when it has multiple artifacts: large
sources, assets, a C++ reference implementation, a runner, a checker, or
baselines. Baselines always stay with the benchmark that produced them:

```text
Sources/Boids2D/
├── Silex.sx
├── Cpp/
├── RunComparison.sh
└── Baselines/
```

The [`Package.json`](Package.json) file defines `Sources` as the package
source root and declares every dependency required by the catalog.

## Catalog

| Benchmark | Purpose |
| --- | --- |
| `Boids2D/` | compare the public Scene2D/ECS/GPU path with two C++23 reference implementations |
| `FallingBodies2D/` | jointly load 2D physics, transform transfer, and rendering |
| `WorldRendering3D/` | measure an instanced 3D world across several GPU and presentation profiles |
| `PhysicsWorldScale2D.sx` | measure sparse motion and body piles at several scales |
| `RetainedCanvasGeometry.sx` | compile dense retained Canvas geometry |
| `UpdatingTextLayers2D.sx` | update retained text layers |
| `RetainedUIInteraction.sx` | measure UI layout, selection, snapshots, and rasterization |
| `TerminalScreenRendering.sx` | measure full terminal-screen rendering and updates |
| `WebViewBridgeRoundTrips/` | exercise 1,000 round trips through a WebView |
| `RegexStreamingSearch.sx` | stream-search through one million Unicode scalars |
| `NetworkFreshnessTracking.sx` | measure network freshness comparisons and trackers |

## Running benchmarks

Measurements are taken from Release builds. Debug runs are only used to verify
correctness and do not constitute performance results.

From the workspace root:

```sh
silex run Silex-Benchmarks/Sources/PhysicsWorldScale2D.sx --release
silex compile Silex-Benchmarks/Sources/FallingBodies2D/Main.sx --release -o /tmp/falling-bodies-2d
/tmp/falling-bodies-2d --smoke --immediate --no-panel
silex compile Silex-Benchmarks/Sources/WorldRendering3D/Main.sx --release -o /tmp/world-rendering-3d
(cd Silex-Benchmarks/Sources/WorldRendering3D && /tmp/world-rendering-3d --benchmark)
```

Campaigns that compare multiple executables document their protocol in their
own `README.md`. They must preserve raw output, repetition count, variance,
build mode, operating system, and architecture. A local baseline is never a
portable performance guarantee.

`Boids2D/Silex.sx` is a faithful copy of the historical benchmark: its
algorithm, constants, and measurement window were not rewritten during the
migration. `FallingBodies2D` likewise preserves its spawning behavior,
asynchronous scheduler, buffers, and options. Only diagnostics reserved for
`GFX.Physics` were removed so the benchmark remains a genuine public
consumer. Any future change to these workloads requires a new baseline and an
explicit justification.

Optimizer and backend benchmarks remain under `Silex/Toolchain/Benchmarks/`.
They are internal toolchain gates rather than public package campaigns.

Performance artifacts that intentionally inspect `package` details also
remain with their owners. This includes the Box2D oracle and fine-grained
solver profiles in `GFX.Physics`, as well as the worker-pool regression test
in `STD`: they verify an implementation, while the scenarios in this
repository cross a real package boundary.
