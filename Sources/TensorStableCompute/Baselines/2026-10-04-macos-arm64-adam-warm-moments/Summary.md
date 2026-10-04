# Adam : suppression des moments nuls recalculés

## Résultat borné

Tensor e742c9a1f55d3dcb4a3d64199607f023e512a193 évite deux calculs temporaires
par paramètre actif après sa première étape Adam. L’initialisation, les formules,
les valeurs et la numérotation des états restent identiques. Ce résultat ne crée
ni API, ni pool, ni regroupement de commandes. Les vérifications et sources sont
liées au [protocole](Protocol.md).

Sur ce M3 Pro / Metal, les pas Adam GPU admis progressent de 5,5 à 9,8 % ; les
pas complets résidents admis progressent de 5,3 à 8,3 %. CNN batch 16 Adam seul
(3,0 %) et RNN batch 16 complet (2,3 %) ne satisfont pas le seuil. Adam CPU
progresse également sur la grille (5,6 à 8,6 %). Aucun gain portable ou gain de
forward/backward n’est revendiqué. La baisse exacte des ressources est commune
aux chemins GPU : deux passes, allocations et fences par paramètre chaud.

## Méthode et règle d’admission

Même machine, même compilateur, mêmes dépendances, même Neural.sx. Cinq paires
indépendantes par famille, ordre des deux binaires alterné et rotation des
familles. Chaque processus vérifie son fonctionnement. Les régions résidentes
ont zéro transfert. Les temps sont muraux synchronisés, pas des timestamps GPU.

La règle fixée avant mesure demande un gain des médianes >=5 %, supérieur aux
MAD relatifs des deux configurations et au moins quatre paires favorables sur
cinq. La règle est un critère d’admission local, pas une preuve statistique de
performance universelle. Le CSV conserve aussi médiane des gains par paire et
min/max ; les RSS sont dans les résumés de chaque configuration. Les phases
Adam mélangent première étape et suivantes, comme le banc de départ.

## Adam GPU

| Famille / batch | Référence ms | Candidat ms | Gain des médianes | MAD réf. / cand. | Paires favorables | Règle |
|---|---:|---:|---:|---:|---:|---|
| mlp / 4 | 21.9877 | 20.0357 | 8.9 % | 0.9 / 0.9 % | 4/5 | admise |
| mlp / 16 | 21.3820 | 19.3547 | 9.5 % | 1.1 / 1.0 % | 5/5 | admise |
| mlp / 64 | 21.8157 | 19.7763 | 9.3 % | 0.1 / 1.6 % | 5/5 | admise |
| cnn / 1 | 21.8917 | 20.3053 | 7.2 % | 1.2 / 1.6 % | 5/5 | admise |
| cnn / 4 | 21.6157 | 19.7960 | 8.4 % | 0.1 / 2.0 % | 5/5 | admise |
| cnn / 16 | 22.2360 | 21.5665 | 3.0 % | 2.1 / 0.9 % | 4/5 | non admise |
| rnn / 4 | 26.7397 | 24.6577 | 7.8 % | 3.1 / 1.3 % | 5/5 | admise |
| rnn / 16 | 26.7560 | 24.1420 | 9.8 % | 0.9 / 0.8 % | 5/5 | admise |
| rnn / 64 | 27.1760 | 25.6825 | 5.5 % | 2.8 / 2.7 % | 5/5 | admise |

## Étape complète résidente GPU

| Famille / batch | Référence ms | Candidat ms | Gain des médianes | MAD réf. / cand. | Paires favorables | Règle |
|---|---:|---:|---:|---:|---:|---|
| mlp / 4 | 36.9453 | 34.4950 | 6.6 % | 1.2 / 1.5 % | 4/5 | admise |
| mlp / 16 | 37.6620 | 34.5380 | 8.3 % | 1.6 / 2.5 % | 5/5 | admise |
| mlp / 64 | 36.7607 | 34.0130 | 7.5 % | 0.7 / 0.9 % | 5/5 | admise |
| cnn / 1 | 37.0093 | 34.8133 | 5.9 % | 0.8 / 0.9 % | 5/5 | admise |
| cnn / 4 | 36.8177 | 34.2387 | 7.0 % | 0.9 / 0.5 % | 5/5 | admise |
| cnn / 16 | 37.5955 | 34.4700 | 8.3 % | 0.7 / 2.7 % | 5/5 | admise |
| rnn / 4 | 82.4283 | 77.7057 | 5.7 % | 1.1 / 0.4 % | 5/5 | admise |
| rnn / 16 | 81.6823 | 79.8147 | 2.3 % | 0.9 / 1.5 % | 4/5 | non admise |
| rnn / 64 | 82.5905 | 78.2130 | 5.3 % | 2.2 / 1.5 % | 5/5 | admise |

