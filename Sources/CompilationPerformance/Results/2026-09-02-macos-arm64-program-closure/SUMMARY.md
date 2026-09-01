# Silex compilation baseline

- Captured: `2026-09-02T00:22:14+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `8465e082219862925d831c8aeb6205282217e746`
- Benchmarks commit: `31fe651d3990edd1235f70d1d0baf71c78d4528b`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 2.800 s | 2.690–2.850 s | 2.830 s | 1709.6 MiB | 0.2 MiB |
| `cold_no_cache` | 2.780 s | 2.680–2.910 s | 2.840 s | 1709.6 MiB | 0.2 MiB |
| `shared_packages` | 2.750 s | 2.740–2.860 s | 2.820 s | 1724.7 MiB | 220.1 MiB |
| `entry_modified` | 2.750 s | 2.740–2.770 s | 2.820 s | 1724.7 MiB | 292.1 MiB |
| `exact_hit` | 0.020 s | 0.010–0.020 s | 0.010 s | 11.7 MiB | 292.1 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.1 MiB | 0.2 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.010 s | 0.000 s | 4.7 MiB | 0.2 MiB |

Trace overhead on the cold profile: `-0.71%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
