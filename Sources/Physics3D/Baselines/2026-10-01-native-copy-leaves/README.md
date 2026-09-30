# Copies de feuilles inutilisées après allocation — Native ARM64

Base compilateur `c26cc92`, physique `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
macOS ARM64, Release, bootstrap ReleaseFast. Quatre paires équilibrées
A/B, B/A, A/B, B/A par charge, priorité normale, aucun build/test concurrent.
Médiane des moyennes par exécution :

| Charge | Base ms/pas | Candidat ms/pas | Réduction |
|---|---:|---:|---:|
| AquariumFill | 7.628009 | 7.291174 | 4.42 % |
| ColumnPeak | 5.991233 | 5.870607 | 2.01 % |

Aquarium : 1 024 corps, 1 800 pas ; colonne : 256 corps, 600 pas.
Toutes les colonnes non temporelles sont exactement identiques, tous les
processus sortent avec le code 0. Hashes des exécutables dans `runs.json`.
`zig build check test -Doptimize=Debug` passe : tests Machine de demande
transitive, branches, boucles, adresses et chevauchements ; 216 tests sources ;
28 programmes oracle et admission rapide de l’optimiseur.

Une expérience antérieure appliquant la passe **avant** allocation a divergé
et échoué au garde de confinement ; elle est rejetée et ses temps exclus.
La passe qualifiée conserve les cartes de registres et de lanes établies.
Le déficit de débit interactif à 2 048 corps demeure ouvert. Linux ARM64
partage ce lowering mais n’a pas été exécuté ici ; X64 reste inchangé.
