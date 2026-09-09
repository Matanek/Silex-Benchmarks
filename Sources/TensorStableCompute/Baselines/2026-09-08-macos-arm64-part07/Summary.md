# Tensor 0.1.0 memory and performance campaign

Seven independent Release processes per group follow one Debug diagnostic run.
Every Release process runs the functional verifier before measuring. Timings
below are median [minimum, maximum] milliseconds per iteration, followed by
relative MAD. GPU compute regions include dispatch, explicit completion wait and
result allocation; cold rows also include first pipeline creation. Upload and
download are reported separately.

```text
date=2026-09-08T16:58:33Z
os=macOS 26.6.2 (25G83)
architecture=arm64
cpu=Apple M3 Pro
gpu=Apple M3 Pro
gpu_driver=Apple Metal supplied by macOS 25G83
memory_bytes=19327352832
silex=silex 0.43.0
diagnostic_mode=debug
measurement_mode=release
processes_per_group=7
dtype_cardinality=65536
equal_transfer_bytes=262144
elementwise_sizes=1024,65536,1048576
reduction_sizes=1024,65536,1048576
matmul_sizes=32,128,512
resident_chain_operations=5
benchmark_commit=a83da3838d53d88cbb7c06dce24a05da68b6c6e7
silex_commit=1c310ce356783ead3bb7607a34f1cd01b0580479
tensor_commit=bdcd0623d010a859368e76478978826b0a8ff5c8
gfx_gpu_commit=bb2378716f9c0b58b796870bd500fb2df9ab26d5
gfx_commit=727efa9356ab9488e884ab8207a97269b1aaf0ec
std_commit=5a018305fb470dfe00e94466150b3c04f207e252
```

## CPU construction and extraction

Equal cardinality: 65,536 elements. Construction receives an already populated
typed Silex array; extraction materializes the public typed array.

| Dtype | Bytes | Construction ms | Extraction ms |
| --- | ---: | ---: | ---: |
| `float32` | 262144 | 0.0136 [0.0108, 0.0486] (20.6%) | 9.4572 [8.3298, 10.4440] (4.2%) |
| `int8` | 65536 | 0.0236 [0.0130, 0.0400] (37.3%) | 11.0386 [9.1222, 12.6018] (7.8%) |
| `uint8` | 65536 | 0.0390 [0.0130, 0.6724] (5.1%) | 9.8534 [9.3790, 11.4270] (3.0%) |
| `int16` | 131072 | 0.0372 [0.0134, 0.0448] (18.3%) | 10.1418 [7.8092, 12.9070] (1.4%) |
| `uint16` | 131072 | 0.0128 [0.0108, 0.0342] (10.9%) | 10.5848 [10.2340, 12.2812] (3.3%) |
| `int32` | 262144 | 0.0176 [0.0114, 0.0388] (35.2%) | 10.6988 [8.8948, 11.9540] (9.2%) |
| `uint32` | 262144 | 0.0230 [0.0132, 0.0458] (33.9%) | 9.9556 [8.4812, 11.7140] (10.5%) |
| `int64` | 524288 | 0.0206 [0.0142, 0.0434] (11.7%) | 9.7252 [9.3328, 11.3818] (4.0%) |
| `uint64` | 524288 | 0.0172 [0.0112, 0.0410] (29.1%) | 11.3004 [8.4720, 13.4506] (4.2%) |

## Equal-cardinality transfers

