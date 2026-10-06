# Public prepared MSE/AdamW training: admitted workloads and regression

October 6, 2026, Apple M3 Pro, macOS 26.6.2 arm64 / Metal, native Release.
The complete synchronized training step is measured, including zero-grad,
forward, scalar MSE, reference backward and AdamW update. Preparation is
separate; Profile is off. Both arms use one exact compiler and identical
sources, and retain the prepared owner. Sixteen warmup steps precede 128 hot
steps for case 0 and 64 for cases 1–2. No samples are excluded.

| Workload | Paired median change | MAD (points) | Favorable pairs | Decision |
|---|---:|---:|---:|---|
| MLP(2,2,4,2) | −6.208% | 1.091 | 16/16 | Admitted gain |
| MLP(16,16,32,8) | +6.487% | 0.813 | 0/16 | Admitted regression; keep eager |
| Dense–LayerNorm–tanh–Dense(4,2,4,2) | −20.661% | 1.183 | 16/16 | Admitted gain |

All A/A controls pass the unchanged 5% / 3 MAD / 14-of-16 rule. The 192
isolated processes include 16 balanced A/B pairs and 8 A/A pairs per arm and
workload. Full final output, loss, gradients, weights and both moments are
printed: all 229,312 GPU scalars agree exactly across arms/processes. Every
process checks an independent CPU eager model at unchanged absolute tolerance
2e-5, together with counters, rates and hyperparameters. AdamW uses epsilon
0.01, betas 0.8/0.9 and weight decay 0.07; LayerNorm epsilon is 0.25.

Run `python3 Verify.py` here without a GPU to verify file integrity, reconstruct
raw measurements, scalar comparisons, RSS, CSV/JSON and all admission decisions.
[Config.json](Config.json) pins the compiler, measured binary, every module
source, benchmark, hardware and thresholds. [Summary.json](Summary.json)
retains medians, MAD, deltas, A/A controls and scope. [Samples.csv](Samples.csv)
and [Samples.json](Samples.json) index raw `.log` and `.time` files.
[Protocol.md](Protocol.md) is the frozen French protocol. `Source.sx.txt`,
`Snapshot-*.txt` and `CampaignDriver.py.txt` preserve the exact tested source
and collection procedure. The driver is historical: give a new campaign its
own output location and requalify exact sources/compiler before collection.

[Tensor-Qualification.json](Tensor-Qualification.json) records 470 passing tests
across 112 sources and their fingerprints. [Diagnostics.json](Diagnostics.json)
records 57 affected rejection fixtures; existing completed rejections from the
same unchanged candidate retain provenance and a positive exit class rather
than an invented numeric exit code. [Composition.json](Composition.json)
records six linked targets, format/architecture and source fingerprints.
[Qualification-Debug.log](Qualification-Debug.log) and
[Qualification-Release.log](Qualification-Release.log) cover full state and
warm restoration, guards before mutation, zero incoming callbacks, consumed
and 4,096-node graph boundaries, nonfinite propagation and 2,048 strided
replay steps across two devices. All resources are destroyed afterward.
The matched public documentation example also compiles and runs and the
package check passes; its commands/results are in [Documentation.json](Documentation.json).

The program is explicitly selected for compatible closed float32 families.
This campaign does not qualify a general gain, float16/mixed training, the
six complete model families, runtime outside macOS arm64/Metal, or isolated
GPU time. Six-target composition is not cross-target execution. RSS measures
process memory, not physical VRAM. Earlier private/public experiments before
the incoming graph guard are historical and are not admission of this source.
