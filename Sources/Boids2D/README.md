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

Compile before starting the series, close other graphical workloads, perform
several warm-up runs, and then rotate between the three executables. Compare at
least five results per version and use the medians. Compilation, shader
translation, initialization, and the first rendered frame are not part of the
FPS measurement.

`RunComparison.sh` automates that complete protocol from any working directory:

```sh
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --wait
```

The default temporary build directory is keyed by both the resolved workspace
root and the selected Silex compiler. Direct checkouts, Spec worktrees, and A/B
compiler runs therefore never reuse the same witness or CMake cache. Use
`--build-dir` only when an explicit reusable location is desired.

The worktree compiler is selected by default. To compare another compiler
against the exact same benchmark source and package closure, pass its executable
explicitly:

```sh
Silex-Benchmarks/Sources/Boids2D/RunComparison.sh \
    --silex-compiler /path/to/Silex/Toolchain/zig-out/bin/silex \
    --wait
```

The log records the selected compiler path and the Git commit of the repository
that contains it. A compiler outside a Git worktree remains runnable, but its
commit is recorded as unavailable and the capture cannot be considered clean
acceptance evidence.

By default it builds all three Release executables, discards one warm-up per
witness, records seven 480-frame processes per witness in Silex, C++
architectural, C++ direct order, and writes a timestamped raw log under
`Baselines/`. Before accepting any timing it validates the boid count, frame
count, fixed delta, normalized display metadata, and numerical summaries of the
initial state and state after four simulation steps. The final terminal table
and log comments report the median, range, median absolute deviation (MAD), and
relative difference from the architectural C++ witness.
It also rejects clean-baseline status when any repository in the resolved
Silex package closure is dirty and records every corresponding commit,
including `GFX.Application` and `GFX.Physics` even though Boids does not import
them directly.

Run it from an external terminal with `--wait` when Codex has active agents or
another workload may affect the result. After the build finishes, stop active
competing work and press Return in the terminal; idle Codex, editor, and other
application processes need not be closed. Use `--frames`, `--runs`, `--warmups`,
`--output`, `--silex-compiler`, or `--build-dir` to override the capture without
editing the script; `--skip-build` reuses executables already present in that
compiler-specific build directory.

The architectural C++ witness is the closest comparison for Silex/GFX. It
matches the major ECS, GPU upload, shader, instancing, presentation, and data
layout costs without pretending to duplicate GFX's scheduler or FrameGraph.
The direct witness remains a useful lower-layer ceiling, not a layer-for-layer
comparison.
