# Tensor memory and compute

This campaign measures the public Tensor surface without exposing
benchmark instrumentation in the package API. It separates:

- CPU construction from an existing typed array and typed extraction;
- upload and download for all nine dtypes, first at 65,536 elements and then
  at an equal 262,144-byte payload;
- CPU hot execution, first GPU pipeline creation plus dispatch, and hot GPU
  dispatch for elementwise addition, global sum, and square matmul;
- a resident `float32` chain of exactly five public operations:
  `add -> multiply -> matmul -> sum -> add`;
- the chain's two input uploads, first execution, hot execution, and final
  scalar download.

`Neural.sx` extends that protocol to complete MLP, CNN and RNN training slices
over three batch sizes. It measures construction, cold and hot forward and
backward execution, SGD and Adam updates, scalar loss observation, a fully
resident training step, and an end-to-end step with explicit ingress and
egress. CPU and GPU use identical public models, inputs and targets.

Every timed GPU region waits for completion at both boundaries. Command
statistics are checked after each region, so asynchronous submission time is
never compared with completed CPU work and a resident row cannot hide an
upload or download. Package-private Tensor tests independently guard buffer,
staging, fence, and pipeline-creation counts; timings never appear in unit-test
assertions.

## Run the diagnostic

Run Silex commands from the Tensor Spec worktree root with an explicit source:

```sh
Silex/Toolchain/zig-out/bin/silex compile \
  Silex-Benchmarks/Sources/TensorStableCompute/Main.sx \
  --debug --nocache --output /private/tmp/tensor-debug
/private/tmp/tensor-debug --verify
```

The verifier checks CPU/GPU values, five resident compute passes, no
intermediate download, and one explicit final download.

The neural verifier uses the same rules:

```sh
Silex/Toolchain/zig-out/bin/silex compile \
  Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx \
  --debug --nocache --output /private/tmp/tensor-neural-debug
/private/tmp/tensor-neural-debug --verify
```

## Run the Release campaign

Commit the harness first so metadata identifies an exact benchmark revision,
then run from the Spec worktree root:

```sh
Silex-Benchmarks/Sources/TensorStableCompute/RunCampaign.sh \
  Silex-Benchmarks/Sources/TensorStableCompute/Baselines/2026-09-08-macos-arm64-part07
```

The runner refuses a dirty benchmark repository. It performs one Debug
diagnostic build/run, one Release build, and seven independent Release
processes for each resumable group: dtypes, elementwise, reduction, matmul,
and resident chain. Each Release process reruns the functional verifier before
measurement.

The result directory contains build logs, raw stdout, `/usr/bin/time -l`
output, exact repository and machine metadata, `measurements.csv`, and a
generated `Summary.md`. Rerun the whole campaign when source, toolchain,
package commits, machine, OS, or driver changes; do not merge samples from
different configurations.

Release measurements from macOS ARM64 are evidence for that machine and those
exact commits only. Integer results characterize construction, extraction and
bit-exact transfer cost; this campaign does not measure integer GPU compute.

Run the neural campaign separately after committing its harness:

```sh
Silex-Benchmarks/Sources/TensorStableCompute/RunNeuralCampaign.sh \
  Silex-Benchmarks/Sources/TensorStableCompute/Baselines/2026-09-09-macos-arm64-part12-neural
```

It starts five independent Release processes for each model family. The raw
logs retain command counters, `/usr/bin/time -l` retains process RSS, and the
generated summary reports dispersion and CPU/GPU ratios without generalizing
beyond the recorded machine, driver and commits. Stable live graph and buffer
counts are enforced by package-private Tensor tests rather than inferred from
process RSS.

## Eager resource attribution

`EagerResources.sx` separates result lifetime from GFX buffer creation/release.
It compares 64 independent additions with replacement or retention of their
results, then checks a chain of 64 dependent additions. All three cases have
64 logical results, passes, submissions and fences. The eager reference makes
64 native buffer allocations; a ready-buffer cache can reuse reservations, with
zero resident transfers. Exact analytical outputs are checked after timing.
Retention is bounded to 64 results (16 MiB at the largest measured size), and
all buffers are released after each verifier case. A separate GFX control
compares creating/releasing 4,096 buffers with accessing one existing buffer;
these calls are outside Tensor.Profile and do not measure physical Metal VRAM
allocation or demonstrate a Tensor pool speedup.

From the workspace root, compile this source with an explicit path and output:

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global" silex compile \
  Silex-Benchmarks/Sources/TensorStableCompute/EagerResources.sx \
  --release --output /private/tmp/tensor-eager-resources
