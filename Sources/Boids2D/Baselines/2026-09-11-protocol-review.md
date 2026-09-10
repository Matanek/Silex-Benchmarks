# Qualification du protocole Boids du 11 septembre 2026

Le candidat instrument `bbfb56f51642c60954a3dac898d9b21eed49de90` passe
ses 16 tests, la syntaxe Bash et le smoke réel. Le portail
`zig build optimizer-admission-quick` et le build du compilateur
`09b7a5ffaa438e808f920a534fefb1ccabce20ac` passent depuis le worktree,
sans l'ancienne capsule. Les messages de couverture volontairement rouge dans
le journal des tests de l'oracle viennent de ses tests négatifs ; la commande
complète termine avec le code 0.

Les captures A et B utilisent les mêmes trois exécutables, shaders et 22
packages propres sur Apple M3 Pro, macOS 26.6.2, ARM64. Chaque capture conserve
54 processus : six tours d'échauffement puis douze tours mesurés, dans les six
permutations. Les charges restent 4 000 boids, 480 frames, delta 1/60 seconde,
fenêtre logique 960 × 640, pixels 1920 × 1280 et présentation immédiate.
Toutes les signatures sémantiques passent.

| Série | A : médiane | A : dérive | B : médiane | B : dérive |
|---|---:|---:|---:|---:|
| Silex | 88.272638 FPS | -1.4273% | 87.825050 FPS | +1.1280% |
| C++ architectural | 89.084505 FPS | -0.2493% | 89.039950 FPS | +0.0247% |
| C++ direct | 86.888255 FPS | -1.0688% | 86.792210 FPS | +0.2060% |
| Silex / C++ architectural | 0.991983 | -1.1754% | 0.987423 | +1.1021% |
| Silex / C++ direct | 1.015802 | -0.3570% | 1.012267 | +0.9202% |

Les deux captures sont **non concluantes** : la dérive Silex et celle du ratio
architectural dépassent 1 %. A dépasse aussi ce seuil pour le C++ direct ; B
échoue également sur le déplacement entre les demi-fenêtres du ratio
architectural (1.0154 %). Les médianes se répètent à moins de 1 %, mais ce fait
ne compense pas la non-stationnarité. Le comparateur retourne donc le code 2.
Les JSON donnent les valeurs exactes, les MAD, les étendues et toutes les séries.

L'ordre ne permet pas à lui seul d'attribuer la dérive : les médianes Silex
par position sont 88.475 / 88.340 / 88.159 FPS pour A, puis
87.735 / 88.020 / 88.198 FPS pour B. La tendance s'inverse entre captures ;
ces quatre échantillons par position ne prouvent aucune cause thermique,
aucun effet d'ordre stable ni aucune régression du compilateur.

Les empreintes de sceau des captures sont identiques :
`833c1f1045e22844176b7197cd0c0980caef763484a96a17a170eeddc1f619d9`.
Clang emploie `-O3 -DNDEBUG`, EnTT est épinglé à
`85c6bba014049b5de8fad49d25424df2f1f6a8c1`. La frontière existante est
explicitement différente : SDL 3.4.8 dynamique côté C++, SDL 3.4.10 avec
l'artefact Silex côté GFX. Les versions et empreintes sont conservées ; aucune
mise à jour de cette frontière n'a accompagné la mesure. Une comparaison de
consommateurs ne suffit donc pas à attribuer un petit écart au seul code produit.

Le contrôle historique `65471f1` et ses seuils restent inchangés. La Part 01
reste active : il manque deux captures stationnaires concordantes et
l'acceptation de la règle proposée. Avant une nouvelle campagne, contrôler les
charges concurrentes de l'hôte ; conserver les mêmes artefacts et la règle
entière. Ne pas supprimer des processus, déplacer la fenêtre ni élargir les
seuils pour obtenir un résultat vert. Aucun changement d'optimiseur n'est inclus.

## Reprise de la qualification

Un relevé ponctuel après la campagne montrait WindowServer à 42.6 % CPU et
trois processus Codex à 29.5 %, 25.8 % et 13.1 %. Il ne couvre pas la durée
des captures et ne démontre pas leur cause. Il motive une répétition depuis un
terminal externe pendant que les tâches Codex sont inactives, avec les mêmes
artefacts et sans changement de règle.

Depuis la racine SilexProject, lancer successivement ces commandes. Le runner
attend Entrée pour permettre d'arrêter les travaux concurrents avant la mesure.
Chaque fichier de sortie doit être nouveau ; conserver également ses fichiers
`.json` et `.seal.json`.

```sh
.specs/Silex-Optimization-Parity-Completion/Worktree/Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --skip-build --wait --build-dir /private/tmp/silex-parity-completion-boids --output /private/tmp/parity-repeat-c-boids.log
.specs/Silex-Optimization-Parity-Completion/Worktree/Silex-Benchmarks/Sources/Boids2D/RunComparison.sh --skip-build --wait --build-dir /private/tmp/silex-parity-completion-boids --output /private/tmp/parity-repeat-d-boids.log
python3 .specs/Silex-Optimization-Parity-Completion/Worktree/Silex-Benchmarks/Sources/Boids2D/Protocol.py compare /private/tmp/parity-repeat-c-boids.log /private/tmp/parity-repeat-d-boids.log
```

Résultat attendu : `stationary` pour chaque capture puis `repeatable` pour la
paire, avec code 0. Un code 2 conserve les données et bloque la qualification.
Les 1 % de dérive ne sont pas une marge de parité : ce sont une condition de
qualité des mesures. La règle proposée reste indépendante de toute modification
d'optimiseur et doit être acceptée selon le contrat de la Spec.
