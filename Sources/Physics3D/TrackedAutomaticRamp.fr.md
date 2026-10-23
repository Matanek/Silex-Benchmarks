# Chenilles : franchir une rampe avec la boîte automatique

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticRampRun.py --mode both
```

Deux recettes de 16 s à 60/120 Hz gardent le véhicule de `TrackedAutomatic.sx`
et comparent un plan à une rampe finie. Après 2 s de stabilisation, 4 s de gaz
à 80 % sont suivies de 10 s de freinage à 4 %. Le parcours sur rampe doit
montrer montée, perte des six appuis, vol, réception et arrêt. Le profil de
boîte reste 2/1.4/1, seuils 1800/1200 RPM, changement 0.5 s, engagement 0.3 s
et latence 0.5 s. Le moteur de 15 N·m, les suspensions et les bandes restent
ceux de la qualification sur plan.

La rampe est une boîte de 8 × 0.4 × 6.03 m centrée en (0, 0.1, 15), inclinée
de −0.1 rad autour de X, avec friction 1. Les points et normales des six rayons
doivent appartenir au plan ou au dessus fini de cette boîte. Le comparateur
recompose régime, rapports, embrayage, bandes et rotation des roues depuis les
observations de chaque moteur. Les bilans d’impulsion et les fenêtres de 1 s
d’efforts résultants, couples, charges normales et rotations sont contrôlés.

Les bornes du châssis restent 0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s.
Les séquences de rapports sont identiques entre moteurs ; leurs dates doivent
différer d’au plus 0.05 s. Une dernière vitesse peut être révisée après
l’intégration de pose sous contact : l’égalité d’intégration reste stricte en
vol. Le partage tangentiel individuel n’étant pas unique, sa parité n’est pas
annoncée. Les 114 champs et le schéma sont soumis à corruption.

Les bruts et le rapport vivent dans `.silex/physics3d-oracle/`. Une qualification
verte exige aussi des sorties Native Debug/Release identiques pour chaque
moteur. Elle porte sur ces deux recettes : pas de terrains généraux, maillons
articulés, contacts volumiques, rectitude prolongée ou performance déduite.
Les contrôles d’interdiction d’upshift de `TrackedAutomaticRun.py` restent
séparés ; être déjà au dernier rapport en vol ne prouve pas cette interdiction.
