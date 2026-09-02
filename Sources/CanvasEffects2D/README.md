# Canvas effects 2D final campaign

This public, offscreen benchmark runs the five final Canvas-effect workloads at
1920×1080 with display density 1, immediate mode, VSync disabled, and no
presentation:

- `analytic-static`: 4,096 placements sharing one shadowed 64×32 rounded box;
- `analytic-transform`: the same placements with transform-only animation;
- `filtered-static`: 128 retained 128×64 path, vector-text, and image groups;
- `filtered-dynamic`: 64 retained 256×128 groups whose path and label mutate;
- `fullscreen`: one radius-24 full-target stress group, reported separately.

Every process performs 120 warm-up frames and 600 measured frames. The runner
builds one Release executable, interleaves seven independent processes per
case, preserves stdout and `/usr/bin/time -l` output, and records machine,
backend, package commits, fixed seed, peak RSS, and renderer-owned memory.
`Summarize.py` emits the CSV and Markdown report and rejects a MAD/median above
5% or a failed structural gate.

Run from the Part worktree while the benchmark, Canvas, and Scene2D repositories
are clean:

```sh
Silex-Benchmarks/Sources/CanvasEffects2D/RunCampaign.sh
```

The backend has no reliable public GPU timestamp. The report therefore keeps
CPU preparation/submit and queue-drain observations separate and leaves GPU
time unavailable. The full-screen result is informative and is not used to
accept or reject ordinary retained paths.

`RunLegacyRegression.sh` separately builds the four unchanged no-effect
workloads against the exact pre-Part07 and candidate package commits. After one
discarded process per executable, it alternates seven Release processes for
each version and applies the 5% primary-metric gate required by the spec:

```sh
Silex-Benchmarks/Sources/CanvasEffects2D/RunLegacyRegression.sh
```

The script derives temporary baseline packages with `git archive`; it does not
move a repository checkout or alter a branch.
