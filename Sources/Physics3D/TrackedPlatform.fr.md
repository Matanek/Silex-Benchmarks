# Chenilles sur une plateforme mobile

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedPlatformRun.py --mode both
```

Quatre parcours de 6 s à 60/120 Hz comparent un support immobile, une translation
latérale freinée, une translation longitudinale freinée et un roulement
longitudinal libre. La plateforme cinématique de 8 × 0.4 × 12 m part du centre
(0, −0.2, 0), se déplace à 2 m/s entre 2 et 4 s, puis s'arrête. Le véhicule
reste dynamique ; aucun déplacement de châssis ne lui est imposé.

Le profil automatique de `TrackedAutomaticRamp.sx` reste au point mort, sans gaz.
Les freins sont serrés à 100 %, sauf dans le quatrième cas. Les deux bandes
ont chacune une inertie de 2 kg·m² et des roues de rayon 0.3 m, pour un châssis
de 100 kg. En roulement libre stationnaire, la contre-épreuve donne
`v = 2 × 4 / (100 × 0.3² + 4) = 0.6153846 m/s`, au lieu des 2 m/s de la
plateforme. Les bandes tournent alors en sens inverse du déplacement relatif.

Le comparateur recompose le mouvement cinématique, les contacts sur le dessus
fini, les bilans d'impulsion du châssis et des bandes libres, les rotations,
la capacité de friction et le retour au repos sur six appuis. Les bornes du
châssis restent 0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s. Les bilans par pas
sont bornés à 0.1 N·s et 0.1 N·m·s, les rotations à 1e−4 rad et la réponse
cinématique à 1e−4 m / m/s. Des fenêtres de 1 s comparent efforts résultants,
couples, charges et rotations ; le partage tangentiel individuel n'est pas
annoncé identique. Les 127 champs et le schéma sont soumis à corruption.

Une qualification verte exige des sorties Native Debug/Release identiques
pour chaque moteur. Bruts et rapport vivent dans `.silex/physics3d-oracle/`.
Cette preuve couvre des translations horizontales et des contacts rayon sur
cette boîte ; elle ne prouve ni supports dynamiques ou rotatifs, ni terrain
général, ni performance, ni rectitude sur les parcours prolongés.
