# Frontières de classes — Native ARM64

Base Silex `6f6730865a6f251eee9cea6dd8f5f24b3be16653`, candidat
`f0123b883e6674a2b3eb16806cab6944ee396da1` ; physique
`d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
macOS ARM64 Release, bootstrap ReleaseFast. Quatre paires A/B, B/A, A/B, B/A,
priorité normale, aucun build ni test concurrent. Médianes des moyennes :

| Charge | Base ms/pas | Candidat ms/pas | Variation |
|---|---:|---:|---:|
| AquariumFill | 6.587691 | 6.298036 | -4.40 % |
| ColumnPeak | 5.664415 | 5.628005 | -0.64 % |

Les observables physiques sont exactement égaux dans les seize exécutions,
toutes terminées avec code 0. Aquarium : 1 024 corps / 1 800 pas ; colonne :
256 corps / 600 pas. Toutes les paires Aquarium s'améliorent ; son gain médian
dépasse 1,5 %. La colonne respecte le garde de régression maximal de 3 %.

`check test -Doptimize=Debug` passe (code 0). Un destructeur effectif modifie
un compteur et écrase un registre volatil pendant que des valeurs entières
et flottantes restent vivantes. Les tests couvrent aussi l'invalidation des
caches et la coexistence des appels heap ABI avec les anciens adaptateurs.

Les champs d'initialisation restent en mémoire ; les handles et valeurs
indépendantes peuvent vivre en registres. Les valeurs traversant init/drop
respectent les banques préservées. Sur macOS et Windows, les appels système
de ces deux opérations évitent l'adaptateur qui sauve tous les temporaires.
Linux ARM64 conserve les syscalls mais bénéficie des résidences ; exécution
Linux non vérifiée ici. Liaison Windows couverte structurellement, sans run
Windows. X64 reste inchangé. Ce gain ne résout pas encore le déficit global
à 2 048 corps ; le binaire interactif public reste celui de `0c178bb`.
