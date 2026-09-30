# Native ARM64: scalar class field transfers

## Result

Apple M3 Pro, macOS 26.6.2 ARM64. Fixed work, Native Release, no rendering.
Four adjacent balanced pairs per workload (A B B A A B B A). Values below
are medians of whole-run means, with the range of those means in parentheses.
A is the validated LSE compiler; B adds the parameter-capture correction and
scalar class field transfers. Physics sources and solver settings are unchanged.

| Workload | A, ms/step | B, ms/step | Change |
|---|---:|---:|---:|
| AquariumFill, 1,024 spheres / 1,800 steps | 8.598 (8.568–8.691) | 8.192 (8.164–8.261) | -4.72% |
| ColumnPeak, 256 boxes / 600 steps | 6.675 (6.666–6.692) | 6.290 (6.277–6.331) | -5.78% |

All four Aquarium pair ratios are below one (0.9505, 0.9536, 0.9498,
0.9549), meeting the predeclared mean ratio < 0.985 rule. The column improves
in every pair and meets the <= 3% regression bound. All recorded physical
observables match exactly, excluding only timing fields.

A separate diagnostic sequence LLVM / original Native / B / B / original
Native / LLVM retains the original compiler baseline and external control:

| Aquarium control | Whole-run ms/step, mean of two runs |
|---|---:|
| Original Native (before LSE) | 8.858 |
| Candidate B | 8.173 |
| LLVM | 2.950 |

The diagnostic cumulative reduction is 7.74%; Native still takes about 2.77
times LLVM's CPU step time. Two control samples do not replace the four-pair
admission campaign. These numbers do not measure render frame time or FPS,
do not establish 120 FPS in active simulation, and do not fix sleeping or the
pre-existing penetration debt. The same physical debt remains visible in the
CSV rather than being hidden by different solver parameters.

## Protocol and provenance

The game was closed before this campaign. An earlier interrupted run while it
was open made the unchanged control about six times slower and was excluded
before completing qualification; its partial log remains in Spec scratch data.
No build, test or other benchmark ran concurrently with the timings here.
Owned child processes used `taskpolicy -a` followed by `taskpolicy -B -p`.
Background OS activity was not disabled. Each process completed with exit 0.
Raw observations, ordering, binary hashes and the predeclared policy accompany
this report. Source and commit identities are in `provenance.json`.

The candidate applications were compiled with the Debug bootstrap, Native
Release and `--nocache` before the implementation was committed. The five
machine-code source file blobs exactly match `bbc8b9f`; later edits only add
release notes and documentation. The LSE baseline bootstrap was also Debug.
The original and LLVM bootstrap build modes were not independently recorded.
The explicit LLVM backend binary is the frozen control from the earlier
major-levers campaign; no backend or source substitution was made here.

`measure.py` and `controls.py` document the original commands from the Spec
Worktree group root and expect the named scratch binaries. They overwrite
scratch result paths if rerun; preserve a completed campaign first.

## Implementation and correctness

Class field loads/stores use GPR or scalar FP residences when assigned, with
stack fallback. Transfers preserve the full 64-bit payload of mixed fields;
packed f32 lanes remain excluded. Stores consume replacement leaves before
publishing the result handle, protecting coalesced input/result registers.
The prerequisite correction `e894c72` accounts for all incoming argument
captures, including unused arguments, in the interference graph.

The exact source implementation had already passed `zig build check test
-Doptimize=Debug` before timing (216 source tests, 28 oracle programs, plus
unit, ownership and ECS coverage). It was preserved as a patch while timing
was blocked, then reapplied byte-for-byte; file blobs were checked against
the tested patch before committing. Reduced tests exercise mixed payloads,
coalesced stores and parameter capture. No semantic suite was weakened.

Scalar class field residences are implemented in the shared ARM64 emitter,
with Release allocation active on macOS/Linux; Windows' current stack lowering
uses the fallback. The prerequisite graph correction also reaches X64 scalar
FP allocation. Execution and performance here are verified only on macOS
ARM64; this is not a six-target qualification. No remote publication or local
baseline integration is part of this campaign.
