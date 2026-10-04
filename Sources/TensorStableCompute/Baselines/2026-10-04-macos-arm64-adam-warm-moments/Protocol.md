# Protocole de comparaison Adam

## Identités et portée

Référence Tensor 175c3834e74390999a6508eec0e8ba28d0ba863a, candidat
Tensor e742c9a1f55d3dcb4a3d64199607f023e512a193. La référence ne diffère de
f1d6d60 que par ses tests. Le candidat change Adam.step, ajoute la garde
AdamWarmState et les notes de développement. Configuration.json fixe les
six commits, les hashes du compilateur et des deux binaires, la machine et
le banc. Le SHA benchmark candidat 29494da est le banc d’entrée, avant ajout
de ces données ; ses sources sont identiques à celles du binaire de référence.

Silex 0.47.1 ReleaseFast compile Neural.sx en Release ; exécution sur macOS
26.6.2 / arm64, Apple M3 Pro, Metal, 18 Gio. La donnée n’établit ni performance
hors M3 ni timestamp device. Les autres cibles ne reçoivent aucun changement
natif, ABI, manifest ou chemin spécifique ; la source Adam est commune CPU/GPU.

## Conditions fixées avant mesure

Même Neural.sx et jeux de tailles que la baseline : MLP 4/16/64, CNN 1/4/16,
RNN 4/16/64. Cinq paires de processus par famille ; A/B aux répétitions 1/3/5,
B/A aux 2/4. Rotation des familles identique au protocole de baseline. Chaque
processus refait le vérificateur fonctionnel ; toutes les données sont admises
ou le processus invalide stoppe la campagne. Pas de compilation ni test
concurrent avec les mesures. Les régions GPU incluent leur attente explicite,
les régions résidentes excluent les transferts ; les observations sont séparées.

La règle fixée dans Task-03 avant modification et campagne porte sur Adam et
step_resident : gain des médianes >=5 %, plus grand que les MAD des deux
configurations et au moins quatre paires favorables sur cinq. Un contrôle
forward/backward défavorable >=5 % dépassant les MAD exige une enquête.
Le rapport conserve les résultats qui n’atteignent pas ces seuils et tous
les contrôles. Les paires ont un label temporel alterné ; le CSV rapporte
aussi la médiane des gains par paire, min/max et les dispersions.

## Contre-épreuve supplémentaire

Les écarts sur les phases non modifiées motivent NegativeControl : cinq
paires supplémentaires par famille du même binaire de référence, même rotation
et tailles, ordres a/b puis b/a. Aucun échantillon n’est retiré. Ce contrôle
mesure le bruit que cinq premiers points et leurs MAD peuvent sous-estimer ;
il ne change pas rétroactivement le critère d’admission ni n’établit une
non-régression générale des autres kernels. Le rapport borne les conclusions.

## Qualification

107 tests sont verts (95 consommateurs et 12 internes), avec Metal exécuté
et non sauté. Les oracles existants sont testés sans régénération Python.
AdamWarmState prouve moments constants indépendants, steps, absence de
gradients, initialisation différée et les comptes 16→14 par paramètre chaud.
La suite OptimizerState/OptimizersGPU et les trajectoires MLP/CNN/RNN conservent
leurs gardes. Les non-finis des moments sont refusés par le témoin ; les
paramètres, buffers et graphes restent sous les bornes des gardes existantes.
Debug et Release passent --verify avant chronométrage ; le diagnostic d’un
moment sur le mauvais device est toujours rejeté par la même cause.

Le premier rejeu consommateurs a trois refus de shader vide pendant des
constructions concurrentes du banc : il reste un incident de qualification,
pas un résultat vert. OptimizersGPU isolé puis la suite entière --nocache
sérialisée passent. Les logs de cet incident et des rejeux sont conservés ;
aucune cause de concurrence n’est affirmée sans réduction supplémentaire.

## Reproduction

Exécuter depuis la racine Worktree de la Spec, avec les six checkouts et liens
workspace confinés correspondant à Configuration.json :

```sh
export ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global"
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/AdamWarmState.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/Consumer --nocache
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/OptimizerState.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/AutogradLifetime.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/PipelineCache.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/PerformanceGuards.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/NeuralPerformanceGuards.sx
Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx --debug --nocache -o .silex/tensor-neural-adam-warm-debug
.silex/tensor-neural-adam-warm-debug --verify
Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx --release --nocache -o .silex/tensor-neural-adam-warm-release
.silex/tensor-neural-adam-warm-release --verify
```

Pour reconstruire le binaire de référence, partir de ses sources exactes sans
changer la lane active, puis revenir aux liens/heads candidats avant comparaison.
La campagne exécutée emploie son binaire conservé et son SHA vérifié, pas un
binaire supposé équivalent reconstruit après coup. Les drivers exacts sont
archivés dans CampaignDriver.py.txt et NegativeControl/CampaignDriver.py.txt ;
ils attendent les deux chemins de binaires du groupe et refusent d’écraser les
résultats. Choisir une nouvelle destination datée pour refaire une campagne.
GPU/SDL requiert l’accès Metal de l’hôte. Ne pas compiler dans un package et ne
pas créer de lien utilisateur ; aucune construction simultanée pendant mesure.

Les rapports se reconstruisent depuis leurs données, sans réexécuter Tensor :
`SummarizeNeural.py <dossier reference ou candidate ou NegativeControl/a/b>`,
puis `python3 SummarizeComparison.py` depuis ce dossier de résultats.
Le fichier Checksums.sha256 conserve les empreintes de la campagne terminée.
