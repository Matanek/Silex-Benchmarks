# Vérifier les parcours chenillés avec une friction statique symétrique

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedBrakeCorpusRun.py --mode both --stable-brakes
```

Cette campagne requalifie les sept parcours de contacts chenillés existants :
conduite au sol, rampe, boîte automatique, boîte automatique sur rampe,
support cinématique en translation, support de masse finie et support tournant.
Elle réutilise leurs programmes, géométries, commandes, durées, fréquences,
qualifications, miroirs, corruptions et comparateurs. Le profil est12/4,
sauf le support de masse finie qui conserve48/4. Native Debug/Release doivent
produire des traces identiques par moteur. Le contrôle de hauteur perturbée
au sol est également conservé. Les parcours en vol sans contact ne sollicitent
pas cette branche de friction et gardent leur qualification originale.

L’option obligatoire `--stable-brakes` identifie une variante du Jolt épinglé :
une copie du seul `TrackedVehicleController.cpp` borne l’impulsion accumulée
des bandes bloquées dans les deux sens. La capacité reste `min(frein, friction)`.
Les couples, contacts, bandes libres et solveur restent identiques. La source
originale est vérifiée par empreinte ; l’archive et les bibliothèques restent
intactes. La copie est liée avant l’archive originale, avec provenance complète.
Aucun ancien résultat original n’est remplacé ni renommé en résultat adapté.

Les traces et le rapport utilisent `tracked-brake-corpus-*-stable-brakes-*`
sous `.silex/physics3d-oracle/`. Le rapport identifie les deux sources, le delta,
les bibliothèques et binaires par empreinte, ainsi que la commande de liaison.
Les harnais historiques gardent leur oracle original. Le nouveau
[transport combiné](TrackedRotatingPlatform.fr.md#combiner-translation-et-rotation)
employant cette variante complète la campagne avec les lois centripètes et
le glissement relatif mesurés indépendamment de l’autre moteur.

Cette campagne ne qualifie pas les terrains arbitraires, les supports de masse
finie en rotation générale ni la rectitude sur un trajet prolongé. Aucun gain
CPU/FPS n’est revendiqué et aucun binaire consommateur ne lie Jolt.
