# Appels agrégés dans les boucles — ARM64 Native

Comparaison locale macOS ARM64 Release, compilateur bootstrap ReleaseFast.
Base compilateur `bbc8b9ff1754fe44440ef8fa9f0cf08b67ffc3b1` ; candidat :
suppression de l’exclusion globale des appels agrégés dans les boucles.
Physique figée à `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.

Quatre paires équilibrées A/B, B/A, A/B, B/A, priorité normale, aucune
compilation ou autre mesure simultanée. Temps moyen par exécution puis
médiane des quatre exécutions ; aucun temps de compilation inclus.

| Charge | Base ms/pas | Candidat ms/pas | Réduction |
|---|---:|---:|---:|
| AquariumFill | 8.163799 | 7.634332 | 6.49 % |
| ColumnPeak | 6.281516 | 6.058964 | 3.54 % |

Les observables physiques de chaque ligne CSV sont strictement identiques.
Les SHA-256 des exécutables sont dans `runs.json`. Aquarium : 1 024 corps,
1 800 pas ; colonne : 256 corps, 600 pas. La suite `zig build check test
-Doptimize=Debug` est verte, y compris une régression Machine vérifiant les
arguments agrégés en mémoire et les calculs indépendants en registres.

Le déficit actif à 2 048 corps reste ouvert. Ces chiffres ne constituent pas
une mesure interactive et ne prouvent aucun gain X64 ou autre système.
