# Silex compilation baseline

- Captured: `2026-09-02T03:48:59+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `33d21d703b0ac6c4fe73a71d4a951874de87f4b2`
- Benchmarks commit: `81cd5526310e44af7391d4823d6392120ce71c1a`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 1.400 s | 1.390–1.530 s | 1.480 s | 1023.0 MiB | 0.0 MiB |
| `cold_no_cache` | 1.410 s | 1.370–1.570 s | 1.490 s | 1023.0 MiB | 0.0 MiB |
| `shared_packages` | 1.130 s | 1.070–1.170 s | 1.220 s | 1023.9 MiB | 208.5 MiB |
| `entry_modified` | 1.090 s | 1.080–1.090 s | 1.180 s | 1024.0 MiB | 342.8 MiB |
| `exact_hit` | 0.010 s | 0.010–0.010 s | 0.000 s | 5.2 MiB | 342.8 MiB |
| `minimal_no_cache` | 0.010 s | 0.010–0.010 s | 0.000 s | 6.1 MiB | 0.0 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.000 s | 0.000 s | 4.7 MiB | 0.0 MiB |

Trace overhead on the cold profile: `+0.71%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
