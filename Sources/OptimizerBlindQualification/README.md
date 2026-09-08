# Blind optimizer qualification

This directory owns the sealed external corpus used by Silex optimizer Part 09.
The corpus is intentionally made only of package and application sources that
predate the qualification campaign. `Manifest.json` fixes their revisions,
hashes, package closure, workloads, semantic oracles, cost dimensions, target
matrix and thresholds before the candidate is observed.

## Local integrity audit

Run from the root containing `Silex`, `Silex-Benchmarks` and `Packages`:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Qualification.py \
  verify --workspace . --silex Silex/Toolchain/zig-out/bin/silex
```

The audit requires every closure repository at its exact sealed HEAD. The owner
repository may be a descendant of its sealed source revision because the
manifest and runner necessarily live in a later commit; every selected source
must still match its sealed hash. The audit also rejects any resolved dependency
that is not a `workspace-link` below that root. Prepare the workspace only with
explicit links such as:

```sh
Silex/Toolchain/zig-out/bin/silex link Packages/STD --workspace .
```

Never use a global `silex link` for this campaign.

The statistical mutation checks are independent of the toolchain:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Qualification.py self-test
```

## Evidence contract

Each native target produces one schema-1 report tied to the SHA-256 of the
sealed manifest. Package-owned and boundary test cases execute through their
test harness, while every executable matrix case must execute in Debug and
Release on the reported native architecture. The macOS ARM64 and macOS X64
profiles also carry all raw paired measurements for execution, startup, cold
and warm compilation, peak RSS and binary size.

Timing and RSS use 21 alternating candidate/reference pairs after two warmups.
The gate recomputes the exact one-sided nonparametric median interval used by
Silex Part 07 and rejects excessive dispersion, regressions and inconclusive
results. Execution must be at parity or better; the other costs use the sealed
125% non-regression ceiling. Binary size is deterministic and uses one pair.
Cross-compilation and emulation are never accepted as physical performance
evidence.

After downloading all six native reports, run:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Qualification.py \
  gate Results/OptimizerBlindQualification/*/report.json
```

All child processes launched by the qualification tooling are bounded in their
own process group. A timeout terminates the full group so a stopped campaign
cannot leave a `silex run` executable consuming CPU in the background.