## Adam CPU

| Famille / batch | Référence ms | Candidat ms | Gain des médianes | MAD réf. / cand. | Paires favorables | Règle |
|---|---:|---:|---:|---:|---:|---|
| mlp / 4 | 2.3923 | 2.1980 | 8.1 % | 1.1 / 0.6 % | 5/5 | admise |
| mlp / 16 | 2.3920 | 2.2043 | 7.8 % | 0.5 / 1.6 % | 5/5 | admise |
| mlp / 64 | 2.4033 | 2.1967 | 8.6 % | 0.2 / 0.5 % | 5/5 | admise |
| cnn / 1 | 0.4103 | 0.3750 | 8.6 % | 1.5 / 2.0 % | 5/5 | admise |
| cnn / 4 | 0.4077 | 0.3850 | 5.6 % | 1.7 / 2.3 % | 4/5 | admise |
| cnn / 16 | 0.4150 | 0.3855 | 7.1 % | 0.8 / 0.4 % | 5/5 | admise |
| rnn / 4 | 0.5770 | 0.5360 | 7.1 % | 0.9 / 3.0 % | 5/5 | admise |
| rnn / 16 | 0.5660 | 0.5293 | 6.5 % | 1.3 / 2.3 % | 5/5 | admise |
| rnn / 64 | 0.5635 | 0.5235 | 7.1 % | 0.7 / 0.7 % | 5/5 | admise |

## Contrôle des phases non modifiées et limite de mesure

La première comparaison signale des écarts défavorables de 15,8 % sur le forward
GPU CNN batch 4, 6,7 % CNN batch 16, 5,1 % RNN batch 64 et 15,2 % sur backward
CNN batch 16, ainsi que 6–7 % sur forward/backward CPU RNN batch 4. Leur code
et leurs comptes de passes sont inchangés ; ces faits seuls ne prouvent pas
une origine expérimentale plutôt qu’un effet indirect de configuration.

Un contrôle négatif refait cinq paires **du même binaire de référence** par
famille, avec le même ordre alterné et les mêmes tailles. Les MAD des forwards
GPU CNN 4 montent à 8,2/4,3 %, CNN 16 à 2,6/12,2 %, RNN 64 à 5,0/7,1 % ; le
backward CNN 16 atteint 9,9/2,4 %. Les temps de candidat des phases signalées
restent dans les plages de ce contrôle. Les faibles MAD de cinq échantillons
lors de la première comparaison ne capturent donc pas toute la variabilité.
Cette expérience n’attribue pas individuellement chaque écart : elle interdit
de qualifier ici une accélération ou une non-régression universelle des kernels.

Les phases principales sont plus stables dans ce contrôle : Adam GPU donne des
écarts des médianes de 0,4–5,2 % entre labels identiques (maximum MLP batch 16),
les pas complets de -0,8 à +2,2 %. Les gains retenus restent supérieurs à leur
écart A/A correspondant et aux MAD A/A correspondants. Le contrôle et toutes
ses données sont conservés dans [NegativeControl](NegativeControl/Comparisons.csv),
sans choisir ou retirer des échantillons. Cette conclusion borne le gain à
Adam et aux étapes résidentes admises ; elle ne prétend pas annuler le bruit.

## Compteurs, correction et limites

La garde AdamWarmState prouve 16 passes/allocations/fences à la première étape
par paramètre, puis 14 ; les paramètres sans gradient consomment zéro passe et
leur initialisation différée reste qualifiée. Les pas chauds complets du banc
passent de 111 à 103 passes (MLP/CNN), de 243 à 233 (RNN). Les phases forward,
backward et SGD conservent leurs comptes. Aucun readback caché n’est ajouté.

107 tests passent, dont les oracles différentiels déjà générés, la première
mise à jour des très petits gradients et les moments signés CPU/GPU. Debug et
Release vérifient le banc avant mesures ; le rejet d’état sur un mauvais
placement est préservé. Les logs de qualification sérialisée sont conservés.
Une qualification concurrente a auparavant reçu trois shaders vides ; son
rejeu isolé et toute la suite sérialisée passent. Aucun sample en échec n’est
admis ; cette possible fragilité de concurrence n’est pas diagnostiquée comme
une erreur numérique d’Adam.

Les trois objectifs de la Spec restent ouverts : profil public, pools/commandes,
fusion/plans et float16 pour J3 ; lots/reprise pour J1 ; composition et modèles
modernes pour J2. Les autres cibles ont le même changement de source pure Silex,
mais leurs performances et leurs backends GPU ne sont pas mesurés ici.
