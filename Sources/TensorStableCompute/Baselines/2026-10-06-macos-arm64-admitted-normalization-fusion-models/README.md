# Admitted add-sqrt normalization fusion: models

Tensor baseline 7d91f411; one exact compiler; native Release macOS arm64 / Metal. Only scalar addition followed by square root is fused. Reduction order, public API, providers and CPU remain unchanged. Run `python3 Verify.py` to recompute the raw paired and A/A results.

| Case | Before (ms) | After (ms) | Paired delta | Verdict |
|---|---:|---:|---:|---|
| cnn | 10.627499 | 10.743500 | -2.359% | indeterminate |
| gru | 28.790499 | 27.772500 | -0.820% | indeterminate |
| lstm | 28.772500 | 28.492500 | -0.722% | indeterminate |
| mlp | 10.031499 | 10.176500 | -5.244% | indeterminate |
| rnn | 13.197999 | 13.528000 | 5.278% | indeterminate |
| transformer | 39.547500 | 39.914000 | 3.570% | indeterminate |

Admission is unchanged: absolute paired median at least 5%, above 3 paired MAD, direction consistent in 14/16 pairs, valid A/A controls. Indeterminate does not establish neutrality. Cold and process RSS are separate from hot wall time; RSS is not physical GPU memory. Seven forward passes become six per normalization, avoiding one output lease/fence/submission. Two Transformer normalizations save six forward passes over three measured steps; scalar-add backward already needed no pass. All 108800 model observations use fixed epsilon 1e-4 and tolerance 2e-5.

Six targeted proofs passed Debug/Release; the full corpus passed 457 tests in 108 sources, with exact Transformer lease counts reduced by two and memory bounds unchanged. Six target consumers compile/link (MSL, SPIR-V, DXIL); only macOS arm64 runtime/performance is claimed. The historical constant-1000 GPU centering bias is preserved exactly and documented by Legacy-Normalization-Bias.json, rather than hidden by a relaxed tolerance. Prototype text files preserve the tested implementation; no version or release is introduced.
