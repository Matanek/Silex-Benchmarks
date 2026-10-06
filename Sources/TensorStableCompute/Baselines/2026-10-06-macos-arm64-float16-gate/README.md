# Float16 gate: indeterminate for the current Tensor HLSL path

Apple M3 Pro / macOS 26.6.2 arm64 / Metal, October 6, 2026. These are correctness
and configuration observations, with no timing or memory admission.

The public HLSL probe qualifies 15 conversions against an independent Python
half oracle: signed zeros, normal/subnormal boundaries, tie rounding, overflow,
infinities and NaN classification. Native Debug and Release agree. Actual
legacy `half` and `min16float` casts/additions retain float32 precision in the
generated MSL. The dynamic addition reads zero from a GPU buffer and returns
1000.25; true half rounding would return 1000. A constant-folded earlier witness
was replaced before the current conclusion.

The native Metal diagnostic control performs the same conversions and addition
in explicit half and returns 1000 in both modes. This establishes these hardware
operations, while locating the observed limitation in the configured HLSL path.
It does not establish a lack of hardware support, nor qualify half matmul,
reduction, convergence or a time/memory benefit. The native control is not a
portable Tensor implementation or a public workaround.

The installed Shadercross 3.0.0 CLI/header provide no native16 activation option
in the inspected interface, and explicit `float16_t` is rejected by this compiler.
Source, diagnostic, header/tool hashes, properties and help are retained. This
is a conclusion about this exact configured pipeline, not all future SDKs.

The full float16/mixed Tensor gate remains **indeterminate**. No float16 dtype
or mixed training API is added; Tensor remains float32. A positive future gate
must first preserve genuine HLSL native16, then qualify matmul/reduction,
precision/convergence, master weights and sensitive states in float32, explicit
scaling and atomic overflow handling, and actual time/memory benefit.

Run `python3 Verify.py` here without a GPU. It recomputes the oracle and raw
bit observations, checks both modes, source integrity, explicit-type rejection
and all six linked HLSL targets. [Config.json](Config.json) pins exact sources,
compiler, SDK and dependency heads. [Protocol.md](Protocol.md) was fixed before
each discriminating experiment. [Task17-Canonical-Qualification.json](Task17-Canonical-Qualification.json)
indexes the eight passing commands and logs. [Task17-Float16-Composition-Summary.json](Task17-Float16-Composition-Summary.json)
records format, architecture and fingerprints for six targets; it proves
composition/linking, not runtime half support on those targets.

The canonical `Float16Gate.sx` runs through public HLSL compilation;
`Float16MetalControl.sx` is a macOS/Metal-only hardware control. Their source
snapshots and the actual generated MSL are stored beside these observations.
