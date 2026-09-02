# Filtered Canvas surfaces

Seven independent Release processes per case after an in-process warm-up.
Time is median, sample variance and [minimum, maximum]. GPU bytes are the
deterministic cache-resident estimate reported by the public renderer; RSS is
the operating-system process peak and is not interpreted as live GPU memory.

```text
date=2026-09-02T00:56:29Z
os=macOS 26.6.2 25G83
architecture=arm64
silex=silex 0.43.0
mode=release
processes_per_case=7
benchmark_commit=04def3236caa7d830fb8d3483a5cece67c887dac
canvas_commit=c3ca3d26660cd4dccbe6f3d07156a2d8931e2718
scene2d_commit=d0658145c80417b71b2d8d37b2866bed6e610e4c
```

| Case | ms/iteration median | Variance | Range | GPU estimate | RSS median |
| --- | ---: | ---: | ---: | ---: | ---: |
| `static` | 0.0465 | 0.000001 | [0.0456, 0.0479] | 1372536 | 182976512 |
| `transform_only` | 0.2797 | 0.000023 | [0.2713, 0.2835] | 2294136 | 115589120 |
| `content_mutation` | 2.7677 | 0.000848 | [2.7411, 2.8219] | 1372536 | 136282112 |
| `fullscreen` | 4.9635 | 0.001492 | [4.9227, 5.0241] | 48620800 | 117915648 |

All processes reported zero CPU RGBA uploads. `transform_only` samples one
retained surface into moving viewports and asserts that the source render count
does not change. The mutation cases assert a stable cache-entry count.
