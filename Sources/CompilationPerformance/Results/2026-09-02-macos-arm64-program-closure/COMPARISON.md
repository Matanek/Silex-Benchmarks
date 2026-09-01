# Portable program closure comparison

`Compare.py` accepted the baseline and candidate as comparable: the machine,
target, mode, repetitions, corpus hashes, package revisions and disposable
single-root cache protocol match.

| Profile | Baseline | Candidate | Change |
| --- | ---: | ---: | ---: |
| `cold_no_trace` | 4.110 s | 2.800 s | -31.87% |
| `cold_no_cache` | 4.180 s | 2.780 s | -33.49% |
| `shared_packages` | 4.050 s | 2.750 s | -32.10% |
| `entry_modified` | 4.230 s | 2.750 s | -34.99% |
| `exact_hit` | 0.020 s | 0.020 s | 0.00% |

The traced cold GFX program contains 5,230 portable functions. Closure retains
2,436 of them for both ARM64 and X64, a reduction of 53.42%. The median closure
cost is 4.57 ms. Median Release optimization falls from 200.17 ms to 98.08 ms,
and median lowering falls from 1.646 s to 459.30 ms. The emitted executable
falls from 49,358,480 bytes to 38,237,472 bytes.

Median cold peak RSS falls from 2,053.5 MiB to 1,709.6 MiB. Minimal and non-GFX
controls remain at their baseline medians, and exact cache hits remain 20 ms.

This change adds no cache directory, cache artifact class, retention rule or
quota. The campaign used one owned `.silex` at the worktree-group root and
removed it on completion. Cold `--nocache` samples retained only the 0.2 MiB
workspace-link context. The largest existing-cache sample was 292.1 MiB versus
283.6 MiB in the baseline; this Part deliberately leaves that existing
retention policy unchanged for the cache-focused Parts of the Spec.

Correctness evidence also includes 154 passing language tests, a macOS ARM64
execution smoke, Linux X64 and Windows X64 structural builds, and an automated
sentinel test proving that unreachable function code and data are absent from
all three backend images.
