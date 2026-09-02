# Scene2D CanvasFilter batching

This public, offscreen benchmark compares 16 retained Canvas placements in
three configurations:

- `unfiltered`: all placements reuse the same source surface;
- `shared`: all placements reuse one filter result after one parameter update
  per measured frame;
- `fragmented`: each placement owns a parameter revision and alternates between
  two programs, forcing 16 filter draws and two cached pipelines per frame.

The Canvas source never changes. Every frame waits for submitted GPU work, and
the executable asserts source sharing, expected filter-pass multiplicity,
pipeline cardinality and zero CPU RGBA uploads. Timing assertions are kept out
of correctness tests.

Run seven independent Release processes for every case from the Part worktree:

```sh
Silex-Benchmarks/Sources/CanvasFilterBatches2D/RunCampaign.sh
```

The result contains raw stdout, `/usr/bin/time -l` output, metadata,
`measurements.csv` and `Summary.md`. Measurements made on macOS ARM64 are local
evidence only and do not predict another architecture or GPU backend.