/private/tmp/tensor-eager-resources --verify
/private/tmp/tensor-eager-resources --measure
/private/tmp/tensor-eager-resources --measure --reverse
```

`--verify` enables Metal validation and checks sizes 1, 256 and 4,096.
`--measure` reports synchronized wall time at sizes 1, 256, 4,096 and 65,536;
`--reverse` reverses the independent and buffer-control pairs. The separate
`cold_ms` includes input upload, pipeline creation and the four synchronized
warmup operations. Warmups are outside the main hot timing, values and counters
are always checked, and the dependent case
is a separate counterexample. Freeze sources and binaries before collecting
balanced repetitions and same-binary controls; retain all raw samples.
No timing threshold is enforced by the correctness verifier.

## Resident steps across six model families

`ResidentSteps.sx` compares MLP, CNN, SimpleRNN, GRU, LSTM and Transformer
training using seeds 481/482, asymmetric inputs and AdamW at 0.01 with an
explicit epsilon of 1e-4. That setting limits amplification of float32
roundoff in nearly zero attention key-bias gradients when comparing complete
independently evolved CPU/Metal states. Each family
warms up for two steps, then times three complete resident steps including
`zero_grad`, forward, cross-entropy, backward, update and final GPU completion.
Full outputs, parameters, gradients, both optimizer moments and step counts
are observed after timing. `--verify` compares every observed CPU/Metal value
with an absolute/relative tolerance of 2e-5 and checks complete resource release.

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global" silex compile \
  Silex-Benchmarks/Sources/TensorStableCompute/ResidentSteps.sx \
  --release --output /private/tmp/tensor-resident-steps
/private/tmp/tensor-resident-steps --verify
/private/tmp/tensor-resident-steps --measure
/private/tmp/tensor-resident-steps --measure --reverse
```

`--cpu` selects CPU measurement. GPU rows report compute passes, submissions,
actual native allocations, releases and peak requested bytes in use by values.
`cold_ms` separately includes construction, upload, pipeline creation and the
two warmup steps through GPU completion. Noncontiguous views can
submit GPU-to-GPU copies in addition to compute passes; every resident region
requires zero CPU/GPU transfers and zero pipeline compilations. Scalar rows
retain the complete final observations for comparisons between binaries.
Freeze sources and binaries before running balanced process pairs and
same-binary controls. A compiler comparison records both compiler identities;
equal Tensor sources alone do not establish an equal toolchain.

## Ready buffer reuse on the corrected eager reference

The 5 October 2026 Release comparison on Apple M3 Pro / Metal uses one exact
compiler, 16 before/after pairs and eight A/A pairs per binary. Eager Tensor
allocates every result; the candidate reuses ready storage in a private cache
bounded to 32 exact size/dtype entries and 1 MiB per device. No command grouping
or shader change is included. All 451 Tensor tests and the eight Debug/Release
benchmark binaries pass; the six-family campaign retains 108,800 complete
scalar observations, with unchanged epsilon 1e-4 and tolerance 2e-5.

| Family | Eager median, three steps | Reuse median | Median paired change | Verdict |
| --- | ---: | ---: | ---: | --- |
| MLP | 10.000 ms | 10.184 ms | +3.61% | Indeterminate |
| CNN | 10.492 ms | 10.569 ms | +0.76% | Indeterminate |
| SimpleRNN | 14.468 ms | 14.129 ms | -5.10% | Indeterminate |
| GRU | 28.911 ms | 28.030 ms | -2.87% | Indeterminate |
| LSTM | 29.550 ms | 29.724 ms | -0.01% | Indeterminate |
| Transformer | 40.260 ms | 37.853 ms | -5.89% | Admitted decrease |

Transformer has paired MAD 1.20 percentage points, 14/16 favorable pairs,
and valid A/A controls. The other families, all cold costs and all twelve
resident microcases remain indeterminate under the frozen 5% / 3 MAD / 14 of
16 rule. Median Transformer native creations decrease from 1365 to 643 while
passes/submissions stay identical. Fewer allocations alone do not prove speed.
Median process RSS for the six-family workload rises from 81,510,400 to
83,869,696 bytes; this includes allocator/driver costs and is not physical VRAM.
No cross-platform performance claim is made.

The [micro campaign](Baselines/2026-10-05-macos-arm64-ready-buffer-reuse-micro/README.md)
and [model campaign](Baselines/2026-10-05-macos-arm64-ready-buffer-reuse-models/README.md)
retain raw samples, sources, protocol, configurations, controls and standalone
verification/measurement recipes. The private pool releases every cached buffer
at the last Tensor storage even when a public Profile remains alive.

## Rejected five-pass softmax grouping

The October 5 experiment preserved all five existing Float32 shaders/passes,
sharing one command buffer and completion token. Public values/gradients, views,
aliases, profiles and resource release were correct. The first prototype passed
456 tests over 108 sources and Debug/Release harness checks; its hot results
were indeterminate. A reduced ownership probe found five native waits on one
shared fence; terminal completion reduced these to one.

The terminal experiment isolated each size in its own process, kept the same
compiler and admission thresholds, warmed up 16 calls, and used 512 hot calls
for the small vectors/view and 64 for the two large vectors. The strided case
regressed by a paired median **25.627%**, MAD 2.728 percentage points, all 16
pairs slower, with valid A/A controls. No case had an admitted decrease. The
vector-7 after A/A was invalid and remains indeterminate. The prototype was
**removed completely**; Tensor remains at its ready-buffer baseline. No new
Tensor API or optimized behavior is shipped from this experiment.

