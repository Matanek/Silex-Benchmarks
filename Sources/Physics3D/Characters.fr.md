# Qualifier les deux modes de personnages

Depuis la racine du workspace ou du groupe Worktree de la Spec :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/CharacterRun.py --mode both
```

Les six scénarios fixes de `CharacterFixture.json` ont les mêmes entrées dans
`Characters.sx` et `CharacterOracle.cpp`. Leur empreinte interdit de modifier
silencieusement le JSON sans adapter les deux consommateurs. Le comparateur
rejette valeurs absentes, dupliquées, non finies et perturbations au-delà des
seuils. `--self-test` vérifie ces rejets sans compilation.

Une capsule de rayon 0,3 m et demi-partie cylindrique de 0,55 m pousse une sphère
de 10 kg, faiblement puis avec une force plafonnée à 100 N sur 0,1 s. Les vitesses
attendues sont 0,009 et 1 m/s, sans rotation pour ce contact central. La masse
virtuelle de 70 kg transmet ensuite son poids à un support de 10 kg pendant
1/60 s, soit −1,1445 m/s. Une vitesse descendante de 0,3 m/s établit le contact
effectif du premier pas dans les deux moteurs ; la gravité reste une entrée
explicite du contrôleur virtuel.

Le personnage physique de 70 kg rencontre une sphère de 30 kg : la collision
inélastique centrale à 1 m/s donne 0,7 m/s aux deux corps, avec rotations bloquées
du personnage. Chute et repos durent 180 pas à 120 Hz. Enfin le personnage
accroupi refuse de se redresser sous un plafond, puis conserve ses pieds et sa
masse lorsque le plafond disparaît. L’adaptation Jolt calcule elle aussi le
centre proposé pour conserver les pieds et restaure la pose après un refus.

Quatorze observables sont comparées à Jolt 5.6.0 épinglé et aux bilans analytiques.
Les tolérances absolues sont 0,0001, sauf les mesures de repos à 0,005. Les
dimensions sont SI. Les deux moteurs emploient 12/4 itérations ; Jolt utilise
un slop de 0,001 m et un padding virtuel de 0,002 m. Amortissement et restitution
sont nuls. Aucune tolérance n’est élargie après observation.

Le lanceur vérifie l’archive Jolt, réutilise les bibliothèques Debug/Release de
son cache lorsqu’elles existent, contrôle leur configuration et enregistre leur
empreinte. Sur cache vide, le helper construit Jolt avec un seul worker.
Le rapport et les exécutables vivent dans `.silex/physics3d-oracle/`.
Cette qualification porte sur macOS ARM64 Native Debug/Release exécutés.
Les rencontres entre personnages, les supports mobiles, filtres, durées de vie,+pentes et marches sont également vérifiés dans les consommateurs de GFX.Physics ;
ce protocole ne prétend pas comparer leurs trajectoires chaotiques complètes.
