# Qualification conservée

Commandes exécutées séquentiellement depuis `.specs/Tensor-Training-Models-Acceleration/Worktree/` :

```text
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global" Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/Consumer
ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global" Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/Consumer/Tests/Profiling.sx
```

Suite consommateur complète : 101 succès avant les deux derniers témoins ;
le fichier Profiling final passe ses huit cas, portant l’union à 103.
Chacun des sept fichiers directs `Packages/Tensor/Tests/*.sx` est ensuite
exécuté séparément par `silex test`, soit 14 guards verts. Un unique build à
la fois utilise le cache de groupe. Aucun test ne concurrence les mesures.

`ProfileSnapshotMutation.sx` compilé avec `-o .silex/profile-mutation` est rejeté
avec `cannot assign through immutable field 'downloads'` ; il ne produit pas
de binaire. Les deux `Neural.sx` compilés en Debug et avec `--release` passent
`--verify` : uploads=0 et hidden_downloads=0. Les sources de compilation et
empreintes produit figurent dans la configuration et Candidate.json.

GPU/SDL est exécuté hors sandbox après approbation automatique ; aucun pipeline,
shader, toolchain ni asset natif n’est remplacé. Les profils publics observent
les appels du thread appelant, sans nouvelle garantie de concurrence.