[First microcases](Baselines/2026-10-05-macos-arm64-rejected-softmax-grouping-first-micro/README.md),
[unchanged model states](Baselines/2026-10-05-macos-arm64-rejected-softmax-grouping-first-models/README.md),
and [terminal isolated cases](Baselines/2026-10-05-macos-arm64-rejected-softmax-grouping-terminal-micro/README.md)
preserve 512 processes, raw measurements, fixed rules, exact prototype snapshots
and standalone `Verify.py` tools. The model campaign checks 108,800 full scalar
observations; all six families are indeterminate and their submission counts
are unchanged. Process RSS and requested buffer peaks are reported separately
from physical GPU memory. This rejects this particular region/representation;
it does not establish that other command regions or kernel fusion cannot help.

`SoftmaxGrouping.sx` remains a public research harness that verifies complete
results on the current eager implementation. Build from the workspace root:

```sh
silex compile Silex-Benchmarks/Sources/TensorStableCompute/SoftmaxGrouping.sx --release --output /private/tmp/tensor-softmax-grouping
/private/tmp/tensor-softmax-grouping --verify
/private/tmp/tensor-softmax-grouping --measure --case-5
```

`--case-0` through `--case-5` select vectors 1/7/257/4096/65536 and the strided
view. Collection must use distinct qualified before/after binaries, one compiler,
16 paired runs and 8 A/A pairs per arm; never compare a new workload to the old
recorded timings or run it concurrently with builds/tests.


## Qualified add-sqrt normalization fusion

Run `NormalizationFusion.sx` with `--verify` for all six complete value checks
or `--measure --case-0` through `--case-5` for isolated workloads. The workload
normalizes float32 vectors of 1/7/257/4096/65536 values and a transpose/narrow
view, with epsilon 0.25, 16 warmups and 512 small/view or 64 large calls.
Timing ends after explicit device completion; all output values and preserved
inputs are checked afterward. Profile counters verify six forward passes
instead of seven, with one fewer temporary lease/submission/fence.

The October 6, 2026 native Release Apple M3 Pro / Metal comparison uses Tensor
7d91f411 as baseline and the same exact compiler on both arms. Sixteen pairs,
eight A/A controls per binary and the unchanged 5% / 3 MAD / 14-of-16 rule
admit paired gains of 9.50% (one value), 10.38% (seven) and 9.08% (strided).
All 16 pairs favor the candidate in each admitted case. Other sizes, cold costs
and all six model families remain indeterminate, with no admitted regression;
indeterminate does not establish neutrality. All 108800 model observations
remain qualified at fixed tolerance 2e-5 and AdamW epsilon 1e-4. Transformer
avoids six forward passes over three steps, without an admitted timing gain.

Raw logs, time/RSS, CSV/JSON, frozen protocol, sources, five exact candidate
module files, eight Debug/Release qualifications, the 457-test corpus summary,
six-target shader/link qualifications and verifiers are in
[the micro campaign](Baselines/2026-10-06-macos-arm64-admitted-normalization-fusion-micro/README.md)
and [the model campaign](Baselines/2026-10-06-macos-arm64-admitted-normalization-fusion-models/README.md).
Both standalone `Verify.py` programs recompute the evidence. RSS is process
memory, not physical VRAM. Six targets compile/link; runtime and gain claims
are limited to macOS arm64 / Metal. The pre-existing constant-1000 centering
bias is retained as a separate exact eager GPU witness, without relaxed tolerances.


## Prepared public forward

`PreparedForward.sx` compares the ordinary public forward of one closed
Sequential/Dense/Activation family with its explicitly prepared plan. The three
hot workloads retain five compute passes and admit paired decreases of 40.15%,
33.42% and 19.58% on Apple M3 Pro / Metal. All 16 pairs favor preparation in each
case and A/A controls pass the fixed admission rule. Cold preparation is recorded
separately; optional Profile overhead remains indeterminate.

The [sealed campaign](Baselines/2026-10-06-macos-arm64-prepared-forward/README.md)
retains 256 raw process logs, 41,472 checked output scalars, source snapshots,
464 passing tests over 110 sources, and six compile/link targets. Its standalone
`Verify.py` reconstructs the results without GPU execution. These measurements
do not qualify prepared training, six full model families, float16 or runtime
gains on another platform.

Build from the workspace root with the compiler containing package-private atom
resolution, then exercise both modes:

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global" silex compile \
  Silex-Benchmarks/Sources/TensorStableCompute/PreparedForward.sx \
  --release --output /private/tmp/tensor-prepared-forward
/private/tmp/tensor-prepared-forward --case-0
/private/tmp/tensor-prepared-forward --planned --case-0
```

Use the sealed campaign's `Run.py` for a fresh balanced A/B and A/A series,
after qualifying the new exact sources and compiler. Keep measurement separate
from concurrent builds/tests; historical timings belong to their recorded pins.
