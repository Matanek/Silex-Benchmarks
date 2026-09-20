# LLVM cycle traversal regression — 20 September 2026

Pruning externally rooted objects from LLVM cycle trials removes repeated
traversal of the retained application scene. The correction is Silex commit
`81899a6bcfacd271e9b8ed844dc5c26170c2b6af`, against reference
`daf2d75d74dec14f1e7a7f2f79bbcdc8de843e62`. Physics and the benchmark source are
unchanged. This record qualifies the local macOS ARM64 result, not other targets
or the Physics/Box2D parity objective.

## Results and limits

The user's progressive scene reproduced the reported slowdown at 3,000 bodies:
reference cadence observations were 56.20–59.82 FPS. The user closed that window
at 64.6 seconds because it fell below 60 FPS. It is an interrupted diagnostic,
not a completed 90-second timing sample. The corrected diagnostic completed
90 seconds, with 31 cadence observations at 3,000 bodies: median 120.00 FPS,
range 119.54–234.99. It continued near 120 FPS through the settled pile.
The user also reported that the corrected run was much better.

These sequential interactive observations use the real-time accumulator and
are not an equal-state throughput comparison. They establish the reproduced
symptom and observed recovery; they do not establish a statistically measured
2× gain. Both request immediate presentation, retain the panels, and use the
original progressive emission. The 800 FPS historical expectation was not
reproduced. Candidate profiles contain substantial Metal `nextDrawable` wait;
requested immediate presentation does not make these runs free of presentation
limits. Window focus/occlusion was not recorded.

Separate bounded, equal-work comparisons used the unchanged benchmark, three
warm-up runs followed by seven alternating before/after samples per case:

| Case | Reference median FPS (range) | Corrected median FPS (range) | Interpretation |
| --- | --- | --- | --- |
| 120 bodies, 120 measured physics steps | 485.43 (439.75–497.37) | 495.23 (353.96–640.29) | Overlapping, variable; no established gain |
| Render only, 3,000 bodies, 120 measured frames | 261.89 (259.73–267.88) | 496.77 (472.48–551.89) | 1.897× median throughput in this bounded control |

All complete final body states match byte for byte across all ten runs of each
case and both compilers. Physics work is 120 measured / 180 total steps in the
first case and zero in the render-only control. These short measurements do not
predict sustained interactive FPS. A prefilled, synchronized ten-second control
already gave 120 FPS both before and after; it did not reproduce the user's
progressive-scene regression.

## Reproduce the configurations

Use the exact revisions and artifact hashes in [provenance.json](provenance.json).
Run compiler commands from `SilexProject/`, sharing its `.silex` cache. Compile
with each reference/corrected compiler separately:

```sh
silex compile Silex-Benchmarks/Sources/FallingBodies2D/Main.sx --backend llvm --release -o /tmp/falling-bodies-2d
/tmp/falling-bodies-2d --stress --smoke --batch-1 --immediate --no-panel --fixed-work
/tmp/falling-bodies-2d --stress-3000 --smoke --immediate --no-panel --render-only --fixed-work --batch-1
```

For the progressive diagnostic, copy that exact `Main.sx` outside the tracked
source and apply [progressive-diagnostic.patch](progressive-diagnostic.patch).
The patch changes only the `--smoke-30` duration to 90 seconds and prints cadence
once per reporting interval. Compile the copy with each compiler and run each
binary with `--smoke-30 --immediate`, sequentially. This patch records the measured
probe; it does not change the public benchmark's flags or duration.

Only one heavy compile or benchmark ran at a time. The compilation of this large
LLVM Release program exceeded the initial 4 GiB guard; successful comparison
builds used 6 GiB / 900 seconds / eight processes on the 18 GiB host, with
`SILEX_COMPILATION_WORKERS=1`. Runtime guards remained 4 GiB, 90 seconds for
fixed-work and 150 seconds for the progressive diagnostic. Guards sample process
group RSS and physical footprint; they are not kernel memory limits. Cache state
differed between builds: no compilation-time gain is claimed. The open Spec's
4 GiB compilation requirement is not satisfied by this exception.

## Correctness and retained evidence

The compiler correction includes four runtime tests, including 256 deterministic
small graphs checked against a separate reachability oracle. Structural traversal
tests fail on the reference runtime. Fourteen LLVM executable fixtures pass in
Debug/Release; Physics `WorldLifetime` (six tests) and `ApplicationIntegration`
(eight tests), `zig build check`, and `zig build test` pass. The installed compiler
has the same SHA-256 as the measured candidate. Recompiling through the installed
`silex` command and running the fixed-work smoke gives identical state and counts.

- [Measurements](measurements.json), [summary](measurements-summary.json), and
  [raw reports](measurements-raw.log) preserve all warm-ups and measured samples.
  Only duplicate `state[...]` lines are removed from those raw reports; their
  exact blocks are in [fixed120-state.txt](fixed120-state.txt) and
  [render3000-state.txt](render3000-state.txt). Each report and measurement records
  the block hash. [Original log hashes](raw-log-sha256.json) identify the inputs.
- [Progressive observations](progressive.json) and complete
  [reference](settled-before.log) / [corrected](settled-candidate.log) diagnostic
  logs retain the interrupted reference and all corrected cadence observations.
- [Validation](validation.json), [validation logs](validation.log),
  [fixture outputs](fixtures.json), [reference test failures](unit-before.log),
  and [resource guards](guards.json) preserve qualification (trailing whitespace
  normalized in the combined validation log), including the failed
  initial compilation guard and successful installation.
- The `*.sample.txt` files retain original profiles; their stripped private
  symbols can resolve to a neighboring exported formatting symbol. They do not
  prove a formatting bottleneck. The `*-profiled.log`, `profiled.log`, and
  `*synchronized.log` controls retain the associated reports.

No benchmark implementation, presentation setting, public Physics API or solver
algorithm was changed by this correction. No 800 FPS or cross-platform performance
claim is made.
