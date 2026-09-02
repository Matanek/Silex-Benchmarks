# Bounded compiler workers candidate

This capture evaluates Silex
`a2ac6bd0a4569954fb67e61d538fb5daa5896c1e` and the benchmark runner
`553c3228ab58763c4da90913987a9965c3c7c905` on the same Apple M3 Pro,
corpus, package commits, and single disposable root-cache protocol as the
accepted Part 04 capture. The controlled reference in
`2026-09-02-macos-arm64-bounded-workers-1` uses the same binaries and inputs
with one compiler worker; this directory forces four workers.

The compiler parallelizes only independent per-function Release optimization
and ARM64 lowering. It selects one worker below 256 reachable functions and at
most four otherwise, bounded by the available CPUs. Each spawned worker owns a
2 MiB stack. Global summaries, inlining, SSA promotion, canonical string-table
construction, cache reads and publications, emission, linking, diagnostics,
and output publication remain sequential barriers.

## Parallel gain

Against the controlled one-worker capture, four workers reduce the cold median
from `1.34 s` to `1.22 s` (`-8.96%`), shared packages from `1.06 s` to
`0.95 s` (`-10.38%`), and an entry modification from `1.05 s` to `0.97 s`
(`-7.62%`). The exact hit remains `0.01 s`.

On the traced cold profile, median optimization falls from `71.92 ms` to
`60.12 ms` (`1.20x`) and ARM64 lowering from `184.71 ms` to `91.45 ms`
(`2.02x`). Relative to four-way ideal scaling, these correspond to useful
parallel efficiencies of `30.0%` and `50.5%`. The conservative residual above
an ideal four-way split is `42.14 ms` for optimization and `45.27 ms` for
lowering; each residual includes both the phase's intentional sequential work
and worker coordination, so it is an upper bound rather than a claim that all
of that time is scheduler overhead. Linking remains the largest sequential
native phase at about `378 ms`.

Median cold peak RSS rises from `1023.3 MiB` with one worker to `1033.4 MiB`
with four (`+10.1 MiB`). It remains about half of the Part 01 baseline
(`2053.5 MiB`) and cannot grow with the number of modules because the pool and
per-worker stacks are fixed. The whole cold compilation consumes `1.45 s` of
CPU for `1.22 s` wall time; the serial frontend and linker intentionally limit
whole-pipeline CPU occupancy.

## Spec completion thresholds

Compared with the accepted Part 01 reference, the final cold median falls from
`4.11 s` to `1.22 s` (`-70.3%`, `3.37x` faster). Shared packages improve from
`4.05 s` to `0.95 s` (`4.26x`) and entry modification from `4.23 s` to
`0.97 s` (`4.36x`). The exact hit is `0.01 s`, below the `0.05 s` limit, and
the direct-path minimal program remains `0.01 s`.

The maximum root cache is exactly `342.8 MiB` in both the one-worker and
four-worker campaigns. The value remains the admitted current working set from
Part 04, above the `320 MiB` rolling-history reserve without turning that
reserve into an admission quota. Parallel work performs no concurrent cache
mutation and introduces no new cache class, generation, or historical key.

## Correctness and reproducibility

Tests serialize and compare portable IR and ARM64 machine IR with one, two,
and four workers over 273 functions. A full ShapeGallery2D Release compilation
with providers, boundaries, shaders, composition, and 1,656 reachable
functions produced the same executable SHA-256 with one, two, and four workers
when the output path was held constant:
`1bbed32c60bd0e1624f9dc65d2037fd1a5f3c1954027b771265e07929e017fc8`.
The same semantic error also produced identical status and diagnostic text.

`zig build check` and `zig build test` are green with workers active, including
the rolling-retention, oversized-current-set, later-small-set, identity
rotation, corruption, atomic publication, ARM64, and X64 portability coverage.
The executable corpus reports `154 passed; 0 failed`. The five-run benchmark
campaigns complete without deadlock or partial cache entries, and the runner
removes its sole root `.silex` after every campaign.

`GFX` and `GFX.Application` had advanced beyond the Part 04 corpus. Both
campaigns therefore used temporary clean local clones at the exact recorded
Part 04 commits; all other packages were linked from clean matching checkouts.
The comparison gate accepted the two reports with worker count as their only
provenance difference.

After the campaign, the acceptance sweep rebuilt the exact compiler commit and
compiled every one of the 34 `Silex-Examples` entry points from the shared
worktree root with relative paths and `--nocache`. All 34 compile in Debug and
all 34 compile in Release with four workers. The sweep exposed and corrected a
missing explicit `GFX.GPU.Commands` extension import in `DirectGPUTriangle` at
Silex-Examples commit `dc5a4413b97155c3aa049b924c4b8c2852e9a208`;
the measured ShapeGallery2D corpus is unchanged. The validation workspace
contained one root `.silex` directory, no nested caches, and only 404 KiB of
package-link metadata after the no-cache sweeps.

## Final local integration

The accepted Spec was combined with the newer local default-branch changes at
Silex commit `3d21c0ee22c26539262e361711b8f7106c3e8499` and Silex-Examples
commit `be8dbb1fe4fe904b3f1b02cbba96450dd0ee4673`. Both `zig build check` and
`zig build test` remain green with 154 of 154 executable scenarios. The
current catalogue has grown to 35 entry points; all 35 compile without cache
from relative root paths in both Debug and Release with four workers.

A fresh five-run campaign on the current translated ShapeGallery2D source
records a `1.17 s` cold median, `0.94 s` for both shared packages and an entry
modification, a `0.01 s` exact hit, and a maximum cache of `342.8 MiB`. Because
the translated source has a different content hash, a second campaign used a
byte-identical copy of the accepted corpus with the same package commits. The
strict comparison gate accepts it: its cold median is `1.25 s` (`+2.46%` from
the Part 05 capture), shared packages `1.01 s` (`+6.32%`), entry modification
`1.00 s` (`+3.09%`), exact hit `0.01 s`, maximum cache `342.8 MiB`, and cold
peak RSS `1030.5 MiB`. Every measured change remains below the 10% regression
gate while preserving the Spec-wide improvement over the `4.11 s` baseline.
