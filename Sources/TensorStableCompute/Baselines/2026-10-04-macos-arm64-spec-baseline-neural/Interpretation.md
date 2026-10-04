# Baseline Tensor actuelle : qualification et interprétation

## Ce que la campagne établit

Cette campagne exerce Silex 0.47.1 et Tensor 0.2.0 sur macOS 26.6.2, Metal,
Apple M3 Pro, 18 Gio. Les identités exactes des six dépôts, des binaires et du
banc sont dans [Configuration.json](Configuration.json) et [Summary.md](Summary.md).
Le SHA benchmark désigne le banc avant ajout de ses résultats ; le commit qui
contient ce dossier est un commit de données, sans changement du banc Neural.sx.
Tensor 175c383 contient uniquement une correction de qualification et deux
nouvelles gardes ; le calcul, les shaders et les optimiseurs restent ceux de
f1d6d60. Aucun gain avant/après n’est revendiqué par ce changement de tests.

Quinze processus Release indépendants, cinq par famille, produisent 810 lignes
brutes. Chaque processus vérifie les résultats avant sa mesure. Le passage
Debug préalable et la validation Metal des tests détectent les erreurs de
ressources. Les phases résidentes mesurées n’ont ni upload ni download.
Les RSS maximales médianes sont 71,5 Mio (MLP), 72,1 Mio (CNN), 72,0 Mio (RNN) ;
ce sont des RSS de processus complet, pas une mesure des octets GPU actifs.

## Coûts observés

| Charge | Forward chaud CPU / GPU | Étape résidente Adam CPU / GPU |
|---|---:|---:|
| MLP batch 16 | 4,4300 / 2,5073 ms | 12,6157 / 37,1577 ms |
| MLP batch 64 | 17,2127 / 2,4013 ms | 41,0170 / 37,7093 ms |
| CNN batch 16 | 2,3390 / 2,5525 ms | 6,1730 / 41,7335 ms |
| RNN batch 64 | 28,7325 / 20,1975 ms | 59,8385 / 86,4635 ms |

Le rapport brut donne médiane, min/max et MAD pour toutes les charges. Le MLP
batch 64 est le seul pas complet résident GPU plus rapide sur cette grille ;
son avantage médian de 1,09× est un constat local à confirmer par un contrôle
équilibré avant toute conclusion de petit gain. Le CPU précède le GPU dans
chaque batch. Les familles tournent entre répétitions, pas les placements.

Adam seul coûte environ 23 ms sur MLP pour tous les batches et 64 passes par
step. Sur CNN, il coûte 22–26 ms et 64 passes ; sur RNN, 27–28 ms et 80 passes.
Le forward MLP chaud n’a que 5 passes, le backward 33 ; le pas résident Adam
complet en a 111. CNN en a 111 aussi ; RNN en a 243 (forward 43, backward 111).
Les valeurs normalisées de SGD peuvent être fractionnaires : le premier step
mesuré initialise le momentum, les suivants le réutilisent ; cette phase
mélange donc initialisation et régime établi. Adam mélange également première et prochaines étapes : son implémentation
recalcule actuellement deux tenseurs nuls par paramètre même lorsque les
moments existent, puis les remplace par ces moments. Le compte de passes reste
donc identique à froid et à chaud ; cette répétition est un premier candidat
borné à éliminer, en conservant exactement l’initialisation de la première étape.

La phase `step_end_to_end` utilise SGD sans momentum, tandis que
`step_resident` utilise Adam. Elle inclut placement du modèle, entrées, lecture
de perte et retour des paramètres au CPU (MLP/CNN : 6 uploads, 5 downloads ;
RNN : 7 uploads, 6 downloads). Leur différence n’est **pas** le coût isolé des
transferts. Les observations unitaires sont séparées dans `loss_read`.
Les mesures sont murales avec attentes explicites, pas des timestamps device.

## Contre-épreuve : mêmes opérations, attentes explicites différentes

[Source conservée](Attribution/EagerOverhead.sx.txt), cinq processus Release,
ordre alterné tailles/attentes, warmup de cinq chaînes, vingt chaînes mesurées.
Chaque chaîne exécute add, multiply, matmul, sum, add sur matrices de uns n×n.
Le résultat indépendant attendu est n³+1. Chaque région GPU vérifie exactement
100 passes, zéro transfert ; le readback de contrôle est hors mesure.
Le temps rapporté additionne la région hôte et l’attente finale. Le temps hôte
inclut les éventuelles attentes internes ; il n’est pas un temps GPU pur.

| Placement | n | Attente par itération | Médiane ms/chaîne | Min/max | MAD relatif |
|---|---:|---|---:|---:|---:|
| cpu | 2 | none | 0.0063 | 0.0062 / 0.0072 | 1.6 % |
| cpu | 64 | none | 25.9250 | 24.4201 / 26.3464 | 1.6 % |
| gpu | 2 | false | 1.8846 | 1.7097 / 2.5603 | 8.5 % |
| gpu | 2 | true | 1.7575 | 1.5997 / 2.0160 | 9.0 % |
| gpu | 64 | false | 2.0705 | 2.0278 / 2.3279 | 1.3 % |
| gpu | 64 | true | 3.0303 | 2.8714 / 4.9962 | 5.2 % |

