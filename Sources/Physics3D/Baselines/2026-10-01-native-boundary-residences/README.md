# Résolution des frontières avant allocation — Native ARM64

Base Silex `f0123b883e6674a2b3eb16806cab6944ee396da1`, candidat
`6b825efed709036ebc51703159701e08c9c31cd5` ; physique
`d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
macOS ARM64 Release, bootstrap ReleaseFast. Quatre paires A/B, B/A, A/B, B/A,
priorité normale, aucun build ni test concurrent. Médianes des moyennes :

| Charge | Base ms/pas | Candidat ms/pas | Variation |
|---|---:|---:|---:|
| AquariumFill | 6.301861 | 6.035111 | -4.23 % |
| ColumnPeak | 5.646577 | 5.075593 | -10.11 % |

Les observables physiques sont exactement égaux dans les seize exécutions,
toutes terminées avec code 0. Aquarium : 1 024 corps / 1 800 pas ; colonne :
256 corps / 600 pas. Les critères préétablis sont satisfaits : quatre paires
Aquarium améliorées, gain médian >1,5 %, régression colonne ≤3 %.

`check test -Doptimize=Debug` passe (code 0). Le test Lower complet vérifie
qu'un vrai sqrt système peut garder son argument en registre et produire une
instruction matérielle, tandis qu'un homonyme privé reste un appel opaque.
Une première fixture utilisait une bibliothèque inconnue sans son attribut
package_private et était donc invalide ; elle a été corrigée avant validation.

L'allocation anticipée avec des signatures vides empêchait la seconde passe
de réexaminer les fonctions déjà colorées. Les fonctions avec external_call
attendent désormais les métadonnées. Les autres conservent le chemin parallèle.
Le cache exclut déjà les boundary_call, donc aucun ancien corps coloré de ce
type n'est réutilisé.

Linux et Windows ARM64 concernés, sans exécution sur ces hôtes ici. X64 reste
inchangé. Ce résultat ne prouve pas encore l'objectif interactif de 120 FPS.

## Contrôle interactif à 2 048 corps

Scène Native du candidat puis contrôle LLVM inchangé, 70 secondes chacun,
présentation immédiate Metal, priorité normale ; aucun build/test concurrent.
Médianes sur les secondes pleines après remplissage, tous les corps éveillés :

| Mesure | Native | LLVM |
|---|---:|---:|
| fps | 13.792 | 105.868 |
| ms_step | 17.752 | 9.246 |
| steps_s | 55.169 | 59.855 |
| physics_ms_frame | 71.006 | 5.233 |

Ce contrôle confirme que l'objectif n'est pas atteint : Native dépasse encore
le budget du pas et sature le rattrapage. Les variations thermiques/système
interdisent de déduire un pourcentage strict en comparant ce passage aux runs
interactifs des sessions précédentes. Les mesures A/B fixes ci-dessus restent
la preuve d'admission des changements. Détails et hashes dans `scene-2048/`.
