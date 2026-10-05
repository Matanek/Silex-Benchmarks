# Rejected softmax grouping: first-models

This is a preserved experiment, not a shipped Tensor optimization. The baseline is Tensor 7d91f411 and both arms use one exact compiler on macOS arm64 / Metal. Five dependent compute passes can share a command buffer correctly; this experiment did not establish an admissible benefit. The terminal variant has an admitted strided regression and was removed completely. Run `python3 Verify.py` to recompute the evidence.

| Case | Before (ms) | After (ms) | Paired delta | Verdict |
|---|---:|---:|---:|---|
| cnn | 11.028499 | 11.105500 | -0.138% | indeterminate |
| gru | 28.845500 | 28.450001 | 1.105% | indeterminate |
| lstm | 28.496500 | 27.915499 | 0.762% | indeterminate |
| mlp | 10.304000 | 10.202500 | 1.277% | indeterminate |
| rnn | 14.699500 | 14.592500 | -2.871% | indeterminate |
| transformer | 38.042501 | 38.661000 | 2.192% | indeterminate |

The first experiment has six indeterminate microcases and six indeterminate model families. The terminal experiment isolates each size in a process and increases small-case repetitions; the strided paired regression is +25.627%, MAD 2.728 points, with valid A/A controls. Its vector-7 A/A after is invalid; no sample was discarded. Cold and RSS evidence remains in Summary.json, distinct from physical VRAM. The model campaign preserves all 108800 scalar observations (1700 per process), epsilon 1e-4, tolerance 2e-5.

Prototype-*.txt stores the exact tested private implementation for diagnosis only. The first variant passed 456 tests/108 sources; the terminal variant has targeted Release and eight Debug/Release harness qualifications, and was rejected before broad admission gates. Restored-Tensor.json proves that the unchanged baseline was restored. The fixed admission remains at least 5%, above 3 paired MAD, consistent direction 14/16 and valid A/A controls. No feature, public API, shader, provider, version or release is introduced. Recorded-Run.py.txt preserves collection provenance; Source.sx.txt and Protocol.md pin each workload.
