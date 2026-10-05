# Task19 — protocole résident corrigé, avant les mesures admises

Complète le protocole des constructions avec un banc de six modèles vérifié
sur toutes les observations. Le premier essai avait une collecte vide et
n’entre dans aucune preuve de gain. Les essais de qualification suivants et
le diagnostic d’epsilon précèdent entièrement la campagne admise.

MLP, CNN, SimpleRNN, GRU, LSTM et Transformer ; seeds 481/482, données
asymétriques et labels [0,1], AdamW learning_rate 0.01, epsilon explicitement
1e-4 dans toutes les familles et tous les bras. Deux étapes de warmup, puis
trois étapes synchronisées zero_grad/forward/cross_entropy/backward/step.
Lecture des sorties, paramètres, gradients, deux moments et compteur cinq
après timing. Exactement 92/116/108/288/372/724 observations respectivement,
1700 au total ; la collecte par référence et sa cardinalité sont obligatoires.

L’epsilon est fixé depuis un diagnostic indépendant de performance : avec
le défaut 1e-8, seuls quatre biais de clés divergent CPU/Metal après cinq
mises à jour, gradients finaux de l’ordre de 1e-9. Ils ajoutent une constante
par query aux scores, neutralisée par softmax ; le bruit de roundoff est
amplifié par l’optimiseur adaptatif. Les 724 observations Transformer sont
identiques avant/après à backend et epsilon identiques. À epsilon 1e-4,
le maximum normalisé CPU/Metal est 2,03e-6, contre 0,01348 avec le défaut.
La tolérance 2e-5 demeure inchangée ; aucun gradient n’est clampé, aucune
formule Tensor ou valeur par défaut produit ne change. Données et seeds
restent identiques. Ce banc n’admet aucun gain spécifique au réglage par défaut.

16 paires de processus avant/après à ordre alterné, puis huit paires A/A de
chaque binaire, soit 64 processus. Même ordre de familles dans une paire,
ordre inverse une paire sur deux. Région sans transfert CPU/GPU ni compilation
de pipeline ; copies GPU internes comptées parmi soumissions/fences. Passes,
allocations et soumissions identiques entre tous les bras ; sorties/gradients/
paramètres/moments complets comparés à 2e-5. Sources, compilateurs, binaires,
HEADs, OS et machine figés avant campagne. Aucune compilation/test concurrent.

Admission inchangée : médiane d’écart apparié au moins 5 %, supérieure à
3 MAD, direction cohérente sur 14/16 et deux contrôles A/A valides. Un zéro ou
contrôle invalide rend la case indéterminée. Aucune sélection/élimination de
répétition. Rapporter régressions et contre-épreuves ; RSS du processus et
bytes demandés ne prouvent pas la mémoire physique GPU. Raw/time/checksums,
configuration et recomputation des statistiques conservés chez Benchmarks.
