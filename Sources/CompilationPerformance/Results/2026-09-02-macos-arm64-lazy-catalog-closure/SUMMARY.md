# Silex compilation baseline

- Captured: `2026-09-02T01:07:42+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `992155352d7800652aecafa9c51c279c0e22d1b9`
- Benchmarks commit: `824c530c90c4b27bf8aa613fc094313af315852f`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 1.350 s | 1.340–1.380 s | 1.410 s | 1022.8 MiB | 0.0 MiB |
| `cold_no_cache` | 1.350 s | 1.340–1.350 s | 1.410 s | 1022.8 MiB | 0.0 MiB |
| `shared_packages` | 1.330 s | 1.320–1.350 s | 1.420 s | 1030.0 MiB | 201.6 MiB |
| `entry_modified` | 1.330 s | 1.300–1.390 s | 1.400 s | 1030.0 MiB | 269.0 MiB |
| `exact_hit` | 0.010 s | 0.010–0.010 s | 0.000 s | 7.7 MiB | 269.0 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.1 MiB | 0.0 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.000 s | 0.000 s | 4.7 MiB | 0.0 MiB |

Trace overhead on the cold profile: `+0.00%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
