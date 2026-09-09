# Tensor 0.1.0 memory and performance campaign

Seven independent Release processes per group follow one Debug diagnostic run.
Every Release process runs the functional verifier before measuring. Timings
below are median [minimum, maximum] milliseconds per iteration, followed by
relative MAD. GPU compute regions include dispatch, explicit completion wait and
result allocation; cold rows also include first pipeline creation. Upload and
download are reported separately.

```text
date=2026-09-09T03:01:32Z
os=macOS 26.6.2 (25G83)
architecture=arm64
cpu=Apple M3 Pro
gpu=Apple M3 Pro
gpu_driver=Apple Metal supplied by macOS 25G83
memory_bytes=19327352832
silex=silex 0.44.0
diagnostic_mode=debug
measurement_mode=release
processes_per_group=7
dtype_cardinality=65536
equal_transfer_bytes=262144
elementwise_sizes=1024,65536,1048576
reduction_sizes=1024,65536,1048576
matmul_sizes=32,128,512
resident_chain_operations=5
benchmark_commit=d81dc36064bf1e5e3f7db4c92e78386628d63703
silex_commit=1e1919297ef3889b5e9dec4428465fc47e153475
tensor_commit=cd91b10742cf4ea2011e43c68c3cd25424697740
gfx_gpu_commit=db65dc3f7d6c37d66e5b9b31faa4f585cf82d518
gfx_commit=1b5084f7d8605a678df2a0ff7da46af3d692a20c
std_commit=80aabd9a2de919af52dc0b8bf2d0f9de50aa75c5
```

## CPU construction and extraction

Equal cardinality: 65,536 elements. Construction receives an already populated
typed Silex array; extraction materializes the public typed array.

| Dtype | Bytes | Construction ms | Extraction ms |
| --- | ---: | ---: | ---: |
| `float32` | 262144 | 0.0052 [0.0050, 0.0096] (3.8%) | 0.9308 [0.8932, 0.9400] (0.9%) |
| `int8` | 65536 | 0.0050 [0.0046, 0.0052] (4.0%) | 0.9768 [0.9686, 1.0022] (0.5%) |
| `uint8` | 65536 | 0.0052 [0.0050, 0.0058] (3.8%) | 0.9794 [0.9726, 0.9990] (0.7%) |
| `int16` | 131072 | 0.0052 [0.0048, 0.0062] (3.8%) | 0.9858 [0.9738, 1.0164] (0.7%) |
| `uint16` | 131072 | 0.0050 [0.0046, 0.0060] (8.0%) | 0.9778 [0.9740, 1.0164] (0.1%) |
| `int32` | 262144 | 0.0054 [0.0046, 0.0058] (3.7%) | 1.0016 [0.9920, 1.0106] (0.4%) |
| `uint32` | 262144 | 0.0048 [0.0042, 0.0060] (8.3%) | 0.9810 [0.9678, 0.9874] (0.5%) |
| `int64` | 524288 | 0.0050 [0.0046, 0.0056] (4.0%) | 0.9558 [0.9462, 0.9662] (0.4%) |
| `uint64` | 524288 | 0.0048 [0.0046, 0.0068] (4.2%) | 0.9760 [0.9670, 0.9806] (0.3%) |

## Equal-cardinality transfers

