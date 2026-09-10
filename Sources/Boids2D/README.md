# Boids C++/Silex

This directory contains three witnesses used to separate native code quality
from the architectural cost of GFX's public Scene2D path:

- Silex uses injected systems, ECS, Rendering, Scene2D, SDL_GPU, the retained
  drawing shader, and one instanced draw;
- C++ architectural uses EnTT, SDL_GPU, the same retained drawing shader, the
  same vertex and instance layouts, and one instanced draw;
- C++ direct keeps the minimal `std::vector` and SDL_Renderer implementation as
  a lower-layer throughput witness.

All three programs preserve the same quadratic algorithm, one flock snapshot per
frame, the same simulation constants, a 960 × 640 logical window requesting a
high-density framebuffer, and immediate presentation without VSync. Every
measured process performs one untimed warm-up frame followed by the same fixed
number of frames at a fixed simulation delta of 1/60 second. Pass `4000 480`
explicitly to every executable for a valid default comparison. Always compare
the reported workload, semantic witness, logical and pixel dimensions; a run
whose frame count, fixed delta, state, presentation mode, or dimensions differ
is invalid.

## Silex/GFX

From the SilexProject workspace root:

```sh
Silex/Toolchain/zig-out/bin/silex compile \
    Silex-Benchmarks/Sources/Boids2D/Silex.sx \
    -o /private/tmp/gfx-boids-silex
/private/tmp/gfx-boids-silex 4000 480
```

The output has this form:

```text
SILEX_GFX_BOIDS count=4000 frames=480 fixed_delta=0.016666668 state_step=4 initial_px=... state_px=... present=immediate fps=80.0 window=960.0x640.0 pixels=1920.0x1280.0 scale=2.0 density=2.0
```

## C++23 witnesses

The C++ witnesses require an SDL3 development installation and the
`shadercross` command discoverable by CMake. The build uses an installed EnTT 4
package when available or fetches the pinned `v4.0.0` release otherwise. These
are benchmark-only build dependencies and do not enter the Silex package or
its public API. The architectural witness compiles the live
`Packages/GFX.Scene2D/Shaders/Drawing.hlsl` source from the sibling workspace
checkout so the C++ and Silex paths cannot silently measure different shaders.

```sh
cmake \
    -S Silex-Benchmarks/Sources/Boids2D/Cpp \
    -B /private/tmp/gfx-boids-cpp \
    -DCMAKE_BUILD_TYPE=Release
cmake --build /private/tmp/gfx-boids-cpp --config Release
/private/tmp/gfx-boids-cpp/BoidsCppDirect 4000 480
/private/tmp/gfx-boids-cpp/BoidsCppArchitectural 4000 480
```

The direct output has this form:

```text
CPP_DIRECT_BOIDS count=4000 frames=480 fixed_delta=0.0166666675 state_step=4 initial_px=... state_px=... present=immediate fps=86.0 window=960x640 pixels=1920x1280 scale=2.0 density=2.0
```

The architectural output has this form:

```text
CPP_ARCHITECTURAL_BOIDS count=4000 frames=480 fixed_delta=0.0166666675 state_step=4 initial_px=... state_px=... ecs=entt renderer=sdl_gpu present=immediate fps=86.0 window=960x640 pixels=1920x1280 scale=2.0 density=2.0
```

## Comparison protocol

`RunComparison.sh` builds and hashes all three Release executables once, then
runs six warm-up rounds and twelve measured rounds at 4,000 boids and 480
frames. Every six-round cycle executes all six permutations of the witnesses;
each occupies each position twice. The raw log records actual process order,
all warm-ups, stdout/stderr, and all fixed-workload/state/display sentinels.
Failed processes leave a `.partial` log and cannot produce a timing verdict.

```sh
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

The runner changes to its workspace root before compilation. A Spec uses its
own compiler and workspace package links; a package escaping that closure is
rejected. `--silex-compiler` selects another exact compiler without changing
package resolution. `--build-dir` selects an explicit reusable artifact
location; the default is keyed by workspace and compiler path.

`Provenance.py` seals compiler bytes and commit, clean package commits,
manifest-selected native artifact checksums, source and shader hashes,
C++ compiler/configuration, EnTT revision, SDL libraries, generated shaders and
executable hashes. `--skip-build` verifies this seal before timing, and the
runner verifies it again afterward. Replacing a compiler, source, native
library or executable requires rebuilding. The seal is copied beside the raw
log as `.seal.json`; source changes during a build reject the seal.

The versioned rule in `Protocol.json` is a proposed measurement rule, independent
of optimizer changes. It never changes the historical Part 05 control. Exactly
rounds 1–6 are excluded from statistics and retained as raw evidence; exactly
rounds 7–18 are analyzed. There is no adaptive trimming or search for a favorable
window. Each witness and both paired Silex/C++ ratio sequences must satisfy:

- MAD / median at most 1%;
- full range / median at most 4%;
- absolute least-squares drift across the complete retained window at most 1%;
- absolute shift between the two half-window medians at most 1%.

A second capture of the same artifacts must satisfy those same gates and
repeat every median within 1%. These stationarity checks are measurement
quality gates, not a confidence interval or proof of performance parity.
A warming retained window, loaded host or outlier makes the result inconclusive;
thresholds must not be weakened after observing an optimizer candidate.

The runner prints a compact summary and writes complete progressions, paired
ratios, median, MAD, range, drift, excluded/retained windows and failure reasons
to `.log.json`. Exit 0 means stationary, 2 means inconclusive/invalid protocol,
and other nonzero exits mean build, semantic, provenance or process failure.
The historical 87.165 FPS median and 98.064% steady ratio remain explicitly
identified as controls with their original protocol; neither is rebaselined by
this instrument change. Historical fixed-order logs remain archived unchanged.

```sh
python3 Silex-Benchmarks/Sources/Boids2D/TestProtocol.py
python3 Silex-Benchmarks/Sources/Boids2D/Protocol.py analyze /path/to/capture-boids.log
python3 Silex-Benchmarks/Sources/Boids2D/Protocol.py compare /path/to/first-boids.log /path/to/second-boids.log
```

`--count`, `--frames`, `--runs` and `--warmups` remain available for diagnostic
smokes; noncanonical captures cannot pass the sealed analysis. `--output` sets
the raw capture path. Output paths are never overwritten. Use `--wait` in an
external terminal when competing work needs to stop after compilation; idle
applications may remain open.

The architectural C++ witness is the closest comparison for Silex/GFX. It
matches the major ECS, GPU upload, shader, instancing, presentation, and data
layout costs without pretending to duplicate GFX's scheduler or FrameGraph.
The direct witness remains a useful lower-layer ceiling, not a layer-for-layer
comparison.
