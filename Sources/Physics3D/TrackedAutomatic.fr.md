# Chenilles : passages automatiques au sol

Depuis la racine du workspace (ou du groupe Worktree de la Spec) :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticRun.py --mode both
```

Quatre recettes de16s à60/120Hz comparent Jolt épinglé au consommateur public
Silex : accélération avant et arrière, bandes opposées sur appuis sans
adhérence, puis bandes en vol sans gravité. Après2s de stabilisation,4s de gaz
à80% sont suivies de10s de freinage modéré à4%. Les deux premiers cas doivent
passer1/2/3 puis2/1/point mort, avec signe inverse en marche arrière. Les deux
contrôles doivent dépasser le seuil de régime en restant au premier rapport.

Le véhicule reprend100kg/inerties100, six roues de.3m, bandes d’inertie2 et
différentiel6, moteur15Nm, suspensions10000/1000 et rayons sur plan. Les
rapports sont2/1.4/1 et−2/−1.4/−1 ; seuils1800/1200RPM, ralenti1000RPM,
maximum6000RPM, changement.5s, engagement.3s et latence.5s. Le contrôle de
contre-rotation supprime les frottements tangentiels ; il isole la condition
de boîte, sans qualifier un pivot chargé prolongé.

Le comparateur recompose régime et automate d’embrayage à chaque pas depuis
les observations de chaque moteur ; il contrôle bandes, angles de roue,
géométrie des rayons, impulsions, capacité de friction et repos. Les séquences
de rapports sont identiques et leurs dates doivent différer d’au plus.05s.
Les bornes châssis restent.05m/.1m/s/.02rad/.15rad/s ; efforts résultants,
couples, charges normales et rotations se comparent sur fenêtres1s. Les efforts
tangentiels individuels ne sont pas uniques et leur parité n’est pas annoncée.
Les114champs sont soumis à corruption, avec gardes de schéma et valeurs finies.

Les sorties et le rapport sont écrits dans `.silex/physics3d-oracle/`. Une
qualification verte porte sur ces recettes, avec sorties Native Debug/Release
identiques ; elle ne qualifie ni conduite automatique sur rampe, ni chenilles
à maillons, ni terrains généraux. Aucun budget de performance n’en découle.
