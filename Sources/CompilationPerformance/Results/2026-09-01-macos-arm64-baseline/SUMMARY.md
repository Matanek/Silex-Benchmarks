# Silex compilation baseline

- Captured: `2026-09-01T23:49:12+0200`
- OS: `macOS-26.6.2-arm64-arm-64bit`
- Architecture: `arm64`
- Runs per profile: `5`
- Silex commit: `844334b515f98818cadc6ddc0ef586dde7c92cec`
- Benchmarks commit: `192d1789cc48374938789af1120c6a2b430c776d`
- Examples commit: `3172344d43585b975b03b4baf691a2183243f5da`

| Profile | Median wall | Range | Median CPU | Median peak RSS | Maximum root cache |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cold_no_trace` | 4.110 s | 4.060–4.290 s | 4.170 s | 2053.4 MiB | 0.2 MiB |
| `cold_no_cache` | 4.180 s | 4.090–4.220 s | 4.210 s | 2053.5 MiB | 0.2 MiB |
| `shared_packages` | 4.050 s | 4.020–4.090 s | 4.150 s | 2068.6 MiB | 283.6 MiB |
| `entry_modified` | 4.230 s | 4.160–4.760 s | 4.320 s | 2068.7 MiB | 282.9 MiB |
| `exact_hit` | 0.020 s | 0.020–0.020 s | 0.010 s | 11.7 MiB | 282.9 MiB |
| `minimal_no_cache` | 0.010 s | 0.000–0.010 s | 0.000 s | 6.1 MiB | 0.2 MiB |
| `non_gfx_no_cache` | 0.000 s | 0.000–0.010 s | 0.000 s | 5.2 MiB | 0.2 MiB |

Trace overhead on the cold profile: `+1.70%`.

`cold_no_cache` measures a real compiler miss with `--nocache`. `shared_packages` compiles a distinct entry after another GFX entry. `entry_modified` changes only the entry text. `exact_hit` repeats the same source, options and output after priming. `minimal_no_cache` and `non_gfx_no_cache` expose fixed and non-GFX closure costs.
