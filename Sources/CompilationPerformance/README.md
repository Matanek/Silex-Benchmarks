# Silex compilation performance

This campaign measures the native compilation stage shared by `silex compile`
and `silex run`. It deliberately uses `compile` so application startup, windows,
and frame loops do not contaminate compiler measurements.

The protocol keeps five independent cache profiles and two closure controls:

- `cold_no_trace`: Release compilation with `--nocache` and tracing disabled;
- `cold_no_cache`: the same miss with phase tracing enabled;
- `shared_packages`: a distinct GFX entry after another GFX application has
  populated the one root cache;
- `entry_modified`: the same entry path with only its source text changed;
- `exact_hit`: identical source, mode, target, output and compiler identity.
- `minimal_no_cache`: a generated `func main() {}` compiled without cache;
- `non_gfx_no_cache`: a real STD consumer compiled without GFX or cache.

`cold_no_trace` and `cold_no_cache` expose instrumentation overhead. The three
cached profiles are not interchangeable: only `exact_hit` is allowed to report
`hit_before_frontend`.
After the requested warm-ups, traced and untraced cold samples alternate their
execution order so filesystem and thermal drift do not always favor one mode.

## Cache safety

The runner accepts only a workspace root without an existing `.silex`. It then
creates exactly one cache at `<workspace>/.silex`, installs explicit workspace
links for every resolved package, verifies their paths, and records an ownership
marker. On exit it removes that cache only if the marker still matches. It
never reads, moves, clears, or deletes a pre-existing cache and never creates a
cache under Silex, Silex-Examples, Silex-Benchmarks, or a package.
The bootstrap linker's Zig local and global caches are redirected below the
campaign scratch directory and are removed with it on every exit.

For a Spec, run it from the root of that Spec's worktree group. Do not point it
at the ordinary `SilexProject` root, because that root intentionally owns the
developer's persistent cache and the runner will refuse it.

## Example

From the `Silex-Compilation-Performance` Part worktree root:

```sh
python3 Silex-Benchmarks/Sources/CompilationPerformance/Run.py \
  --workspace . \
  --packages-root /Users/nekmata/Projects/SilexProject/Packages \
  --silex Silex/Toolchain/zig-out/bin/silex \
  --primary Silex-Examples/Sources/ShapeGallery2D/Main.sx \
  --warm-source Silex-Examples/Sources/AnalogClock.sx \
  --non-gfx Silex/Examples/Distribution/Hello.sx \
  --runs 5 \
  --warmups 1 \
  --output Silex-Benchmarks/Sources/CompilationPerformance/Results/<capture>
```

Each sample preserves the compiler's structured phase trace, `/usr/bin/time`
output, stdout, command, user/system CPU, peak RSS, and total plus per-class
cache size before and after compilation. The trace records the compiler worker
count; it is currently one because the native compilation pipeline is serial.
`report.json` contains the complete machine-readable campaign and `SUMMARY.md`
contains medians and ranges. Performance comparisons must use the raw samples
and matching commits; timing is not a correctness assertion.
