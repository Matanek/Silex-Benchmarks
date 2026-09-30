# Copies de pile stables — Native ARM64

Base Silex `0c178bb`, candidat `6f6730865a6f251eee9cea6dd8f5f24b3be16653` ; physique `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
macOS ARM64 Release, bootstrap ReleaseFast. Quatre paires A/B, B/A, A/B, B/A,
priorité normale, aucun build ni test concurrent. Médianes des moyennes :

| Charge | Base ms/pas | Candidat ms/pas | Variation |
|---|---:|---:|---:|
| AquariumFill | 6.835520 | 6.702441 | -1.95 % |
| ColumnPeak | 5.941590 | 5.675790 | -4.47 % |

Les observables physiques sont exactement égaux dans les seize exécutions,
toutes terminées avec code 0. Aquarium : 1 024 corps / 1 800 pas ; colonne :
256 corps / 600 pas. Le gain Aquarium dépasse le seuil préétabli de 1,5 % ;
la colonne respecte son garde de régression maximal de 3 %.

`check test -Doptimize=Debug` passe (code 0), avec régressions de snapshots,
écritures, jointures CFG, adresses exposées et résidences de registres.
La transformation suit les copies entre seuls stockages mémoire stables après
allocation ; elle ne prolonge aucun registre et conserve les opérations physiques.

Linux ARM64 applicable mais non exécuté ici. X64 reste inchangé. Cette étape
ne résout pas encore le déficit de la scène interactive à 2 048 corps.
