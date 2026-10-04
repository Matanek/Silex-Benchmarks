# Qualification du profil public Tensor

Sur macOS 26.6.2 / Apple M3 Pro / Metal, Silex 0.47.1, le profil public observe
les coûts sans ajouter de transfert ni changer les valeurs d’entraînement.
Le suivi des buffers reste actif sans profil ; une période active ajoute les
incréments. La campagne évalue ces deux coûts mais ne les déclare pas nuls.

## Provenance et méthode

La référence est le binaire du lot Adam accepté (Module Tensor `e742c9a`,
identique à `27f6cae`). Le candidat possède l’instrumentation de Task-02.
[Configuration](Configuration.json) conserve les sources et binaires par SHA256,
la toolchain, les dépendances, OS et matériel. Le SHA produit est consigné dans
`Candidate.json` après validation. Aucun build ou test ne concurrence les mesures.

[Protocole](Protocol.md) : cinq triplets par famille, ordre alterné et rotation
MLP/CNN/RNN, puis cinq paires A/A du même binaire par famille. 75 processus,
4 050 lignes de timing et 90 instantanés publics, sans échantillon éliminé.
L’option active ouvre un profil par device avant les uploads et lit/imprime ses
compteurs après les sections chronométrées. Elle inclut donc le parcours GPU
et son setup, pas uniquement une étape. Les temps sont muraux avec l’attente GPU
explicite existante ; aucun temps device n’est prétendu.

## Parcours complet résident

Médianes en ms par étape. « Inactif » compare le candidat sans profil à la
référence ; « actif » compare la collecte d’une période au même candidat inactif.
« A/A » compare les deux groupes de contrôle inactifs.

| Famille/batch | Référence | Inactif | Actif | Δ inactif | Δ actif | Δ A/A |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MLP/4 | 35.351 | 34.773 | 34.806 | -1.64% | +0.10% | +0.34% |
| MLP/16 | 34.964 | 34.022 | 35.842 | -2.70% | +5.35% | -0.72% |
| MLP/64 | 35.028 | 34.467 | 35.450 | -1.60% | +2.85% | +0.15% |
| CNN/1 | 36.309 | 34.646 | 35.075 | -4.58% | +1.24% | -2.00% |
| CNN/4 | 35.675 | 35.095 | 34.967 | -1.62% | -0.37% | -6.93% |
| CNN/16 | 39.484 | 35.954 | 34.837 | -8.94% | -3.11% | -3.80% |
| RNN/4 | 78.958 | 80.088 | 80.883 | +1.43% | +0.99% | -1.31% |
| RNN/16 | 79.080 | 80.167 | 79.605 | +1.37% | -0.70% | -1.48% |
| RNN/64 | 79.264 | 79.836 | 79.118 | +0.72% | -0.90% | +2.21% |

Les médianes inactives vont de −8,94% à +1,43% sur ces neuf charges ; actives de
−3,11% à +5,35%. Ce sont des écarts observés, pas des gains ni une garantie de
non-régression. Au MLP/16 résident, la collecte active est à +5,35%, avec une
plage appariée de −3,04% à +10,64%. Une seule campagne ne sépare pas parfaitement
le coût des incréments de l’ordonnancement et du bruit. Les min/max et MAD de
chaque phase ainsi que chaque paire sont dans [Comparisons.csv](Comparisons.csv).
Les phases de construction/lecture quasi nulles peuvent être quantifiées à zéro ;
les rapports correspondants sont absents quand leur dénominateur est nul.

## Écarts à examiner

Tous les signaux GPU ≥5%, supérieurs aux MAD des deux groupes et positifs dans
au moins quatre paires sur cinq, sont conservés ci-dessous. Les contre-épreuves
A/A produisent elles-mêmes cinq signaux, dont le forward RNN/4 chaud à +7,16%,
le backward MLP/4 à +6,56%, le SGD CNN/16 à +12,19% et le parcours complet
MLP/16 à +8,90%. Cela limite l’attribution ; cela ne prouve pas que les écarts
inactifs/actifs sont entièrement du bruit.

