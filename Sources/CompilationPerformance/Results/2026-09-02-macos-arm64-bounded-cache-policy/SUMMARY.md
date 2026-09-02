# Silex compilation baseline

- Captured: `2026-09-02T02:38:38+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `244f9aecf5a6630c7d790041dbcae19c131ee00e`
- Benchmarks commit: `b61c90580b0e926571a52aefe9f65cb648f86c03`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 1.400 s | 1.360–1.430 s | 1.480 s | 1022.8 MiB | 0.0 MiB |
| `cold_no_cache` | 1.420 s | 1.360–1.450 s | 1.500 s | 1022.8 MiB | 0.0 MiB |
| `shared_packages` | 1.440 s | 1.390–1.440 s | 1.520 s | 1030.0 MiB | 201.6 MiB |
| `entry_modified` | 1.380 s | 1.370–1.390 s | 1.460 s | 1030.0 MiB | 336.2 MiB |
| `exact_hit` | 0.010 s | 0.010–0.010 s | 0.000 s | 7.8 MiB | 336.2 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.2 MiB | 0.0 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.000 s | 0.000 s | 4.6 MiB | 0.0 MiB |

Trace overhead on the cold profile: `+1.43%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
