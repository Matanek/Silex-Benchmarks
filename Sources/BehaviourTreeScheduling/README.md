# Behaviour Tree scheduling

This public campaign consumes `AI.BehaviourTree` through the package boundary
and compares four ways to advance the same deterministic agent workload:

- `root` interrupts each instance and reevaluates every agent from the root;
- `resume` resumes every instance on every measured frame;
- `event` resumes only the agents present in the wake queue;
- `state_machine` applies the same event transition with direct handwritten code.

The shared tree has 11 nodes, maximum depth 5, and two root branches. Every
agent is initialized on the same long-running action. The measured event marks
0%, 1%, 10%, or 100% of 1,000, 10,000, or 100,000 agents as ready. The three
tree strategies share one immutable definition and keep one execution instance
per agent; the handwritten reference keeps only its direct state.

Before timing, `verify` runs all strategies from fresh identical data, compares
their final business-state checksums, and checks the exact condition, action,
and node-visit multiplicities. Timed runs omit the transition observer. A
separate replay records public node transitions so instrumentation does not
distort CPU time.

Run the complete Release campaign from the Spec worktree:

```sh
Silex-Benchmarks/Sources/BehaviourTreeScheduling/RunCampaign.sh
```

The runner first confirms that dependency resolution selects the Spec's
workspace-linked `AI` candidate. It compiles once in Release mode, runs the
functional verifier, then launches seven independent processes for every row
of the 3 × 4 × 4 matrix. Results retain raw output, package resolution, build
log, exact Silex/AI/benchmark commits, target, OS, CPU, parameters,
`measurements.csv`, and `Summary.md`.

Mean CPU time, sample variance, and range are reported per scheduling frame.
Sparse event rows are accepted only when their complete measured range is below
the ranges of both full-population strategies. The state-machine ratio exposes
the price of the generic structure without requiring the tree to beat direct
specialized code. macOS ARM64 results do not predict x64 behavior and are not a
portable performance guarantee.
