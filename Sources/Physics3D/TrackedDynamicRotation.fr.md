# Mesurer la réaction d’une plateforme tournante de masse finie

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedDynamicRotationRun.py --mode both --stable-brakes
```

Sept parcours de 6 s à 60/120 Hz comparent le repos, les deux sens de rotation
sur une plateforme de 1000 kg puis de 200 kg, les bandes libres sur 200 kg et
un contrôle cinématique. Le châssis de 100 kg est décentré de 2,5 m. Les six
roues, suspensions, bandes et matériaux reprennent les autres témoins chenillés.
La plateforme mesure 8 × 0.4 × 12 m et repose sur un plan sans friction.

À 2 s, le support dynamique reçoit une impulsion angulaire `Iy × 0.5 N·m·s` ;
à 4 s, l’impulsion opposée retire le moment injecté. Les deux cas négatifs
inversent les signes. Aucune rotation ou vitesse n’est prescrite ensuite au
support dynamique, et aucune pose/vitesse n’est imposée au châssis. Le contrôle
cinématique reçoit au contraire 0.5 rad/s entre 2 et 4 s, puis zéro. Les freins
restent serrés, sauf sur le cas libre pendant le mouvement ; il freine à 4 s.
Les profils sont 48/4 pour les supports dynamiques et 12/4 pour le cinématique,
identiques entre moteurs et conservés depuis les recettes correspondantes.

Freins serrés, les deux corps partagent l’inertie de rotation. La vitesse commune
approche `L / (Iy_support + 100 + μ × 2.5²)`, avec `μ = 100M / (100 + M)`.
Le support léger ralentit davantage que le lourd ; la rotation imposée garde
sa vitesse. Les bandes libres permettent une vitesse relative et changent le
partage de mouvement. Le centre de masse horizontal total reste fixe malgré
le mouvement de chaque corps.

Le harnais contrôle le moment cinétique autour de Y avec l’inertie transformée
dans le monde et les termes orbitaux `r × mv`. Les réactions roues/support
sont opposées au même point. Le sol peut exercer une force verticale et des
couples X/Z, mais aucune force horizontale ni couple Y. Les bilans par pas,
la quantité de mouvement, le centre de masse, la géométrie des contacts, les
rotors, les miroirs et le repos final sont des contre-épreuves indépendantes
à la comparaison Jolt. La dernière seconde exige six appuis et 981 ± 2 N.

Budgets fixés avant observation : parité des deux corps 0.05 m / 0.1 m/s /
0.02 rad / 0.15 rad/s ; miroir 0.005 m / 0.02 m/s / 0.005 rad / 0.02 rad/s ;
impulsions par pas 0.1 N·s ou N·m·s ; quantité de mouvement horizontale totale
0.1 N·s, moment cinétique Y total 0.5 N·m·s et centre de masse 0.001 m.
La vitesse relative freinée reste sous 0.05 m/s, le partage analytique sous
0.03 rad/s d’écart. Les fenêtres d’efforts gardent 20 N / 30 N·m / 20 N / 0.1 rad.
Le schéma de 127 valeurs et les branches sont protégés par 146 corruptions
par moteur/mode. Native Debug/Release doivent être byte-identiques.

L’option obligatoire `--stable-brakes` identifie explicitement la copie du
contrôleur Jolt aux bornes statiques symétriques. Sources et bibliothèques
originales restent intactes ; delta, empreintes et liaison sont consignés.
Traces et rapport sont séparés sous `.silex/physics3d-oracle/` avec le préfixe
`tracked-dynamic-rotation-stable-brakes` et la fixture `tracked-dynamic-rotation-v1`.
Aucune autre adaptation de Jolt n’intervient dans cette campagne.

Cette preuve concerne les masses, géométries, impulsions et contacts rayon
fixés. Elle ne qualifie ni les terrains arbitraires, ni les grands basculements
libres, ni une campagne générale de véhicules. Aucun gain CPU/FPS revendiqué.
Voir aussi [la translation de masse finie](TrackedDynamicPlatform.fr.md) et
[le support à rotation imposée](TrackedRotatingPlatform.fr.md).
