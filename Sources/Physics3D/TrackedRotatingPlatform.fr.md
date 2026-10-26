# Transporter un véhicule chenillé sur une plateforme tournante

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedRotatingPlatformRun.py --mode both
```

Quatre parcours de 6 s à 60/120 Hz comparent le repos, une rotation autour de
+Y et de −Y avec freins serrés, puis la rotation +Y avec bandes libres. Le
support cinématique mesure 8 × 0.4 × 12 m et garde son centre en (0, −0.2, 0).
Sa vitesse angulaire vaut ±0.25 rad/s entre 2 et 4 s, puis zéro ; son angle
final vaut ±0.5 rad. Le châssis part en (1, 1.15, 0), décentré du pivot.
Aucune pose ou vitesse de châssis n'est imposée pendant la simulation.

Le véhicule conserve les six rayons, le châssis de 100 kg, les bandes d'inertie
2 kg·m² et le profil au point mort du support en translation. Les freins valent
1500 N·m par bande, sauf dans le cas libre. Le profil reste à 12 itérations de
vitesse et 4 de position dans les deux moteurs.

Freins serrés, la vitesse du châssis doit rejoindre la vitesse du support à
son centre : `ω × (position_châssis − position_support)`. Le lacet doit suivre
la rotation du support. Les bandes libres tournent et permettent un mouvement
relatif ; elles ne doivent pas se confondre avec les freins bloqués. La symétrie
des deux sens constitue une contre-épreuve indépendante de Jolt.

Le comparateur garde 0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s pour la parité
châssis ; le mouvement prescrit du support est vérifié à 1e−4. Le miroir est
borné à 0.005 m / 0.02 m/s / 0.005 rad / 0.02 rad/s. Les bilans par pas restent
à 0.1 N·s ou N·m·s, les bandes libres à 0.002 N·m·s. Géométrie, intégration des
roues et contacts dans le repère tourné sont vérifiés. Les fenêtres de 1 s
comparent forces, couples, charges et rotations. La dernière seconde exige
six appuis, 981 ± 2 N et le retour au repos.

Les 127 valeurs et le schéma sont soumis à 143 corruptions, y compris les
branches libre, immobile et miroir. Une qualification verte exige des traces
Native Debug/Release identiques. Bruts et rapport sont écrits sous
`.silex/physics3d-oracle/`.

L'étude préalable à 12/24/48/96 a isolé une asymétrie de friction statique près
de l'arrêt. Des tours supplémentaires ne la supprimaient pas. Les roues
verrouillées bornent désormais leur impulsion cumulée dans les deux sens ;
la capacité d'adhérence et le couple maximal restent identiques. Avec une ellipse
d'adhérence combinée, les deux composantes candidates sont appliquées ensemble,
y compris lorsque le candidat est déjà à l'intérieur. Le test SDK
miroir réduit distingue cette correction d'une simple hausse d'itérations.

Cette preuve porte sur ce support cinématique, ces vitesses et ces rayons.
La rotation dynamique générale, les terrains généraux et la rectitude prolongée
restent à qualifier. Voir aussi le [support de masse finie](TrackedDynamicPlatform.fr.md).

## Combiner translation et rotation

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedRotatingPlatformRun.py --mode both --combined --stable-brakes
```

Cette variante ajoute ±2 m/s le long de Z aux rotations ±0.25 rad/s autour de Y,
entre2 et4s. Le support se trouve finalement en(0,−0.2,±4), tourné de±0.5rad.
Le contrôle0 reste immobile. Le cas3 libère les bandes seulement pendant le
mouvement2..4s et serre explicitement les freins à partir de4s pour éprouver
l'arrêt. Sans drapeau, le cas3 historique reste libre tout au long du parcours.
Les deux moteurs reçoivent exactement la même recette par variante.

La vitesse attendue au centre du châssis combine les deux termes :
`v_support + ω_support × (position_châssis − position_support)`.
Les points de contact sont contrôlés dans le repère translaté et tourné du
support au début du pas. Les bilans d'impulsion du châssis restent exprimés dans
le monde. Miroir, freins/roulement, fenêtres de forces et retour au repos gardent
les seuils ci-dessus ; aucun budget n'est augmenté pour cette composition.

Le préfixe et l'identité de fixture deviennent `tracked-combined-platform-v1`
(le préfixe brut omet `-v1`). Traces et rapport restent séparés, sous
`.silex/physics3d-oracle/tracked-combined-platform-*`. Schéma et comparateurs sont
partagés avec la rotation seule, sans seconde copie de la physique. La commande utilise explicitement la variante `--stable-brakes` : une copie
du seul bloc de bornes de friction des chenilles bloquées conserve une plage
symétrique pour l’impulsion accumulée. Capacités, couples et branche libre
restent identiques. L’archive, le contrôleur et les bibliothèques originaux
restent intacts ; le rapport consigne delta, empreintes et liaison. Sans ce
drapeau, la référence reste originale et son miroir combiné échoue à l’arrêt.
Les sorties de la variante portent le suffixe `-stable-brakes`, séparé des
résultats originaux. L’adaptation des petits angles moto n’intervient pas.
Cette variante qualifie la composition cinématique fixée, sans revendiquer
la rotation des supports de masse finie ou les terrains arbitraires.

Le contrôle analytique ne prend pas l’autre moteur pour cible : en régime
adhérent, la somme des efforts horizontaux vaut en moyenne
`100 · ω × (ω × r)` à2N près, la charge981N à2N près et le couple moyen reste
sous2Nm. Il vérifie également la vitesse relative en chaque contact et les
bandes bloquées. Le [corpus des freins](TrackedBrakeCorpus.fr.md) exerce les
parcours antérieurs avec la même variante explicite.
