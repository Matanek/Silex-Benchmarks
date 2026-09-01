# GFX.Font rasterization comparison

Seven independent Release processes per engine; median [min, max] in milliseconds.
Negative deltas favor the vector candidate. Logical metrics and each engine's pixel
signatures are identical within each engine; every raster is non-empty. Heights and
line counts match exactly; deterministic width differences must remain within 1%.

```text
date=2026-09-01T09:27:53Z
os=macOS 26.6.2 25G83
architecture=arm64
silex=silex 0.43.0
compiler_commit=a7abd029060e6ebaa8b78d4c0426a8f3bf8e2b64
compiler_binary=/Users/nekmata/Projects/SilexProject/.specs/GFX-Vector-Font-System/Worktrees/spec-gfx-vector-fonts-09/Silex/Toolchain/zig-out/bin/silex
mode=release
density=2.0
repetitions=7
baseline_canvas=4975f3f8db0628c9bb5740b6f2b77b676599072a
candidate_canvas=8c5e3178c222c7bd087dc2d5766a79bb438335ed
candidate_font=a1207ecd14cadfae438b4b7c8a4644610a0b30b6
common_gfx=ddb5f09b615aeb36c75f9b2073dfefbacc77e6cd
common_assets=75170e3c260d7901537534afd55b6d9036e22280
common_std=5a018305fb470dfe00e94466150b3c04f207e252
monospace_sha256=65b5e2b2c4a1fba9ae8be1f026cb35b03dcb8886d9b2a4147054fde12f7e767d
default_sha256=bfb7bb691513f12e734dc346c03a03f784912432d7e3fa8e56efcf906fe86b3d
```

| Case | Phase | SDL_ttf baseline | Vector candidate | Delta |
| --- | --- | ---: | ---: | ---: |
| `cold_first` | load | 0.584 [0.571, 1.997] | 0.723 [0.675, 3.072] | +23.8% |
| `cold_first` | measure | 0.737 [0.679, 4.230] | 0.377 [0.359, 2.693] | -48.8% |
| `cold_first` | raster | 1.489 [1.452, 3.587] | 1.288 [1.186, 2.559] | -13.5% |
| `cold_first` | combined | 2.788 [2.702, 9.814] | 2.338 [2.220, 8.324] | -16.1% |
| `retained_static` | measure | 3.855 [3.612, 4.175] | 0.265 [0.259, 0.272] | -93.1% |
| `retained_static` | raster | 1.253 [1.245, 1.340] | 0.804 [0.786, 0.824] | -35.8% |
| `retained_static` | combined | 5.108 [4.869, 5.439] | 1.072 [1.053, 1.083] | -79.0% |
| `retained_static_soak` | measure | 35.972 [35.303, 38.179] | 2.056 [2.040, 2.119] | -94.3% |
| `retained_static_soak` | raster | 2.156 [2.039, 2.185] | 1.571 [1.546, 1.624] | -27.1% |
| `retained_static_soak` | combined | 38.128 [37.467, 40.349] | 3.632 [3.608, 3.718] | -90.5% |
| `forced_static_raster` | measure | 3.940 [3.742, 4.082] | 0.323 [0.298, 0.332] | -91.8% |
| `forced_static_raster` | raster | 887.983 [880.496, 923.419] | 426.769 [421.401, 444.843] | -51.9% |
| `forced_static_raster` | combined | 891.769 [884.436, 927.371] | 427.067 [421.714, 445.166] | -52.1% |
| `dynamic_short` | measure | 3.048 [2.877, 3.082] | 28.384 [26.876, 28.731] | +831.2% |
| `dynamic_short` | raster | 371.469 [364.951, 386.269] | 163.729 [155.197, 165.494] | -55.9% |
| `dynamic_short` | combined | 374.542 [367.890, 389.317] | 192.231 [182.073, 194.225] | -48.7% |
| `multi_script` | measure | 7.127 [7.021, 7.541] | 0.652 [0.631, 0.658] | -90.9% |
| `multi_script` | raster | 166.045 [163.169, 173.211] | 79.937 [79.016, 80.736] | -51.9% |
| `multi_script` | combined | 173.172 [170.190, 180.604] | 80.568 [79.668, 81.394] | -53.5% |
| `pressure_first` | measure | 6.404 [6.232, 6.663] | 41.641 [39.724, 42.208] | +550.2% |
| `pressure_first` | raster | 1103.179 [1085.412, 1141.437] | 427.171 [408.974, 432.469] | -61.3% |
| `pressure_first` | combined | 1109.583 [1091.645, 1148.100] | 469.379 [448.956, 474.279] | -57.7% |
| `pressure_revisit` | measure | 6.425 [6.210, 6.633] | 11.612 [11.538, 11.883] | +80.7% |
| `pressure_revisit` | raster | 999.773 [993.396, 1029.389] | 439.370 [434.135, 443.439] | -56.1% |
| `pressure_revisit` | combined | 1006.255 [999.801, 1036.022] | 451.155 [445.673, 455.242] | -55.2% |

