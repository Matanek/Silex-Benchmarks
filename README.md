# Silex Benchmarks

`Silex-Benchmarks` rassemble les charges de performance publiques de Silex et
de ses packages. Le dépôt conserve ensemble chaque scénario, son protocole, ses
témoins externes et ses résultats bruts lorsqu'ils existent.

## Organisation

Tous les benchmarks Silex vivent sous [`Sources/`](Sources/). Ils ne sont pas
classés par package : leur nom décrit directement la charge mesurée.

Un benchmark autonome reste un fichier direct :

```text
Sources/RetainedCanvasGeometry.sx
Sources/RegexStreamingSearch.sx
Sources/UpdatingTextLayers2D.sx
```

Un benchmark reçoit un dossier uniquement lorsqu'il possède plusieurs
artefacts : sources volumineuses, assets, témoin C++, runner, checker ou
baselines. Les baselines restent toujours avec le benchmark qui les produit :

```text
Sources/Boids2D/
├── Silex.sx
├── Cpp/
├── RunComparison.sh
└── Baselines/
```

Le fichier [`Package.json`](Package.json) définit `Sources` comme racine du
package et déclare toutes les dépendances nécessaires au catalogue.

## Catalogue

| Benchmark | Objectif |
| --- | --- |
| `Boids2D/` | comparer le parcours public Scene2D/ECS/GPU à deux témoins C++23 |
| `FallingBodies2D/` | charger conjointement la physique 2D, le transfert des transformations et le rendu |
| `WorldRendering3D/` | mesurer un monde 3D instancié selon plusieurs profils GPU et présentation |
| `PhysicsWorldScale2D.sx` | mesurer mouvements épars et pile de corps à plusieurs échelles |
| `RetainedCanvasGeometry.sx` | compiler une géométrie Canvas retenue dense |
| `UpdatingTextLayers2D.sx` | mettre à jour des couches de texte retenues |
| `RetainedUIInteraction.sx` | mesurer layout, sélection, snapshot et rasterisation UI |
| `TerminalScreenRendering.sx` | mesurer le rendu d'un écran terminal complet et ses mises à jour |
| `WebViewBridgeRoundTrips/` | exercer 1 000 messages aller-retour avec une WebView |
| `RegexStreamingSearch.sx` | rechercher en flux dans un million de scalaires Unicode |
| `NetworkFreshnessTracking.sx` | mesurer les comparaisons et trackers de fraîcheur réseau |

## Exécution

Les mesures sont réalisées après compilation en Release. Une exécution Debug
sert uniquement à vérifier la correction et ne constitue pas un résultat de
performance.

Depuis la racine du workspace :

```sh
silex run Silex-Benchmarks/Sources/PhysicsWorldScale2D.sx --release
silex compile Silex-Benchmarks/Sources/FallingBodies2D/Main.sx --release -o /tmp/falling-bodies-2d
/tmp/falling-bodies-2d --smoke --immediate --no-panel
silex compile Silex-Benchmarks/Sources/WorldRendering3D/Main.sx --release -o /tmp/world-rendering-3d
(cd Silex-Benchmarks/Sources/WorldRendering3D && /tmp/world-rendering-3d --benchmark)
```

Les campagnes qui comparent plusieurs exécutables décrivent leur protocole
dans leur propre `README.md`. Elles doivent conserver les sorties brutes, le
nombre de répétitions, la variance, le mode de compilation, l'OS et
l'architecture ; une baseline locale n'est jamais une promesse portable.

`Boids2D/Silex.sx` est une copie fidèle du témoin historique : son algorithme,
ses constantes et sa fenêtre de mesure ne sont pas reformulés lors de la
migration. `FallingBodies2D` conserve de la même façon son spawn, son ordonnanceur
asynchrone, ses buffers et ses options ; seuls les diagnostics réservés à
`GFX.Physics` ont été retirés afin que le benchmark reste un véritable
consommateur public. Toute évolution future de ces charges exige une nouvelle
baseline et une justification explicite.

Les benchmarks de l'optimiseur et du backend restent sous
`Silex/Toolchain/Benchmarks/` : ils constituent des gates internes de la
toolchain plutôt que des campagnes publiques de packages.

Les corpus qui inspectent volontairement des détails `package` restent eux
aussi chez leur propriétaire. C'est notamment le cas de l'oracle Box2D, des
profils fins du solveur dans `GFX.Physics` et de la garde d'allocation du pool
de workers dans `STD` : ils vérifient une implémentation, alors que les
scénarios de ce dépôt franchissent une vraie frontière de package.