| Dtype | Elements | Bytes | Upload ms | Upload MiB/s | Download ms | Download MiB/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `float32` | 65536 | 262144 | 6.4948 [6.0158, 8.5530] (7.4%) | 38.49 | 3.5182 [2.9510, 4.3534] (4.9%) | 71.06 |
| `int8` | 65536 | 65536 | 7.7272 [5.4260, 8.6672] (7.1%) | 8.09 | 3.7058 [3.0480, 4.4464] (5.6%) | 16.87 |
| `uint8` | 65536 | 65536 | 7.6886 [5.9210, 10.0664] (10.4%) | 8.13 | 3.3978 [2.5488, 3.9082] (9.5%) | 18.39 |
| `int16` | 65536 | 131072 | 7.6816 [6.0012, 9.4810] (17.2%) | 16.27 | 3.3892 [2.9114, 4.6680] (10.2%) | 36.88 |
| `uint16` | 65536 | 131072 | 8.4658 [6.0346, 9.7890] (8.0%) | 14.77 | 3.7042 [2.8206, 4.6030] (6.9%) | 33.75 |
| `int32` | 65536 | 262144 | 7.3106 [6.1036, 9.2590] (15.0%) | 34.20 | 4.1378 [3.3150, 4.3080] (4.1%) | 60.42 |
| `uint32` | 65536 | 262144 | 7.2068 [5.9084, 9.2712] (8.8%) | 34.69 | 3.5616 [3.0100, 4.7058] (15.5%) | 70.19 |
| `int64` | 65536 | 524288 | 7.6132 [5.7312, 10.2744] (5.1%) | 65.68 | 3.7806 [2.8032, 5.3680] (3.1%) | 132.25 |
| `uint64` | 65536 | 524288 | 7.5642 [6.8206, 9.5384] (6.6%) | 66.10 | 4.0382 [3.0964, 4.8264] (17.8%) | 123.82 |

## Equal-byte transfers

| Dtype | Elements | Bytes | Upload ms | Upload MiB/s | Download ms | Download MiB/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `float32` | 65536 | 262144 | 8.0666 [5.9892, 8.7226] (6.4%) | 30.99 | 3.4184 [2.9210, 5.0346] (5.8%) | 73.13 |
| `int8` | 262144 | 262144 | 11.1124 [9.6954, 15.2626] (12.8%) | 22.50 | 10.5356 [9.6030, 11.6954] (6.0%) | 23.73 |
| `uint8` | 262144 | 262144 | 12.5210 [10.2576, 14.7308] (8.9%) | 19.97 | 11.0266 [9.5258, 13.1808] (6.3%) | 22.67 |
| `int16` | 131072 | 262144 | 9.7260 [7.5042, 11.4348] (14.4%) | 25.70 | 6.2518 [5.4394, 8.0012] (5.4%) | 39.99 |
| `uint16` | 131072 | 262144 | 9.4406 [7.6026, 12.4438] (9.0%) | 26.48 | 5.9986 [5.2436, 8.0656] (11.3%) | 41.68 |
| `int32` | 65536 | 262144 | 6.9120 [6.0352, 8.3922] (5.4%) | 36.17 | 3.9884 [3.5696, 5.4698] (6.6%) | 62.68 |
| `uint32` | 65536 | 262144 | 8.6698 [7.0404, 9.0568] (4.5%) | 28.84 | 3.5862 [2.8504, 6.7462] (5.8%) | 69.71 |
| `int64` | 32768 | 262144 | 6.0442 [4.3162, 9.8616] (5.3%) | 41.36 | 2.7894 [2.0588, 2.8730] (3.0%) | 89.63 |
| `uint64` | 32768 | 262144 | 6.3460 [5.4828, 7.5772] (4.1%) | 39.39 | 2.6628 [1.6096, 2.9130] (9.4%) | 93.89 |

## Float32 compute grids

No upload or download occurs in GPU cold/hot rows. CPU and GPU compare the
same logical cardinality; matmul `size` is the side of two square matrices.

