# GFX.Font rasterization comparison

This benchmark compares the last direct `GFX.Canvas` SDL_ttf implementation
with the vector-font candidate through one unchanged public Silex source. It
does not open a window or involve UI, Viewer, Scene2D, GPU, scrolling, or frame
scheduling.

The workload uses the exact same bundled Noto Sans and Noto Sans Mono files,
font size, strings, and density (`2.0`) for both implementations. It covers the
first font load and render, retained static reuse, a retained ×10 soak, forced
static rerasterization, short dynamic labels, multi-script labels, cache
pressure, and a second pressure pass in reverse order.
Each raster must be non-empty. Heights and line counts must match exactly;
widths must remain within 1%, which admits deterministic hinting differences
well below one logical pixel per typical label. Pixel signatures are expected
to be deterministic per engine, not byte-identical between two different
rasterizers.

`RunComparison.sh` requires clean candidate repositories at these exact commits:

- SDL_ttf baseline `GFX.Canvas`:
  `4975f3f8db0628c9bb5740b6f2b77b676599072a`;
- vector candidate `GFX.Canvas`:
  `8c5e3178c222c7bd087dc2d5766a79bb438335ed`;
- vector candidate `GFX.Font`:
  `a1207ecd14cadfae438b4b7c8a4644610a0b30b6`;
- cumulative Silex compiler:
  `a7abd029060e6ebaa8b78d4c0426a8f3bf8e2b64`.

From this directory, run:

```sh
./RunComparison.sh
```

The runner builds both executables in isolated temporary workspaces, alternates
their execution order, and runs every case in seven independent Release
processes per engine. Per-case processes prevent unrelated allocator
high-water marks from accumulating across the campaign. The runner records raw
output, build logs, maximum RSS, metadata, a CSV, and a Markdown summary below
`Results/`. It extracts the SDL_ttf baseline from the recorded historical
`GFX.Canvas` commit, so the direct checkout remains on the current vector-font
implementation and no persistent baseline worktree is required.
Already downloaded SDL_ttf boundary archives are reused from the current
`GFX.Canvas` checkout; if the host archive is absent, normal package linking
downloads and verifies the historical artifact declared by the baseline.

By default the runner uses the Silex binary built in the sibling `Silex`
repository at the exact compiler commit above. `SILEX_BIN` may override the
binary, but the owning Toolchain repository must still be clean at that
recorded commit.

`retained_static` creates one Canvas snapshot and one text layer, then reuses
that exact layer 1,000 times. `retained_static_soak` repeats the same path
10,000 times so its process peak can be compared with the short retained case.
`forced_static_raster` intentionally rebuilds the wrapper and text layer; it is
not representative of a retained UI frame. Likewise, `pressure_first` is one
640-label pass, while `pressure_revisit` includes an unreported first pass and
a measured reverse pass. Their RSS values expose allocator high-water marks;
they are not silently presented as live cache residency.

On macOS the runner also executes `leaks --atExit` on the two-pass pressure
case and preserves its complete output. A zero-leak result does not erase the
reported maximum-RSS growth; it distinguishes live ownership leaks from
allocator/transient high-water behavior.

`Direct.sx` is a candidate-only attribution probe for bundled-face loading,
direct shaping, and per-glyph rasterization. Its explicit SHA-256 measurement
demonstrates why recomputing a cryptographic digest is not part of the normal
bundled-face load path.

The performance decision uses the complete load/measure/raster path relevant
to Canvas UI. The report still exposes each phase: shaping a new dynamic label
can be slower than SDL_ttf's measurement call even when the candidate's
rasterization makes the complete operation faster. Conversely, the retained
cases measure cache hits and must not be extrapolated from forced misses.
