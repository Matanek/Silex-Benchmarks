# Node scheduling campaign metadata

- Date: 2026-09-09 to 2026-09-10
- Host: macOS 26.6.2 (25G83), ARM64
- CPU: Apple M3 Pro
- Compiler: `8f1717ab060de27d5d9be2bb1b25ce063e5d4ae6`
- Baseline GFX.Nodes: `aabe529`
- Pre-cache GFX.Nodes: `124db229a98a269b991499423a39d31ec8b2373a`
- Candidate GFX.Nodes: `0f2c4c70aca9c6081d29ffdfa6384bae3e67143b`
- Entities: 1,000
- Warm-up frames: 20
- Measured frames: 200
- Samples: seven independent Release processes per available revision and
  strategy

Every revision was compiled with `--release --nocache` after linking that exact
package checkout. Construction, Application preparation, startup, checksum
validation, and shutdown are outside the timed interval. The baseline predates
the benchmark's strategy names, but the current source remains compatible with
its public API; its `nodes_static` path still recursively invokes the empty
lifecycle hook and full component synchronization for every Node.
