# Silex compilation baseline

- Captured: `2026-09-02T02:34:51+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `74e7794c2af6f80cd32cb823fbbc78e35742b163`
- Benchmarks commit: `07ac49e73a2edb260aecac5b58cb3d37bf6b1cca`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 1.370 s | 1.360–1.460 s | 1.460 s | 1022.8 MiB | 0.0 MiB |
| `cold_no_cache` | 1.370 s | 1.360–1.390 s | 1.450 s | 1022.8 MiB | 0.0 MiB |
| `shared_packages` | 1.370 s | 1.360–1.530 s | 1.460 s | 1031.0 MiB | 203.7 MiB |
| `entry_modified` | 1.380 s | 1.370–1.410 s | 1.460 s | 1031.0 MiB | 338.2 MiB |
| `exact_hit` | 0.010 s | 0.010–0.010 s | 0.000 s | 7.8 MiB | 338.2 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.2 MiB | 0.0 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.000 s | 0.000 s | 4.8 MiB | 0.0 MiB |

Trace overhead on the cold profile: `+0.00%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