| Dtype | Elements | Bytes | Upload ms | Upload MiB/s | Download ms | Download MiB/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `float32` | 65536 | 262144 | 1.3986 [1.2390, 1.7336] (10.2%) | 178.75 | 0.5972 [0.4638, 0.7994] (9.3%) | 418.62 |
| `int8` | 65536 | 65536 | 1.2166 [1.1426, 2.0108] (5.8%) | 51.37 | 0.4954 [0.4566, 0.5986] (0.7%) | 126.16 |
| `uint8` | 65536 | 65536 | 1.2630 [1.1114, 1.7478] (8.3%) | 49.49 | 0.4862 [0.4712, 0.5138] (1.9%) | 128.55 |
| `int16` | 65536 | 131072 | 1.2244 [0.9834, 1.6704] (2.7%) | 102.09 | 0.5084 [0.4788, 0.5126] (0.8%) | 245.87 |
| `uint16` | 65536 | 131072 | 1.3388 [1.0314, 1.5792] (7.4%) | 93.37 | 0.5078 [0.4922, 0.5548] (3.1%) | 246.16 |
| `int32` | 65536 | 262144 | 1.1824 [0.9872, 1.6298] (9.1%) | 211.43 | 0.5114 [0.5050, 0.5868] (1.3%) | 488.85 |
| `uint32` | 65536 | 262144 | 1.1728 [1.0918, 1.2734] (5.4%) | 213.17 | 0.5028 [0.4888, 0.5636] (2.2%) | 497.22 |
| `int64` | 65536 | 524288 | 1.1782 [1.1222, 1.2612] (1.7%) | 424.38 | 0.5206 [0.4972, 0.5630] (2.9%) | 960.43 |
| `uint64` | 65536 | 524288 | 1.2050 [1.1802, 2.0452] (2.1%) | 414.94 | 0.5174 [0.4950, 0.5652] (1.4%) | 966.37 |

## Equal-byte transfers

| Dtype | Elements | Bytes | Upload ms | Upload MiB/s | Download ms | Download MiB/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `float32` | 65536 | 262144 | 1.4596 [1.1260, 1.6088] (10.2%) | 171.28 | 0.4682 [0.4612, 0.4740] (0.4%) | 533.96 |
| `int8` | 262144 | 262144 | 2.3496 [1.9034, 2.5032] (5.0%) | 106.40 | 1.4794 [1.4600, 1.5016] (0.5%) | 168.99 |
| `uint8` | 262144 | 262144 | 2.0756 [1.9256, 2.5782] (7.2%) | 120.45 | 1.4992 [1.4608, 1.5256] (1.7%) | 166.76 |
| `int16` | 131072 | 262144 | 1.5574 [1.4004, 1.6720] (6.7%) | 160.52 | 0.8248 [0.7960, 0.8520] (1.1%) | 303.10 |
| `uint16` | 131072 | 262144 | 1.4482 [1.3966, 1.6034] (2.7%) | 172.63 | 0.8304 [0.8134, 0.8878] (1.2%) | 301.06 |
| `int32` | 65536 | 262144 | 1.4046 [1.1344, 1.6050] (14.3%) | 177.99 | 0.5026 [0.4748, 0.5158] (1.0%) | 497.41 |
| `uint32` | 65536 | 262144 | 1.1624 [1.1586, 1.5232] (0.3%) | 215.07 | 0.4948 [0.4722, 0.5040] (0.7%) | 505.25 |
| `int64` | 32768 | 262144 | 1.3582 [1.0214, 1.5056] (10.9%) | 184.07 | 0.3428 [0.3196, 0.3812] (4.1%) | 729.29 |
| `uint64` | 32768 | 262144 | 1.0040 [0.8956, 1.1046] (1.0%) | 249.00 | 0.3400 [0.3240, 0.3640] (2.0%) | 735.29 |

## Float32 compute grids

No upload or download occurs in GPU cold/hot rows. CPU and GPU compare the
same logical cardinality; matmul `size` is the side of two square matrices.

