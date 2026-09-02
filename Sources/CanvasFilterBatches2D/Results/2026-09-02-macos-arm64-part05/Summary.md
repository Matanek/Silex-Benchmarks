# Scene2D CanvasFilter batching

Seven independent Release processes per case after an in-process warm-up.
Each measured frame waits for GPU completion. Time is median, sample
variance and [minimum, maximum]. GPU bytes are the renderer's deterministic
cache-resident estimate; RSS is the operating-system process peak.

```text
date=2026-09-02T01:48:24Z
os=macOS 26.6.2 25G83
architecture=arm64
silex=silex 0.43.0
mode=release
processes_per_case=7
placements=16
benchmark_commit=377e781819e85a86f4e9a78212a525b58447df80
gpu_commit=e8a512b93346c3139760f6d5675d8044565f79f9
canvas_commit=9115713dbad490eef927fa4d553d4aa2599e7bcd
scene2d_commit=4ac06362a4246e2148ac31a42370a62db74ba16e
```

| Case | ms/frame median | Variance | Range | Filter draws | Pipelines | GPU estimate | RSS median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `unfiltered` | 0.1901 | 0.000025 | [0.1862, 0.1987] | 0 | 0 | 131072 | 121765888 |
| `shared` | 0.3417 | 0.000618 | [0.2954, 0.3774] | 36 | 1 | 196608 | 124895232 |
| `fragmented` | 1.3481 | 0.001238 | [1.2728, 1.3782] | 576 | 2 | 1179648 | 147980288 |

All processes retained one Canvas source render and reported zero CPU RGBA
uploads. `shared` performs one filter draw per frame for 16 placements;
`fragmented` performs 16 and alternates two cached programs. Results are
local macOS ARM64 evidence and do not predict another architecture or backend.
