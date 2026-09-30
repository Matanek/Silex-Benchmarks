# Native class counters: macOS ARM64 LSE

Measured on Apple M3 Pro, macOS 26.6.2 ARM64, Native Release, `--nocache`.
Compiler baseline `251d4ec827e15e117d945d22532290f8c19ae48c`; candidate
`87133ed79a1c5ab8f8192d1bed2dcac3265036ce`. Physics is unchanged at
`d955a1aec00a36ccdda8d2461801d5cc07a74f15`. The candidate used a Debug bootstrap compiler; the baseline bootstrap mode
was not separately recorded. Both application binaries are Release. Candidate binaries
were built before adding the regression tests and comments; the executable
encoder implementation matches the candidate commit. Their hashes are recorded
in `runs.json`.

## Protocol

Four balanced adjacent pairs per scene, A B B A A B B A. A is the frozen native
baseline; B is the LSE candidate. No other build, test, or benchmark ran during
timing. Each owned child ran at normal priority via `taskpolicy`. The policy
was saved before this qualification, separately from exploratory runs.

The workload and solver settings are unchanged. AquariumFill emits 1,024
bodies and runs 1,800 fixed steps; ColumnPeak runs 256 boxes for 600 steps.
Every recorded physical observable is exactly equal across all eight runs of
each workload. Only timing columns are excluded from equality.

| Workload | Baseline ms/step, median (range) | Candidate ms/step, median (range) | Change |
|---|---:|---:|---:|
| AquariumFill | 8.865 (8.820–8.881) | 8.600 (8.580–8.626) | -2.99% |
| ColumnPeak | 6.854 (6.801–6.940) | 6.814 (6.739–6.899) | -0.59% |

These are CPU physics step times, not rendered FPS. The column change is small;
the aquarium meets the predeclared admission rule. This does not resolve the
remaining Native/LLVM gap, establish 120 FPS, or change sleeping/penetration
behavior. The previous LLVM control remains in `2026-09-30-major-levers`;
there is no new LLVM measurement in this LSE qualification.

## Implementation and verification

On Darwin ARM64, retain uses LDADDAL; drop uses LDAR/CASAL with a zero check
and retry. Acquire/release ordering and saturating decrements are preserved.
The finalization claim and cycle protocol are unchanged. Linux and Windows
ARM64 retain the baseline exclusive loops because their generic CPU profile
does not guarantee LSE. X64 code is unchanged. No gain is claimed elsewhere.

`zig build check -Doptimize=Debug` and `zig build test -Doptimize=Debug` exited
zero. New tests compare instruction words with the local Apple assembler,
check platform selection, and execute balanced root/edge transitions and
zero-count saturation. Existing ownership, cyclic destruction, and native
portability tests also pass. No remote publication or reintegration occurred.

Rebuild from the Spec Worktree group root:

```sh
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig" Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/Physics3D/AquariumFill.sx --release --nocache -o .silex/aquarium-fill
.silex/aquarium-fill
```

Use `ColumnPeak.sx` with the same options for the second workload. Raw CSV and
run ordering are preserved alongside this report. Correctness failures from
rejected earlier experiments are preserved separately in the Spec memory;
none of those patches is part of this candidate.