| Family | Size | CPU hot ms | GPU cold ms | GPU hot ms | Resident speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| `elementwise` | 1024 | 0.5833 [0.3848, 1.0299] (27.6%) | 5.2700 [2.9020, 8.9500] (18.2%) | 3.2839 [2.6300, 4.2099] (5.0%) | 0.18× |
| `elementwise` | 65536 | 34.8696 [32.4725, 38.1885] (3.9%) | 3.6470 [2.4890, 6.1370] (22.9%) | 3.3932 [2.4379, 3.6558] (5.1%) | 10.28× |
| `elementwise` | 1048576 | 550.1324 [506.8290, 613.6397] (5.0%) | 6.5730 [4.0800, 8.3580] (24.2%) | 3.8757 [2.4327, 4.9100] (14.7%) | 141.95× |
| `reduction` | 1024 | 0.4235 [0.3348, 0.5914] (18.5%) | 9.8030 [3.7790, 12.2920] (23.2%) | 3.5680 [3.4070, 4.2895] (3.5%) | 0.12× |
| `reduction` | 65536 | 23.8587 [23.1189, 26.3442] (2.3%) | 23.2300 [20.3550, 62.8450] (11.4%) | 19.2620 [18.2417, 39.2290] (4.7%) | 1.24× |
| `reduction` | 1048576 | 358.9283 [332.2750, 407.4880] (3.6%) | 291.0440 [283.8740, 469.0180] (2.3%) | 280.7187 [276.0927, 331.2167] (1.6%) | 1.28× |
| `matmul` | 32 | 10.9289 [1.3637, 12.3618] (5.8%) | 4.2020 [1.4100, 278.0760] (48.5%) | 3.6079 [0.9010, 4.2913] (10.2%) | 3.03× |
| `matmul` | 128 | 692.7877 [86.6947, 744.1473] (0.7%) | 4.7290 [1.5370, 10.1600] (25.8%) | 3.3907 [1.6443, 5.4013] (37.3%) | 204.32× |
| `matmul` | 512 | 46114.1050 [5815.2534, 47513.1250] (2.0%) | 5.9570 [2.2010, 10.0100] (44.6%) | 3.6500 [0.9220, 5.7970] (20.3%) | 12634.00× |

## Five-operation resident chain

The exact public chain is `add -> multiply -> matmul -> sum -> add`. Each GPU
cold/hot iteration records five compute passes and zero intermediate readbacks.
End-to-end adds two input uploads and the final scalar download to one hot chain.

| Size | CPU hot ms | Upload ms | GPU cold ms | GPU hot ms | Download ms | Resident speedup | End-to-end speedup |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 2.1679 [1.7102, 15.9148] (21.1%) | 21.4360 [3.1810, 28.9780] (35.2%) | 15.5870 [5.1680, 27.8870] (30.7%) | 8.4452 [3.1919, 19.5343] (62.2%) | 0.2650 [0.2030, 1.1540] (23.4%) | 0.26× | 0.07× |
| 128 | 91.8890 [90.1673, 774.1390] (1.9%) | 5.9750 [2.9460, 25.5530] (50.7%) | 14.6940 [10.9020, 30.9690] (25.8%) | 11.8920 [10.9317, 19.0513] (8.1%) | 0.4010 [0.3300, 0.8720] (17.7%) | 7.73× | 5.03× |
| 512 | 44293.3800 [5874.4067, 46787.9800] (5.6%) | 31.8600 [7.7450, 42.5650] (4.0%) | 134.2980 [125.6420, 337.9780] (3.7%) | 128.4070 [123.1720, 238.9860] (2.2%) | 0.6250 [0.3630, 1.1040] (35.8%) | 344.95× | 275.30× |

## Observed recommendation

- Elementwise resident crossover: 65536 elements.
- Global-sum resident crossover: 65536 elements.
- Square-matmul resident crossover: side 32.
- Five-operation chain resident crossover: side 128.
- Integer rows measure storage and exact round trips only; Tensor 0.1.0 does
  not claim integer GPU compute acceleration.
- Transfer-inclusive decisions must use the end-to-end column, not the resident
  speedup alone. Reuse GPU-resident inputs across several operations whenever
  upload and download would otherwise dominate.

**Release gate: passed on this machine.** The GPU beats the CPU on 2/3 representative resident-chain sizes; command counters show no hidden upload/download inside the chain.

## Measurement limitations

CPU process timings showed multiple scheduling regimes for `matmul/32`, `matmul/128`, `matmul/512`, `resident_chain_5/32`, `resident_chain_5/128`, `resident_chain_5/512`. All seven samples remain in the report with no outlier rejection. Use the median for this run, inspect the full range, and do not generalize the resulting speedup ratios.

## Peak process memory

`/usr/bin/time -l` peak resident size includes runtime and driver allocations.

| Group | Median bytes | Range bytes |
| --- | ---: | ---: |
| `types` | 83623936 | [81035264, 83722240] |
| `elementwise` | 89128960 | [87375872, 97632256] |
| `reduction` | 80248832 | [80134144, 81002496] |
| `matmul` | 76447744 | [76333056, 79052800] |
| `chain` | 78266368 | [75137024, 83886080] |

These results are local macOS ARM64 evidence for the exact commits above.
They do not predict another CPU architecture, GPU, driver or backend.