| Comparaison | Phase | Famille/batch | Δ médiane | Plage appariée |
| --- | --- | --- | ---: | --- |
| Inactif | `forward_cold` | CNN/16 | +7.54% | +0.30% à +32.64% |
| Inactif | `forward_cold` | CNN/4 | +19.53% | -4.43% à +31.46% |
| Inactif | `forward_hot` | RNN/4 | +14.07% | -4.21% à +15.06% |
| Inactif | `step_end_to_end` | CNN/4 | +7.05% | -9.88% à +17.15% |
| Actif | `backward_cold` | CNN/1 | +20.75% | -0.64% à +30.60% |
| Actif | `backward_hot` | MLP/4 | +10.45% | -5.25% à +32.84% |
| Actif | `loss_read` | MLP/16 | +5.11% | -4.11% à +30.60% |
| Actif | `step_adam` | MLP/4 | +6.52% | +0.69% à +15.39% |
| Actif | `step_end_to_end` | MLP/16 | +5.54% | +0.74% à +23.48% |
| Actif | `step_resident` | MLP/16 | +5.35% | -3.04% à +10.64% |
| Actif | `step_sgd` | MLP/64 | +7.22% | +1.01% à +12.54% |

L’ajout du profil ne touche pas les chemins CPU ; plusieurs phases CPU présentent
également des signaux dans le CSV. On conserve donc les régressions possibles,
les écarts froids jusqu’à +20,75% et chauds jusqu’à +14,07%, sans promettre une
collecte gratuite ni une non-régression universelle. L’API sert à observer avant
optimisation ; aucune accélération n’est admise depuis cette campagne.

## Correction, mémoire et compteurs

Les transferts et compute_passes des 54 sections chronométrées de chaque
processus correspondent exactement dans les cinq groupes. Chaque instantané
public satisfait passes=bindings=dispatches et soumissions=fences. Les neuf
instantanés end-to-end par répétition correspondent aux compteurs GFX indépendants
pour uploads/downloads/passes. Les sections résidentes gardent zéro transfert.
Les pics de buffers demandés dépendent aussi de l’achèvement et de la rétention
réelle des parents : ils ne sont pas présentés comme VRAM physique.

Tous les processus passent le vérificateur CPU/GPU. La qualification séparée
conserve 103 tests consommateur (95 existants et huit nouveaux), 14 guards
internes dont deux durées de vie, le diagnostic d’immuabilité et les vérificateurs
neuronaux Debug/Release. Les compteurs existants restent compatibles. Un témoin
SGD indépendant conserve exactement les mêmes valeurs avec collecte inactive ou
active et vérifie la solution analytique après deux étapes. Le stress ouvre
18 000 profils, chacun réinitialisé, et retourne au registre initial après les
derniers buffers/profils ; aucun stockage n’est retenu par le profil public.

RSS processus (Mio), médiane et plage, mesuré par `/usr/bin/time -l` :

| Groupe | Médiane | Min–max |
| --- | ---: | --- |
| reference | 72.20 | 71.50–72.42 |
| off | 72.22 | 71.67–72.66 |
| on | 72.22 | 71.64–72.59 |
| control-a | 72.27 | 71.62–72.66 |
| control-b | 72.28 | 71.66–72.59 |

Ces RSS ne prouvent pas une borne en octets de l’allocateur ni une différence
mémoire entre profils. La borne de propriété est structurelle et testée : un
état par device ayant des buffers ou profils vivants, une période par profil,
aucun historique conservé. Les instantanés ne contiennent que 18 entiers.

## Reproduction

Depuis la racine du groupe Worktree qualifié, compiler `Neural.sx` en Release
avec `ZIG_GLOBAL_CACHE_DIR="$PWD/.silex/zig-global"` et la toolchain consignée.
Les options `--measure-*` et `--profile-*` sélectionnent les trois familles.
`CampaignDriver.py.txt` conserve le pilote exact utilisé et les empreintes de
sa référence ; une nouvelle campagne doit prendre un nouveau dossier de résultat.
`Summarize.py [dossier]` revalide les faits des logs et régénère le CSV avec la
bibliothèque standard Python. Les logs, temps/RSS et qualification utiles sont
conservés avec leurs checksums ; aucun binaire ni cache n’est versionné.
