# Rejected softmax grouping: first-micro

This is a preserved experiment, not a shipped Tensor optimization. The baseline is Tensor 7d91f411 and both arms use one exact compiler on macOS arm64 / Metal. Five dependent compute passes can share a command buffer correctly; this experiment did not establish an admissible benefit. The terminal variant has an admitted strided regression and was removed completely. Run `python3 Verify.py` to recompute the evidence.

| Case | Before (ms) | After (ms) | Paired delta | Verdict |
|---|---:|---:|---:|---|
| strided/63 | 7.917500 | 6.508000 | -18.284% | indeterminate |
| vector/1 | 7.053000 | 6.069500 | -14.317% | indeterminate |
| vector/257 | 13.511000 | 10.490000 | 7.321% | indeterminate |
| vector/4096 | 83.037000 | 83.401505 | 0.564% | indeterminate |
| vector/65536 | 1258.446500 | 1248.929900 | -0.642% | indeterminate |
| vector/7 | 7.516000 | 6.205500 | -15.036% | indeterminate |

The first experiment has six indeterminate microcases and six indeterminate model families. The terminal experiment isolates each size in a process and increases small-case repetitions; the strided paired regression is +25.627%, MAD 2.728 points, with valid A/A controls. Its vector-7 A/A after is invalid; no sample was discarded. Cold and RSS evidence remains in Summary.json, distinct from physical VRAM. The model campaign preserves all 108800 scalar observations (1700 per process), epsilon 1e-4, tolerance 2e-5.

Prototype-*.txt stores the exact tested private implementation for diagnosis only. The first variant passed 456 tests/108 sources; the terminal variant has targeted Release and eight Debug/Release harness qualifications, and was rejected before broad admission gates. Restored-Tensor.json proves that the unchanged baseline was restored. The fixed admission remains at least 5%, above 3 paired MAD, consistent direction 14/16 and valid A/A controls. No feature, public API, shader, provider, version or release is introduced. Recorded-Run.py.txt preserves collection provenance; Source.sx.txt and Protocol.md pin each workload.
