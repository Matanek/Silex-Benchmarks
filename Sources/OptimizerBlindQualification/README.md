# Blind optimizer qualification

This directory owns the sealed external corpus used by Silex optimizer Part 09.
The corpus is intentionally made only of package and application sources that
predate the qualification campaign. `Manifest.json` fixes their revisions,
hashes, package closure, workloads, semantic oracles, cost dimensions, target
matrix and thresholds before the candidate is observed.

`Candidate.json` is the append-only correction descriptor created after sealed
sentinels rejected candidate revisions. It binds the unchanged manifest hash,
the rejected SHA, every corrected SHA in order and each autonomous Silex
regression added before the campaign is resumed. It does not alter a source,
workload, target, metric or threshold from the sealed corpus.

`FixtureCorrection.json` records the one accepted harness-only correction. The
original Regex fixture spent the qualification timeout constructing two dynamic
million-element lists before its stopwatch or Regex search began. The corrected
fixture constructs the same one-million `a` scalars plus the same `Z` suffix
geometrically. The descriptor binds both source hashes, the unchanged workload
and oracle, and the four remote diagnostic runs that established attribution.
The gate requires its hash in every native report.

`BoundaryScope.json` records the explicit SDL3 trust boundary selected after a
GitHub-hosted Windows X64 runner could not create a D3D12 GPU pipeline, the
Linux X64 profile was confirmed to use Xvfb with Mesa Lavapipe rather than a
physical GPU, and no physical-GPU macOS X64 runner was available. macOS X64,
Linux and Windows ARM64/X64 must still compile Boids2D, FallingBodies2D and
Scene3D in both Debug and Release and record each native binary's hash and
size. Their GPU execution is not required on those profiles. Every other
native case still executes on all six targets, including the CPU performance
workloads on physical macOS ARM64 and X64. The three graphical sentinels execute
only on the physical-GPU macOS ARM64 profile; SDL3 owns their cross-platform GPU
execution contract. The gate binds this exact scope descriptor by SHA-256 and
rejects any broader compile-only set.

## Local integrity audit

Run from the root containing `Silex`, `Silex-Benchmarks` and `Packages`:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Qualification.py \
  verify --workspace . --silex Silex/Toolchain/zig-out/bin/silex
```

The audit requires every closure repository at its exact sealed HEAD, except
that Silex must be at the exact corrected SHA bound by `Candidate.json`. The
corrected SHA must descend from the rejected sealed candidate and contain every
hashed regression in the append-only correction chain. The owner repository
may be a descendant of its
sealed source revision because the manifest and runner necessarily live in a
later commit; every selected source must still match its sealed hash. The audit
also rejects any resolved dependency that is not a `workspace-link` below that
root. Prepare the workspace only with explicit links such as:

```sh
Silex/Toolchain/zig-out/bin/silex link Packages/STD --workspace .
```

Never use a global `silex link` for this campaign.

The statistical mutation checks are independent of the toolchain:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Qualification.py self-test
```

Run a bounded native correctness campaign with an explicit output location:

```sh
python3 Silex-Benchmarks/Sources/OptimizerBlindQualification/Campaign.py \
  --workspace . --silex Silex/Toolchain/zig-out/bin/silex \
  --runner local-macos-arm64 \
  --output /tmp/silex-part09/report.json
```

`--only CASE` and `--mode debug|release` are repeatable and safely resume a
partial report. The manual
`optimizer-blind-qualification.yml` workflow materializes the same closure and
is the authoritative source for the six named native runner profiles. Only its
macOS ARM64/X64 jobs collect physical CPU performance evidence; graphical
execution and measurements are required only on macOS ARM64.

## Evidence contract

Each native target produces one schema-1 report tied to the SHA-256 of the
sealed manifest, corrected candidate, fixture correction and boundary scope.
Package-owned and boundary test cases execute through their test harness, while
every executable matrix case must execute in Debug and Release on the reported
native architecture except the graphical cases on hosted profiles without a
physical GPU explicitly listed above. The macOS ARM64 and macOS X64 profiles
also carry all raw paired measurements for every non-scoped performance case;
macOS ARM64 additionally measures the graphical cases. The dimensions are
execution, startup, cold and warm compilation, peak RSS and binary size.

Timing and RSS use 21 alternating candidate/reference pairs after two warmups.
Startup is the wall-clock interval from process spawn until a pinned injected
dyld constructor exits before application `main`; its source hash is carried by
every startup measurement. This keeps the loader measurement available on
current macOS runners where `DYLD_PRINT_STATISTICS` no longer emits a record and
does not execute the graphical workload during startup sampling.
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

The `regex-diagnostic` target of `optimizer-blind-qualification.yml` is
explicitly non-qualifying. It first checks the sealed Regex source hash, then
derives one temporary `main` per unchanged test body in a valid transient module
directory, which it removes after measurement. Debug and Release compilation
and execution are timed independently with short process-group bounds; binaries
and compiler caches remain below `.silex`. This attributes a qualification
timeout without editing or replacing the sealed workload. `--only` can restrict
a run to one diagnostic entry, including `input-construction`, which isolates
the million-scalar fixture before any Regex search begins.
