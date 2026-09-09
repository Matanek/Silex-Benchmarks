# Node scheduling

This public benchmark compares the per-frame scheduling cost of the object
scene tree with a direct ECS workload. Construction and startup are outside the
measured interval. Every moving case performs the same translation and verifies
the resulting position checksum.

The six strategies are:

- `nodes_static`: mounted `Node2D` instances without authored processing;
- `nodes_processing`: authored `Node2D` callbacks without component mutation;
- `nodes_mixed`: ten percent moving Nodes among static built-in Nodes;
- `nodes_moving`: `Node2D` subclasses moving through `on_process`;
- `ecs_static`: the same number of mounted transforms without an update system;
- `ecs_moving`: one ECS query mutating every transform.

Compile from the workspace root in Release mode, then run each configuration in
a separate process:

```sh
silex compile Silex-Benchmarks/Sources/NodeScheduling/Main.sx --release -o /tmp/node-scheduling
/tmp/node-scheduling nodes_static 10000 200
/tmp/node-scheduling nodes_processing 10000 200
/tmp/node-scheduling nodes_mixed 10000 200
/tmp/node-scheduling nodes_moving 10000 200
/tmp/node-scheduling ecs_static 10000 200
/tmp/node-scheduling ecs_moving 10000 200
```

Repeat each row in independent processes before comparing it. Results are
specific to the recorded OS, architecture, compiler commit, package commits,
and Release build; they do not predict another target.

The initial before/after campaign is archived under
[`Baselines/2026-09-09-macos-arm64`](Baselines/2026-09-09-macos-arm64). It
demonstrates the intended trade-off: static, callback-only, and mostly static
object scenes no longer pay recursive ECS synchronization. Even the deliberately
transform-heavy object workload stays close to the direct ECS query once its
spatial parent relation is resolved at mount time.
