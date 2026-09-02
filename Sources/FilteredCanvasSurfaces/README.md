# Filtered Canvas surfaces

This public benchmark exercises `GFX.Scene2D.CanvasSurfaceRenderer` without a
window or private renderer access. It distinguishes four costs:

- `static`: repeated requests for one unchanged bounded filtered group;
- `transform_only`: GPU composition of the same retained surface into moving
  viewports, with no source rerender;
- `content_mutation`: a bounded 320×180 filtered group whose contents change;
- `fullscreen`: the same mutation path at 1920×1080.

Every mutation preserves the authored Canvas and layer identities, reuses its
previous snapshot, waits for submitted GPU work, verifies stable cache-entry
residency and rejects CPU RGBA uploads. The transform case waits on each sampled
composition and asserts that its source render count remains unchanged.

Run the seven-process Release campaign from the Part worktree:

```sh
Silex-Benchmarks/Sources/FilteredCanvasSurfaces/RunCampaign.sh
```

The results directory contains raw stdout, `/usr/bin/time -l` output,
`measurements.csv`, metadata and `Summary.md`. The summary reports median,
sample variance, range, peak process RSS and the renderer's cache-resident GPU
byte estimate. macOS ARM64 measurements are local evidence, not a portable X64
performance claim.
