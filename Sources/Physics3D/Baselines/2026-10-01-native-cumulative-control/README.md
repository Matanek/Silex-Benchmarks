# Contrôle cumulé Native / LLVM — physique 3D

Apple M3 Pro, macOS ARM64, applications Release. Bac à 1 024 corps,
1 800 pas fixes à 60 Hz ; mêmes sources Physics `d955a1a`.
Référence Native Silex `251d4ec`, candidat qualifié `6b825ef`, contrôle LLVM
figé de la campagne initiale. Les SHA-256 exacts figurent dans `runs.json`.

Six exécutions séquentielles : LLVM, original, qualifié, qualifié, original,
LLVM. Priorité normale pour ces seuls processus enfants, aucun build, test ou
profilage concurrent. Tous les codes de retour sont zéro. Les observables
physiques de chaque ligne sont **exactement identiques entre les trois
configurations**, hors colonnes de temps 1 et 14.

| Configuration | Moyenne des deux runs, ms/pas | Plage des moyennes |
|---|---:|---:|
| Native initial | 8,663646 | 8,605371–8,721920 |
| Native qualifié | 6,009690 | 5,998437–6,020943 |
| LLVM | 2,964235 | 2,954222–2,974248 |

La réduction cumulée du temps Native est **30,63 %**. Le Native qualifié
consomme encore **2,03 fois** le temps LLVM. Ces deux répétitions constituent
un contrôle cumulé, pas une nouvelle admission de passe : les quatre paires
par charge et les tests de chaque tranche restent leurs preuves d'admission.

## Changements conservés

- `87133ed` : compteurs de références LSE sur macOS ARM64.
- `e894c72` : interférence des paramètres entrants.
- `bbc8b9f` : champs de classes en registres.
- `c26cc92` : régions avec appels à agrégats dans les boucles.
- `984c757` : élimination tardive des copies de feuilles inutiles.
- `0c178bb` : admission des régions et chargements mixtes.
- `6f67308` : copies de pile stables.
- `f0123b8` : opérations de classes et ABI du tas.
- `6b825ef` : signatures externes résolues avant allocation des registres.

Les suites pertinentes passent sur le candidat conservé. Les cibles
Linux/Windows ARM64 et X64 ont une applicabilité documentée dans les rapports
de chaque tranche ; cette campagne n'apporte aucune nouvelle preuve
native sur ces systèmes.

## Limite interactive toujours ouverte

Le contrôle séparé de la scène à 2 048 corps est conservé dans
`../2026-10-01-native-boundary-residences/scene-2048/` : médianes Native
13,79 FPS / 17,75 ms par pas, LLVM 105,87 FPS / 9,25 ms par pas.
Native sature à quatre pas de rattrapage par image ; le facteur FPS dépasse
ainsi largement le facteur CPU par pas. Le profil Native séparé compte
3 403 échantillons dans World.step sur 3 758 du thread principal (~90,6 %).
Le compteur Render Frame inclut cette attente de simulation.

Ni 120 FPS actifs, ni sommeil correct de la pile, ni comparaison Unity
équivalente ne sont acquis. Aucun pas supprimé, taux physique réduit ou
endormissement forcé n'est utilisé pour améliorer les mesures. La scène
publique de la Spec est celle du candidat `6b825ef`, SHA-256
`6bf63f469834cf52140e35783df78bee048d56060844d48ccf5bfaba0e1b169a`.

## Expériences écartées après ce candidat

GPR régionaux, extension de l'inlining aux opérations de classes,
désactivation SIMD dans les grosses fonctions et propagation des copies de
pile vers les registres FP ont été examinés séparément. Aucun ne franchit
une admission justifiant sa conservation. La dernière expérience retire
34 accès à la pile dans solve_sphere_point3d mais ne réduit pas le coût de
la simulation complète : nombre d'instructions et temps réel ne sont pas
interchangeables. Les patches et logs diagnostiques sont conservés dans le
cache de travail de la Spec ; aucun de ces essais n'est dans le candidat.
