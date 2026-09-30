# Admission régionale — Native ARM64

Base Silex `984c757`, physique `d955a1aec00a36ccdda8d2461801d5cc07a74f15`.
Candidat : seuil arithmétique régional 16 ; résultats de chargements mixtes
protégés localement au lieu d’une exclusion globale. macOS ARM64 Release,
bootstrap ReleaseFast, quatre paires A/B, B/A, A/B, B/A, priorité normale,
aucun build ni test concurrent. Médianes des moyennes par exécution :

| Charge | Base ms/pas | Candidat ms/pas | Variation |
|---|---:|---:|---:|
| AquariumFill | 7.345176 | 6.840655 | -6.87 % |
| ColumnPeak | 5.910902 | 5.971260 | +1.02 % |

Le bac gagne dans les quatre paires et dépasse la réduction requise de 1,5 %.
La colonne régresse légèrement, dans la limite préétablie de 3 %.
Les observables physiques CSV restent exactement égaux, sorties 0.
Aquarium 1 024 corps/1 800 pas ; colonne 256 corps/600 pas.

Validation : check, 216 tests sources, oracle 28 programmes et admission rapide
verts. Le nouveau test Machine a initialement omis deux champs obligatoires
d’une conversion ; après correction, les **791 tests unitaires** passent.
Les deux relances manuelles avec cwd/environnement incomplets sont exclues ;
preuve finale `regional-admission-units-final.log`, cwd Toolchain et cache Zig
isolé absolu comme le build officiel. Aucun défaut de comportement conservé.

Le déficit interactif reste ouvert. Gain mesuré sur macOS ARM64 uniquement ;
Linux ARM64 applicable mais non exécuté ici. X64 inchangé.
