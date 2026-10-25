# Chenilles sur un support de masse finie

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedDynamicPlatformRun.py --mode both
```

Six parcours de 6 s à 60/120 Hz comparent le repos, une impulsion latérale
avec frein, puis une impulsion longitudinale avec frein ou bandes libres.
Ces deux derniers cas sont répétés avec une plateforme plus légère. La boîte
mesure 8 × 0.4 × 12 m, pèse 1000 ou 200 kg et repose sur un plan sans frottement.
Une impulsion centrale de +2M N·s à 2 s, puis −2M à 4 s, la met en mouvement.
Ni sa vitesse ni sa pose ne sont imposées. Le châssis de 100 kg reste au point
mort ; les six suspensions et les bandes échangent leurs efforts avec le support.

Freins serrés, la vitesse stationnaire commune vaut `2M / (M + 100)`.
Bandes libres, avec `K = 4 / 0.3²`, le support atteint
`U = 2M / (M + 100K / (100 + K))` et le véhicule `v = KU / (100 + K)`.
Le support ralentit donc sous la réaction du véhicule. La quantité de mouvement
horizontale totale et le déplacement du barycentre fournissent deux contrôles
indépendants de la comparaison entre moteurs.

Le profil emploie explicitement 48 itérations de vitesse par phase et 4 de
position dans les deux moteurs. Le défaut SDK reste 12. L'étude 12/24/48
conserve le même protocole et les mêmes budgets : les profils 12 et 24 dépassent
ponctuellement 0.1 m/s d'écart ; seul 48 satisfait cette qualification.
Cela ne prouve pas une convergence monotone ni les performances d'une scène.

Les bornes point par point du châssis et du support restent
0.05 m / 0.1 m/s / 0.02 rad / 0.15 rad/s. Les bilans d'impulsion sont bornés
à 0.1 N·s ou N·m·s, la dérive du barycentre à 0.001 m et le bilan des bandes
libres à 0.002 N·m·s. Les contacts sont vérifiés dans le repère réel du support.
Des fenêtres de 1 s comparent efforts, couples, charges et rotations.
Les 127 valeurs et le schéma sont soumis à 152 corruptions par moteur.
Une qualification verte exige aussi des sorties Native Debug/Release identiques.
Bruts et rapport vivent dans `.silex/physics3d-oracle/`.

Cette preuve couvre ces impulsions horizontales, deux masses et les contacts
rayon sur cette boîte. Les supports rotatifs généraux, la conduite prolongée,
les impacts généraux et les autres plateformes d'exécution restent à qualifier.
Voir aussi le [support à vitesse imposée](TrackedPlatform.fr.md).
