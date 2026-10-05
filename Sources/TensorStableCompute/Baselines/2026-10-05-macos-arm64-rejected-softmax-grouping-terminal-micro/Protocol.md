# Task39B — protocole scellé de l’achèvement terminal

## Hypothèse et portée

Après les corrections de construction et de buffers prêtes, quatre soumissions/fences sur cinq peuvent rester évitables dans une composition softmax fermée. Explication concurrente : domination du kernel, coût du token et rétention obligatoire des intermédiaires. Conserver le regroupement uniquement avec un bénéfice admis, résultats et gradients inchangés. Le nombre de soumissions seul n’est pas une mesure d’accélération.

Token privé transmis explicitement aux cinq passes ; nouvelle passe à chaque dépendance. Mêmes shaders, arithmétique et ordre. Aucun graphe de capture, callback, transfert caché, pool de fences, ni surface publique. Le token ne possède aucun résultat/parent/ProfileState. Après la première attente réussie, il libère la fence et reste achevé : les autres owners ne réattendent pas. La sonde indépendante a compté cinq attentes avant et une après, avec les mêmes ressources finales. Les cinq stockages possèdent la fence partagée ; recyclage après achèvement uniquement. Snapshot/reset neutres et cache prêt limité à 32 buffers/1 MiB demandés par device.

## Configuration figée

Baseline Tensor `7d91f411c70caa12e0f2bf4ebdf388abfe1ab1bd`. Compilateur direct Silex `d0834c70`, même exécutable dans les deux bras, SHA256 `9b5ceb5e1a951bb8a92190d690ed68a0b85ddb1c577b302c539f42dbc21e833c`. Permutation temporaire des seuls `@Storage.sx`, `@Tensor.sx`, `@Neural.sx` restaurée dans finally à l’octet, sans mouvement de HEAD ni changement des liens utilisateur. Compilation depuis Worktree et son unique cache.

Deux sources identiques dans les deux bras : `SoftmaxGrouping.sx` et `ResidentSteps.sx`. Binaries Debug/Release qualifiés avant mesure ; corpus positif complet et tests publics spécifiques Debug/Release obligatoires avant admission/intégration. Aucun build/test simultané aux mesures. Capturer chaque empreinte et les HEADs, statut/diff, environnement, sources, binaires et logs.

macOS arm64, Metal. Token et commandes utilisent le même provider portable SDL sur les cibles distribuées ; aucune ABI/archive/sélection de cible/shader modifiée. Applicabilité structurelle aux devices supportés sur ces cibles, gain et exécution Linux/Windows/x64 inconnus dans cette tranche. Aucune généralisation du gain hôte.

## Charges observables

Softmax : six cas isolés par processus (vecteurs 1, 7, 257, 4096, 65536 ; vue transposée/rétrécie issue de [7,9], 49 valeurs). 512 appels chauds sur vecteurs 1/7/257 et vue, 64 sur vecteurs 4096/65536 ; 5 passes/bindings/dispatches par appel identiques, 5 soumissions avant et 1 après ; attendre le device avant arrêt du chronomètre. Initialisation/upload/pipelines et 16 appels de warmup achevés dans `cold_ms`, distinct de la métrique chaude. Chaque résultat et l’entrée entière sont vérifiés après chronométrage, tolérance 2e-5, dtype float32 et input fini. Aucun upload/download/pipeline dans la région chaude ; le cache et les bytes utilisés/demandés sont rapportés. CPU stable softmax oracle ; témoins scalaires et gradients analytiques séparés dans les tests.

Modèles : MLP/CNN/SimpleRNN/GRU/LSTM/Transformer, mêmes seeds 481/482, AdamW 0.01, epsilon 1e-4, warmup 2 étapes et 3 étapes chaudes synchronisées. 1700 scalaires (92/116/108/288/372/724), toutes sorties/paramètres/gradients/deux moments et step_count 5. Tolérance CPU/Metal et avant/après 2e-5 fixée. Passes identiques ; soumissions/fences fidèles et réduites uniquement aux softmax groupés, copies GPU de vues conservées. Vérifier les compteurs de façon stable par variante, sans exiger leur égalité entre variantes. Aucun transfert ou pipeline chaud. Observer l’état après chronométrage et vérifier tous les scalaires de chaque processus.

## Admission

Pour chaque cas softmax : 16 paires avant/après en ordre alterné, 8 paires A/A par bras ; 64 processus isolés, 384 processus pour six cas. Pour les modèles : 16 paires avant/après et 8 A/A par bras, 64 processus pour six familles ; ordre des familles inversé entre paires. Aucune soustraction des résultats de la première campagne, dont le verdict reste indéterminé. La nouvelle charge réduit les transitions entre kernels lourds et microcas ainsi que le bruit relatif des petits cas. Signal au moins 5 %, supérieur à 3 MAD des différences appariées, direction cohérente sur au moins 14/16, les deux A/A valides. A/A invalide si sa médiane absolue atteint 5 % et dépasse 3 MAD ; dénominateur nul indéterminé. Aucun retrait d’outlier, changement de seuil ou soustraction du bruit après observation.

Conserver raw logs/time, CSV/JSON, sources, qualification, contrôles et recomputation. Rapporter coûts froids et pics de bytes utilisés/natifs demandés, cache et RSS processus (pas de VRAM physique). Une indétermination ne prouve pas l’absence de régression. Ne pas modifier les seuils numériques, epsilon ou forme des modèles pour obtenir un résultat favorable. Promotion et livraison uniquement après corpus complet vert et analyse des contre-épreuves.
