# Lazy catalog closure comparison

This capture is compatible with
`2026-09-02-macos-arm64-program-closure`: the target, mode, machine, worker
count, repetitions, corpora, package revisions, and disposable root-cache
protocol match. The candidate compiler keeps public reexports and catalog
contributions discoverable through an in-memory source surface, then deeply
loads their providers only when an active reference crosses the binding.

## Wall-clock profiles

| Profile | Program closure | Lazy catalog closure | Delta |
| --- | ---: | ---: | ---: |
| `cold_no_trace` | 2.800 s | 1.350 s | -51.79% |
| `cold_no_cache` | 2.780 s | 1.350 s | -51.44% |
| `shared_packages` | 2.750 s | 1.330 s | -51.64% |
| `entry_modified` | 2.750 s | 1.330 s | -51.64% |
| `exact_hit` | 0.020 s | 0.010 s | -50.00% |
| `minimal_no_cache` | 0.010 s | 0.010 s | +0.00% |
| `non_gfx_no_cache` | 0.000 s | 0.000 s | +0.00% |

The fixed and non-GFX controls do not regress. The exact-hit values are below
the timer's useful resolution and remain cache hits before the frontend.

## Cold traced closure

The first cold traced sample records the same 23 packages and 374 discovered
modules in both captures.

| Metric | Program closure | Lazy catalog closure | Delta |
| --- | ---: | ---: | ---: |
| Frontend | 1.741 s | 0.646 s | -62.9% |
| Module loading | 76.510 ms | 50.938 ms | -33.4% |
| Composition | 166.303 ms | 94.440 ms | -43.2% |
| Specialization | 161.604 ms | 66.967 ms | -58.6% |
| Semantic analysis | 1.329 s | 0.427 s | -67.9% |
| Native lowering | 400.645 ms | 188.266 ms | -53.0% |
| Loaded modules | 183 | 122 | -33.3% |
| Deeply parsed modules | 188 | 129 | -31.4% |
| Indexed public declarations | n/a | 57 | in-memory only |
| Source bytes read | 2,268,339 | 1,798,070 | -20.7% |
| AST functions | 1,438 | 1,024 | -28.8% |
| Portable functions | 5,230 | 3,181 | -39.2% |
| Reachable and machine functions | 2,436 | 1,656 | -32.0% |
| Native output | 38,237,472 B | 35,241,120 B | -7.8% |

The reduced frontend closure also lowers median cold peak RSS from 1,709.6 MiB
to 1,022.8 MiB (-40.2%). Linking stays in the same range and is not credited
as a frontend improvement.

## Cache invariant

The source-surface index and retained source buffers exist only for one
compiler process. The candidate writes no persistent interface or index cache.
The maximum root cache observed by the modified-entry and exact-hit profiles
falls from 292.1 MiB to 269.0 MiB (-7.9%). The runner removed its single root
`.silex` and its redirected Zig caches after the campaign.

Separate Release probes compiled `CornellBox.sx` and
`FallingBodies/Main.sx`. They confirm that references to Scene3D and Physics
reactivate their deferred catalog providers and native boundaries.
