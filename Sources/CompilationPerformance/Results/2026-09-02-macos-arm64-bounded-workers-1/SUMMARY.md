# Silex compilation baseline

- Captured: `2026-09-02T05:37:06+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `a2ac6bd0a4569954fb67e61d538fb5daa5896c1e`
- Benchmarks commit: `553c3228ab58763c4da90913987a9965c3c7c905`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 1.340 s | 1.330–1.340 s | 1.400 s | 1023.2 MiB | 0.0 MiB |
| `cold_no_cache` | 1.330 s | 1.330–1.340 s | 1.400 s | 1023.3 MiB | 0.0 MiB |
| `shared_packages` | 1.060 s | 1.040–1.110 s | 1.150 s | 1024.2 MiB | 208.5 MiB |
| `entry_modified` | 1.050 s | 1.040–1.070 s | 1.140 s | 1024.2 MiB | 342.8 MiB |
| `exact_hit` | 0.010 s | 0.010–0.010 s | 0.000 s | 5.2 MiB | 342.8 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.1 MiB | 0.0 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.000 s | 0.000 s | 4.7 MiB | 0.0 MiB |

Trace overhead on the cold profile: `-0.75%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
