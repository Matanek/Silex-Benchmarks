# Chenilles : franchir une rampe finie

Depuis la racine du workspace (ou le groupe Worktree de la Spec), exécuter :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedRampRun.py --mode both
```

Le témoin conserve le véhicule manuel à six roues de `TrackedGround.sx` et
compare le sol plat à une boîte inclinée finie. Après2s de réception,5s à80%
de gaz et7s de freinage à4%, les six appuis sont retrouvés au repos. Le frein
modéré isole l’obstacle : le freinage maximal depuis environ58km/h bascule
dans Jolt à120Hz et n’est pas qualifié par cette recette.

Le comparateur contrôle positions/vitesses, bilans linéaires/angulaires,
géométrie des rayons d’appui, vitesse/rotation des bandes, régime moteur et
fenêtres de résultantes et charges. L’intégration de position est contrôlée
exactement en vol ; sous contact, les solveurs peuvent encore corriger la
vitesse après l’intégration de pose. Les sorties brutes et le rapport vivent
dans `.silex/physics3d-oracle/`.

Ce parcours ne qualifie ni maillons articulés, ni contacts volumiques de
chenille, ni boîte automatique au sol, ni terrains généraux.