| Family | Size | CPU hot ms | GPU cold ms | GPU hot ms | Resident speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| `elementwise` | 1024 | 0.0800 [0.0791, 0.0821] (1.0%) | 0.8490 [0.8220, 2.1680] (2.9%) | 0.6347 [0.4951, 0.6866] (8.1%) | 0.13× |
| `elementwise` | 65536 | 4.1054 [4.0510, 4.1500] (0.5%) | 0.8910 [0.8570, 1.1640] (3.8%) | 0.7481 [0.5566, 0.7837] (4.3%) | 5.49× |
| `elementwise` | 1048576 | 65.3570 [64.8260, 65.7963] (0.6%) | 1.2940 [1.1690, 1.6600] (3.4%) | 0.8873 [0.7423, 1.6833] (1.9%) | 73.66× |
| `reduction` | 1024 | 0.0583 [0.0550, 0.0617] (2.4%) | 1.1530 [1.0040, 1.9040] (0.4%) | 0.6058 [0.5314, 1.4759] (5.4%) | 0.10× |
| `reduction` | 65536 | 2.2794 [2.2464, 2.5838] (0.5%) | 17.0740 [16.7090, 27.2900] (1.3%) | 16.3411 [16.2910, 16.5292] (0.3%) | 0.14× |
| `reduction` | 1048576 | 36.2383 [35.9100, 41.1107] (0.7%) | 263.8250 [263.3770, 264.3070] (0.1%) | 263.7983 [263.2267, 264.3240] (0.2%) | 0.14× |
| `matmul` | 32 | 2.9629 [2.9517, 3.0672] (0.4%) | 1.3450 [1.1470, 39.9930] (6.7%) | 0.6877 [0.5829, 0.8649] (10.2%) | 4.31× |
| `matmul` | 128 | 189.3043 [188.0693, 196.1210] (0.7%) | 1.2470 [1.1830, 1.6130] (3.6%) | 0.5960 [0.5640, 0.9110] (2.8%) | 317.62× |
| `matmul` | 512 | 12278.9690 [12139.8450, 12963.9300] (0.4%) | 3.5440 [2.1110, 3.5920] (1.2%) | 2.9350 [1.5360, 2.9540] (0.3%) | 4183.64× |

## Five-operation resident chain

The exact public chain is `add -> multiply -> matmul -> sum -> add`. Each GPU
cold/hot iteration records five compute passes and zero intermediate readbacks.
End-to-end adds two input uploads and the final scalar download to one hot chain.

| Size | CPU hot ms | Upload ms | GPU cold ms | GPU hot ms | Download ms | Resident speedup | End-to-end speedup |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 32 | 3.3126 [3.2864, 3.4171] (0.8%) | 2.8530 [2.2840, 3.5020] (9.5%) | 5.0260 [4.5460, 5.6490] (9.3%) | 2.9139 [2.7239, 3.9890] (3.6%) | 0.1720 [0.1520, 0.1880] (4.7%) | 1.14× | 0.56× |
| 128 | 195.7313 [192.9250, 200.1447] (0.9%) | 3.0980 [2.8280, 3.6090] (8.6%) | 13.4480 [10.9540, 24.6060] (11.9%) | 9.8827 [9.2720, 10.6630] (4.0%) | 0.1960 [0.1680, 0.5640] (14.3%) | 19.81× | 14.85× |
| 512 | 12600.9260 [12406.9460, 12854.1470] (0.9%) | 5.2640 [4.5940, 7.6100] (4.7%) | 127.9880 [121.6280, 132.0590] (0.7%) | 114.2130 [113.8510, 116.5790] (0.1%) | 0.2820 [0.2030, 0.2980] (5.0%) | 110.33× | 105.22× |

## Observed recommendation

- Elementwise resident crossover: 65536 elements.
- Global-sum resident crossover: none on measured grid elements.
- Square-matmul resident crossover: side 32.
- Five-operation chain resident crossover: side 32.
- Integer rows measure storage and exact round trips only; Tensor 0.1.0 does
  not claim integer GPU compute acceleration.
- Transfer-inclusive decisions must use the end-to-end column, not the resident
  speedup alone. Reuse GPU-resident inputs across several operations whenever
  upload and download would otherwise dominate.

**Release gate: passed on this machine.** The GPU beats the CPU on 3/3 representative resident-chain sizes; command counters show no hidden upload/download inside the chain.

## Peak process memory

`/usr/bin/time -l` peak resident size includes runtime and driver allocations.

| Group | Median bytes | Range bytes |
| --- | ---: | ---: |
| `types` | 84148224 | [84082688, 84164608] |
| `elementwise` | 94928896 | [94863360, 94978048] |
| `reduction` | 85868544 | [85835776, 85999616] |
| `matmul` | 82231296 | [82182144, 82427904] |
| `chain` | 85721088 | [85671936, 85786624] |

These results are local macOS ARM64 evidence for the exact commits above.
They do not predict another CPU architecture, GPU, driver or backend.
