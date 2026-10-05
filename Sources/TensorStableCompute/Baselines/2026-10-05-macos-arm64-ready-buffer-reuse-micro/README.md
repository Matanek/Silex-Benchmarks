# Ready-buffer reuse: micro

This recorded Release campaign uses one exact compiler for eager Tensor e7394c81
and the ready-buffer candidate. Sources and protocol were frozen before 16 paired
runs and 8 A/A pairs per binary. Run python3 Verify.py to recompute the recorded
medians, MAD, controls, resource counters and RSS from the raw samples.

All 12 resident microcases and 8 GFX controls are indeterminate. The largest replace case has a paired median -7.542%, but only 13/16 favorable pairs and therefore fails the fixed admission rule. All cold cases are indeterminate. Native creations may decrease without demonstrating a timing benefit.

The private cache is bounded to 32 exact size/dtype entries and 1 MiB of requested buffer sizes per device, and clears when the last Tensor storage disappears. The portable GPU provider and shaders are unchanged. Measurements are macOS arm64 / Apple M3 Pro / Metal only. See Configuration.json for identities and platform data, Source.sx.txt for the common harness, Protocol.md for the frozen rules, Binary-Qualification.json and Qualification-*.log for Debug/Release gates, and Candidate-*.txt for the exact changed module sources. Tensor-Qualification.json records 451 tests over 107 sources; unchanged proofs are reused only with matching compiler/module/source fingerprints.

To collect a NEW campaign, build eager and candidate binaries with the SAME compiler from their source snapshots, qualify both with --verify, and produce the eight-entry manifest in the format of Binary-Qualification.json. From the workspace root, use python3 Silex-Benchmarks/Sources/TensorStableCompute/Baselines/2026-10-05-macos-arm64-ready-buffer-reuse-micro/Run.py micro --before-binary /absolute/eager --after-binary /absolute/candidate --compiler /absolute/silex --baseline-tensor-commit e7394c81b72ae86058bca7e9e5f1fc58674651ef --qualification /absolute/qualification.json --protocol /absolute/Protocol.md --out /absolute/new-campaign. The output directory must not already exist. This does not rebuild sources or overwrite this recorded campaign. Never time concurrently with a build or test.
