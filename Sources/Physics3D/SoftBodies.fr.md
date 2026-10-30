# Qualification des corps souples 3D

Comparer les contraintes indépendantes avant les scènes composées. La
référence est Jolt 5.6.0 au commit
`e77f175595e64cb44218cc9d9d56fc365ad0e36a`, avec huit sous-pas, sans sommeil.
`SoftBodyOracle.cpp` utilise les archives Jolt du protocole Physics3D existant ;
aucune bibliothèque physique étrangère n’est intégrée au package Silex.

## Corpus et seuils

Les cinq primitives sont distance souple, volume tétraédrique, flexion dièdre,
pression et attache de longue portée. Après douze pas à 60 Hz sans gravité ni
amortissement, positions et vitesses sont comparées avec une erreur absolue
maximale de 0,0002. La flexion accepte 0,002 : Jolt utilise un acos approché.
Les paramètres et les indices sont identiques ; aucun réglage ne dépend des
résultats mesurés.

Un cube tétraédrique sur plan, un tissu suspendu et un tissu drapé sur sphère
vérifient ensuite des invariants physiques communs : volume relatif entre
0,9 et 1,1 pour le cube, étirement inférieur à 1,2, pénétration des sommets
inférieure à 0,0001 m et mouvement descendant des tissus. Le volume calculé
sur une surface ouverte n’a pas de sens physique et n’est pas comparé.
Jolt réordonne les contraintes avec `Optimize` ; la qualification n’exige pas
une trajectoire identique des tissus entre solveurs.

Le consommateur public Silex vérifie aussi ancrages mobiles, destruction du
rigide attaché, pose partielle et butée arrière, transfert de quantité de
mouvement, snapshots, pause et géométrie Scene3D révisée, ainsi que 256 instances
à un/quatre workers avec égalité exacte des positions et vitesses à chaque pas.
Le programme est répété et ses observations doivent rester identiques.
Dix entrées invalides contrôlent indices, masses, triangles, tétraèdres,
pression, rayon, possession, pose, ancrage et référence périmée.

Les cinq tests de `SoftBodyContacts3D.sx` complètent ce corpus : impact
excentré et inertie, bilan du couple de friction, filtres/capteurs/désactivation,
sommet rapide sur paroi mince et collecte déterministe d’impulsions vers un
même rigide. La pose partielle est également vérifiée sur un tissu connecté :
sommets guidés mobiles, sommets libres sous gravité, puis retrait du guidage.

## Exécuter les binaires qualifiés

Depuis la racine SilexProject, ou la racine du groupe Worktree d’une Spec :

```sh
silex compile Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodies3D.sx --backend native --debug -o /private/tmp/soft-body-silex-debug
silex compile Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodies3D.sx --backend native --release -o /private/tmp/soft-body-silex-release
silex test Packages/GFX.Physics/Tests/Consumer/Tests/SoftBodyContacts3D.sx --backend native
```

Construire les oracles Debug/Release avec la configuration et l’archive
épinglées décrites dans le [protocole Physics3D](README.md), en passant
`SoftBodyOracle.cpp` au helper `build_oracle` de `Run.py`. Puis :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/VerifySoftBodies.py --silex /private/tmp/soft-body-silex-debug --jolt /private/tmp/soft-body-oracle-debug --mode Debug --output /private/tmp/soft-bodies-debug.json
python3 Silex-Benchmarks/Sources/Physics3D/VerifySoftBodies.py --silex /private/tmp/soft-body-silex-release --jolt /private/tmp/soft-body-oracle-release --mode Release --output /private/tmp/soft-bodies-release.json
```

Les rapports conservent les sorties, codes de retour, erreurs numériques,
configuration, plateforme et empreintes des binaires. Ils établissent la
correction de ces parcours, sans revendication de gain de vitesse, de 60 FPS,
de collision souple/souple ou d’auto-collision.

## Surfaces et contrôle négatif du CCD

Les contrôles additionnels de l’oracle vérifient la sortie d’un convexe et la
récupération d’une pénétration arrière peu profonde sur triangle/maillage.
Le témoin isolé d’un seul sommet à 120 m/s, un pas de 1/60 s et un sous-pas
traverse le triangle dans le Jolt original, dans les deux configurations.
Ce résultat est conservé comme limite du témoin de référence, sans modification
de Jolt ni élargissement d’une tolérance. Silex conserve sa protection CCD
explicite : arrivée depuis l’avant arrêtée à +0,03 m ; traversée depuis l’arrière
laissée libre. Les tests analytiques de surface valident ces deux cas.
