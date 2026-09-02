# Legacy no-effect regression gates

The unchanged public workloads were built in Release against the pre-Part07
package commits and the candidate commits, then run as seven alternating
independent processes after one discarded warm-up process per executable.

```text
date=2026-09-02T08:57:00Z
os=macOS 26.6.2 25G83
architecture=arm64
cpu=Apple M3 Pro
gpu=Apple M3 Pro
backend=Metal
mode=release
processes_per_version=7
order=alternating
voluntary_gpu_competitors=none
benchmark_commit=5e956f82234cffa55a08b006aae609011caf51cb
canvas_baseline=9115713dbad490eef927fa4d553d4aa2599e7bcd
canvas_candidate=4a382c6dd3a7f4e3db109f385f8daab3f28a54d3
scene2d_baseline=9d8098dd65770f64ec561c3e4dd1419836015669
scene2d_candidate=aa5217b830604b4e0b2e0aa4264f1777479b3d56
ui_baseline=6b990ac700840255afbbd38d7107054d9e9ee7b2
ui_candidate=a2ede7e81775db858eb0ebb91fd16a2efed5b2b8
rendering_baseline=f77863b4a6135b0ef634d0a6d7a459fda3c0c342
rendering_candidate=913d77ba7680bc8d2fc3940f4adae0515b7864a1
```

| Workload | Primary metric | Baseline median | Candidate median | Change | Baseline MAD | Candidate MAD | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `RetainedCanvasGeometry` | construction + vector_geometry ms | 8.4160 | 8.5640 | +1.76% | 1.85% | 0.19% | **pass** |
| `AnimatingCanvasGeometry` | ms per update | 1.2541 | 1.2566 | +0.20% | 0.41% | 0.21% | **pass** |
| `UpdatingTextLayers2D` | ms_per_frame | 10.6374 | 10.8117 | +1.64% | 0.95% | 2.49% | **pass** |
| `RetainedUIInteraction` | layered_presentation_ms_per_update | 0.3298 | 0.3421 | +3.74% | 0.10% | 0.42% | **pass** |

Secondary RetainedUIInteraction selection timings remain in every raw log and
do not compensate for its primary layered-presentation gate. Raw
`/usr/bin/time -l` files are retained for audit but include process-level residency rather than
renderer-owned live memory.
