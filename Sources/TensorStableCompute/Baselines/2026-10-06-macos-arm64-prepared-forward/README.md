# Prepared public forward: first closed family

Recorded Release campaign on Apple M3 Pro / Metal, macOS ARM64. One binary uses
public Sequential.forward with or without its prepared plan. Both arms prepare
and warm identical pipelines; eager clears its plan before warmup. The hot
comparison does not establish a startup gain. Every process checks all output
values against CPU eager after timing and verifies input preservation; its log
records the successful checked count. Five compute passes remain per forward.

| Case | Iterations | Eager median ms | Prepared median ms | Paired delta | Verdict |
|---|---:|---:|---:|---:|---|
| 0 | 512 | 92.364500 | 55.076999 | -40.147% | gain |
| 1 | 256 | 45.525500 | 30.442000 | -33.423% | gain |
| 2 | 128 | 21.935000 | 17.637999 | -19.580% | gain |

Each case has 16 A/B pairs and 8 A/A pairs per arm, balanced order. Admission
requires at least 5%, above 3 paired MAD, 14/16 favorable pairs, and valid A/A
controls. No sample was discarded. Case 3 separately measures optional Profile
overhead on a prepared small model; it remains indeterminate. Preparation,
including first pipeline compilation, is observed separately around 1.09 ms.
256 processes check 41,472 output scalars. This does not qualify six model
families, a prepared training step, float16, or runtime performance on other
architectures. Six consumers compile/link; only host behavior is exercised.

Run `python3 Verify.py` to check checksums and reconstruct paired results from
raw logs/CSV/JSON, plus source and qualification consistency. The source is
byte-identical to canonical `TensorStableCompute/PreparedForward.sx`; the original
consumer-local measurement path is preserved only as provenance. Product modules
and the original qualification helper are snapshotted. The compiler prerequisite
is package-private nominal atom resolution, with no backend or shader change.

To collect a new series, first build and qualify the canonical source with one
compiler. Run `Run.py --binary <release-binary> --compiler <same-compiler>
--protocol <Protocol.md> --out <new-directory>` from the workspace root or Spec
Worktree group. Keep builds/tests separate from measurements. New collection
produces its own source hashes and summary; qualifying and sealing its exact
candidate remain separate requirements.
