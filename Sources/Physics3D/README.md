# Qualify the first 3D physics foundation witness

This witness compares a native Silex program with an independently built
[Jolt Physics v5.6.0](https://github.com/jrouwe/JoltPhysics/releases/tag/v5.6.0)
oracle and an analytical result. It checks a quarter turn around Y, a solid
sphere's inertia, and a freely moving body with zero gravity and damping. It
does not qualify collision handling or a Silex 3D physics world.

From the `Jolt-3D-Physics` Spec's `Worktree/` directory, run:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/Run.py
```

The runner needs `silex`, CMake, Make, Clang and `curl`. It downloads the
official archive for commit `e77f175595e64cb44218cc9d9d56fc365ad0e36a`,
verifies its SHA-256, builds Jolt as a separate CPU-only static library, and
compiles both programs in Debug and Release. All downloads and build outputs
stay under `Worktree/.silex/physics3d-oracle/`. The workspace link to `STD`
is confined to `Worktree/`; the runner verifies its effective origin. The
official Jolt source is not copied into the Silex package or its consumers.

To use an already downloaded copy of that exact archive:

```sh
python3 Silex-Benchmarks/Sources/Physics3D/Run.py \
  --archive /absolute/path/to/JoltPhysics-e77f175.zip
```

The current fixture is [Fixture.json](Fixture.json), schema 1. Its integer
inputs are passed unchanged to both programs. The runner checks ten named,
finite observables against the analytical solution and against the other
program with the fixture's fixed absolute tolerance. It rejects missing or
duplicate fields, non-finite output, a mismatched revision and invalid inputs.
`--self-test` exercises these guards and a deliberately altered result without
building either program. A successful full run writes machine-readable
configuration and values to `Worktree/.silex/physics3d-oracle/qualification.json`.

Jolt is used under its [MIT license](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/LICENSE).
The downloaded archive retains the license and attribution. The oracle
implements only the fixture's Jolt API calls; it does not embed Jolt into a
distributed Silex binary.