| Case | SDL_ttf width milli-pixels | Vector width milli-pixels | Delta |
| --- | ---: | ---: | ---: |
| `cold_first` | 311000 | 311000 | +0.00% |
| `retained_static` | 344000 | 345000 | +0.29% |
| `retained_static_soak` | 344000 | 345000 | +0.29% |
| `forced_static_raster` | 344000000 | 345000000 | +0.29% |
| `dynamic_short` | 110058000 | 110412000 | +0.32% |
| `multi_script` | 51680000 | 51920000 | +0.46% |
| `pressure_first` | 310615000 | 311210000 | +0.19% |
| `pressure_revisit` | 310615000 | 311210000 | +0.19% |

| Case | SDL_ttf maximum RSS bytes | Vector maximum RSS bytes | Delta |
| --- | ---: | ---: | ---: |
| `cold_first` | 26509312.000 [26443776.000, 26542080.000] | 49479680.000 [49446912.000, 49496064.000] | +86.7% |
| `retained_static` | 26689536.000 [26640384.000, 26722304.000] | 49856512.000 [49856512.000, 49856512.000] | +86.8% |
| `retained_static_soak` | 26689536.000 [26640384.000, 26722304.000] | 49856512.000 [49840128.000, 49856512.000] | +86.8% |
| `forced_static_raster` | 26722304.000 [26624000.000, 26755072.000] | 82624512.000 [82608128.000, 82640896.000] | +209.2% |
| `dynamic_short` | 43532288.000 [43466752.000, 43565056.000] | 97959936.000 [97959936.000, 97976320.000] | +125.0% |
| `multi_script` | 49954816.000 [49872896.000, 50053120.000] | 60342272.000 [60293120.000, 60375040.000] | +20.8% |
| `pressure_first` | 52248576.000 [52215808.000, 52346880.000] | 123600896.000 [123568128.000, 123650048.000] | +136.6% |
| `pressure_revisit` | 52281344.000 [52248576.000, 52314112.000] | 167624704.000 [167608320.000, 167641088.000] | +220.6% |

Cold-process candidate RSS difference: +21.9 MiB. This is reported
separately as provider/runtime overhead; per-case peaks are not interpreted as live
cache residency without allocator evidence.

Retained ×10 soak RSS growth: +0.0 MiB. Forced pressure
second-pass peak growth: +42.0 MiB. The accompanying macOS
`leaks --atExit` pressure run reports 0 leaks for 0 total leaked bytes. The
forced-path growth therefore remains visible as allocator/high-water behavior,
while the retained UI path demonstrates the bounded plateau relevant to frames.

The end-to-end `combined` phase is the UI raster path used for the performance
decision. Cold loading and shaping misses remain visible as separate phases: a
miss-only `measure` regression is not relabeled as a gain even when the subsequent
rasterization makes the complete operation faster. Retained hits are reported
separately and must not be inferred from the forced rerasterization workloads.

## Candidate direct attribution

Seven independent Release processes; median [min, max] in milliseconds.
The SHA-256 phase is diagnostic and is absent from bundled-face loading.

| Phase | Vector candidate |
| --- | ---: |
| `hash_ms` | 324.257 [322.800, 359.968] |
| `face_ms` | 0.718 [0.658, 0.962] |
| `instance_ms` | 0.096 [0.078, 0.276] |
| `shape_ms` | 0.150 [0.139, 0.437] |
| `raster_ms` | 1.045 [1.000, 1.116] |

Direct probe maximum RSS bytes: 15351808.000 [15335424.000, 15384576.000].
