# Comparer les motos avec des petits angles précis

Les parcours moto proposent une variante explicite du contrôleur Jolt 5.6.0
épinglé à `e77f175595e64cb44218cc9d9d56fc365ad0e36a`. Elle remplace uniquement
les trois magnitudes d'angle `acos(target·up)` par
`atan2(|target×up|, target·up)`, avec le signe original. Cette formulation
équivalente conserve les très petits angles lorsque le produit scalaire en
simple précision arrondit à 1. Gains, physique, commandes et tolérances restent
ceux des témoins existants.

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleLeanOracleCheck.py
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleHandlingRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleDrivingRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleRampRun.py --mode both --stable-lean
python3 Silex-Benchmarks/Sources/Physics3D/MotorcycleCrossRun.py --mode both --stable-lean
```

Sans `--stable-lean`, les quatre harnais utilisent toujours le contrôleur
original. Avec ce drapeau, les traces et rapports portent `stable-lean` dans
leur nom, sous `.silex/physics3d-oracle/`. Les rapports distinguent la variante,
les empreintes des sources et binaires originaux/adaptés, les trois substitutions
et la commande de liaison. Les comparateurs, scénarios et durées ne changent pas.

L'archive Jolt et ses sources restent vérifiées et intactes. Le harnais écrit
une copie du seul contrôleur dans le cache, conserve sa notice MIT et son
delta, puis lie cet objet avant la bibliothèque Jolt originale. Une source dont
l'empreinte diffère de la révision attendue ou un nombre de substitutions
incorrect provoque un échec. Le moteur Silex et les applications distribuées
ne lient aucune bibliothèque Jolt.

Le contrôle analytique applique une inclinaison de ±1e−5/±1e−4 rad, à 60/120 Hz,
à une moto sur des appuis sans frottement. La différence entre assistance active
et coupée doit suivre `−raideur × angle / inertie` sur le premier pas. Le témoin
original conserve sa zone morte ; la variante doit retrouver cette réponse avec
la tolérance analytique de 5 %. Les sorties Debug/Release doivent être identiques.
Le test consommateur SDK `MotorcycleSmallLean3D.sx` vérifie séparément la même
loi physique sur Silex.

Le contrôleur original peut produire une dérive latérale sur un parcours
symétrique sans direction : une comparaison spatiale stricte avec Silex peut
alors échouer malgré des bilans valides. Conserver ces résultats originaux ;
ne pas les présenter comme une réussite ni agrandir les tolérances pour
masquer l'écart. La variante est une adaptation numérique identifiée de l'oracle,
pas un résultat du contrôleur original. Elle ne qualifie aucun terrain ou
régime de conduite supplémentaire.
