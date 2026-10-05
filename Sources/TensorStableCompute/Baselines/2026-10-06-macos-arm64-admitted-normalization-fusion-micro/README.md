# Admitted add-sqrt normalization fusion: micro

Tensor baseline 7d91f411; one exact compiler; native Release macOS arm64 / Metal. Only scalar addition followed by square root is fused. Reduction order, public API, providers and CPU remain unchanged. Run `python3 Verify.py` to recompute the raw paired and A/A results.

| Case | Before (ms) | After (ms) | Paired delta | Verdict |
|---|---:|---:|---:|---|
| strided/63 | 51.668999 | 47.002000 | -9.084% | signal_decrease |
| vector/1 | 49.575500 | 44.967999 | -9.501% | signal_decrease |
| vector/257 | 179.333500 | 175.717000 | -1.828% | indeterminate |
| vector/4096 | 127.881010 | 125.504995 | -0.556% | indeterminate |
| vector/65536 | 1050.714050 | 1050.802500 | 0.007% | indeterminate |
| vector/7 | 50.586998 | 45.278000 | -10.385% | signal_decrease |

Admission is unchanged: absolute paired median at least 5%, above 3 paired MAD, direction consistent in 14/16 pairs, valid A/A controls. Indeterminate does not establish neutrality. Cold and process RSS are separate from hot wall time; RSS is not physical GPU memory. Seven forward passes become six per normalization, avoiding one output lease/fence/submission. Two Transformer normalizations save six forward passes over three measured steps; scalar-add backward already needed no pass. All 108800 model observations use fixed epsilon 1e-4 and tolerance 2e-5.

Six targeted proofs passed Debug/Release; the full corpus passed 457 tests in 108 sources, with exact Transformer lease counts reduced by two and memory bounds unchanged. Six target consumers compile/link (MSL, SPIR-V, DXIL); only macOS arm64 runtime/performance is claimed. The historical constant-1000 GPU centering bias is preserved exactly and documented by Legacy-Normalization-Bias.json, rather than hidden by a relaxed tolerance. Prototype text files preserve the tested implementation; no version or release is introduced.
