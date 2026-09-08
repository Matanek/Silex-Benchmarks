# Tensor memory and compute

This campaign measures the public Tensor 0.1.0 surface without exposing
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
bit-exact transfer cost; Tensor 0.1.0 makes no integer GPU compute claim.
