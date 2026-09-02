# Canvas effects 2D final campaign

Seven independent Release processes per case, each with 120 warm-up and
600 measured frames. CPU preparation/submit time is distinct from the GPU
queue drain. No reliable GPU timestamp is available on this backend, so the
campaign makes no GPU-time claim. RSS is the operating-system process peak;
texture bytes are the renderer's deterministic cache-resident estimate.

```text
date=2026-09-02T08:58:52Z
os=macOS 26.6.2 25G83
architecture=arm64
cpu=Apple M3 Pro
gpu=Apple M3 Pro
backend=Metal
silex=silex 0.43.0
mode=release
processes_per_case=7
warmup_frames=120
measured_frames=600
target=1920x1080
display_density=1
seed=12648430
vsync=false
presentation=false
voluntary_gpu_competitors=none
gpu_timestamp=unavailable
benchmark_commit=7ce7b749354af1438c7b1159371593b72f17d5fe
canvas_commit=4a382c6dd3a7f4e3db109f385f8daab3f28a54d3
scene2d_commit=aa5217b830604b4e0b2e0aa4264f1777479b3d56
```

| Case | CPU ms/frame median | Variance | MAD/median | Queue drain ms | Draws | Instances | Geometry uploads | Texture allocations | Texture bytes | Filtered pixels | RSS median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `analytic-static` | 82.2201 | 2.268022 | 1.08% | 4.8568 | 1 | 4096 | 0 | 0 | 0 | 0 | 178454528 |
| `analytic-transform` | 83.9814 | 2.385945 | 0.74% | 4.6245 | 1 | 4096 | 0 | 0 | 0 | 0 | 178520064 |
| `filtered-static` | 26.3964 | 0.448198 | 0.53% | 0.7621 | 128 | 128 | 0 | 0 | 5814848 | 1048576 | 288866304 |
| `filtered-dynamic` | 841.9523 | 29.335345 | 0.42% | 1.0192 | 1073 | 1142 | 38400 | 0 | 8876448 | 2097152 | 2082766848 |
| `fullscreen` | 0.1892 | 0.000005 | 1.10% | 0.3267 | 1 | 1 | 0 | 0 | 43401000 | 2073600 | 138379264 |

Correctness and structural gates are asserted inside every process: fixed
offscreen target, disabled presentation, zero CPU RGBA uploads, zero texture
allocations after warm-up, static-cache reuse, and bounded proportional mesh
uploads for the dynamic groups. `fullscreen` is an informational stress case,
not an ordinary-path non-regression baseline.