À n=2, déplacer l’attente explicite à la fin ne supprime pas le coût : les
variantes se recouvrent dans leur dispersion. La même chaîne CPU est environ
0,006 ms, contre environ 1,8 ms côté GPU. À n=64, le CPU monte à environ 26 ms,
le GPU sans attente par itération reste proche de 2 ms ; les attentes par
itération ajoutent un coût visible. Le retard GPU des toutes petites charges
ne se réduit donc pas au calcul CPU du modèle ni à l’attente finale du banc.
Il subsiste sans compilation froide de pipeline ni transfert dans la région.

L’inspection du propriétaire explique une frontière supplémentaire :
`GPUStorage.drop` attend sa fence avant de libérer ses ressources ; chaque
opération eager crée une sortie et une soumission. Les gardes internes
`PerformanceGuards` confirment cinq allocations, cinq fences et cinq passes par
chaîne chaude, sans nouvelle compilation de pipeline. Les causes restantes
(allocations, émission des commandes, attentes de destruction, exécution des
petits kernels) ne sont pas séparées temporellement par cette expérience.
Le prochain résultat est leur observation par device/période, puis une
variation bornée à travail identique ; aucun pool ni regroupement n’est admis
sur le seul nombre de passes.

## Qualification et correction du témoin RNN

95 tests consommateurs dans 25 fichiers, dont les oracles différentiels
existants, et 11 tests internes passent : durée de vie autograd (2), état des
optimiseurs (2), pipelines (5), ressources eager (1), ressources neurales (1).
Les [logs](Qualification/Consumer-Tests-Corrected.log) exercent effectivement
Metal. 89 diagnostics rejettent leur entrée sans crash ; leurs sorties sont
conservées dans [Diagnostics.json](Qualification/Diagnostics.json) et ont été
confrontées aux fixtures. Les vérificateurs Neural Debug/Release passent aussi.
Les références externes déjà générées sont exécutées ; leurs outils Python et
les bibliothèques d’oracle ne sont pas régénérés durant cette qualification.

Le test RNN initial divergeait après Adam : des paires d’entrées opposées,
biais nuls et tanh impair annulent analytiquement les gradients des biais.
Les résidus float32 CPU/GPU de 10⁻⁹, comparables à epsilon=10⁻⁸, sont amplifiés
par la mise à jour -lr*g/(abs(g)+epsilon). Deux contre-épreuves passent : même
cas avec epsilon=10⁻⁴, ou légère asymétrie des entrées avec epsilon inchangé.
La correction retenue utilise l’asymétrie et resserre les tolérances de
paramètres 0,15→0,003 et gradients 0,03→0,003, avec contrôle des non-finis.
La propriété d’annulation reste un test indépendant au zéro analytique
(tolérance 10⁻⁷). Un second test vérifie la première mise à jour Adam de petits
gradients signés contre sa formule (10⁻⁶), sans rabattre les gradients à zéro.
Aucun epsilon, shader ou calcul produit n’est modifié.

## Reproduction

Depuis la racine du groupe Worktree de la Spec, avec les six checkouts et
les liens workspace exclusifs décrits par Configuration.json :

```sh
export ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global"
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/Consumer
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/AutogradLifetime.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/OptimizerState.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/PipelineCache.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/PerformanceGuards.sx
Silex/Toolchain/zig-out/bin/silex test Packages/Tensor/Tests/NeuralPerformanceGuards.sx
Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx --debug -o .silex/tensor-neural-debug
.silex/tensor-neural-debug --verify
Silex/Toolchain/zig-out/bin/silex compile Silex-Benchmarks/Sources/TensorStableCompute/Neural.sx --release -o .silex/tensor-neural-release
.silex/tensor-neural-release --verify
```

Une commande GPU requiert l’accès SDL/Metal de l’hôte. La source exacte du
driver de cette campagne est [conservée](CampaignDriver.py.txt) comme archive
d’exécution : il attend les deux logs de vérification dans `../Memory/Artifacts`
et refuse d’écraser ce dossier de résultats. Pour une nouvelle campagne,
choisir un autre dossier daté et conserver les mêmes ordres et cinq processus.
Chaque processus reçoit `--measure-mlp`, `--measure-cnn` ou `--measure-rnn`.
`SummarizeNeural.py <dossier>` reconstruit CSV et résumé depuis les logs bruts.

Pour la contre-épreuve, copier les deux fichiers `.txt` du dossier Attribution
comme source `Investigations/EagerOverhead/Main.sx` et son `Package.json`,
compiler en Release depuis le groupe puis exécuter cinq processus, avec
`--reverse` aux processus 2 et 4. Ce dossier source est indépendant de Tensor.
Le driver des diagnostics est également conservé ; il faut confronter les
messages à leur cause attendue, sa garde automatique seule vérifiant surtout
rejet, absence de crash et absence de panne d’environnement.

## Limites et décision de route

Cette qualification porte sur macos-arm64/M3 ; aucun gain portable, aucune
gate float16, aucun modèle moderne ni reprise complète n’est établi. Les
archives de septembre restent une référence datée avec autre compilateur :
leur différence n’isole pas un effet de version. Les garde-fous de propriété
et les métriques ne suffisent pas à prouver les trois objectifs de la Spec.
L’élimination des deux tenseurs nuls recalculés puis jetés par paramètre Adam
est la prochaine tranche bornée : les compteurs actuels permettent déjà de
prouver sa fréquence. Le profil public par device/période reste nécessaire
avant de choisir une réutilisation de ressources ou un regroupement plus large.
