# Task19 — protocole d’attribution préalable

Préparé avant toute mesure de candidat : aucun gain admis ni optimisation
produit implémentée. Les valeurs exactes du socle seront scellées après la
livraison37 et la validation/commit du banc ; protocole et artefacts porteront
leurs empreintes. Ne pas modifier ce protocole depuis un résultat favorable.

## Expérience et invariants

Hôte macOS ARM64 / Metal M3 du contrat. Tensor source et compilateur exacts ;
Release, aucune compilation ni autre test pendant les timings. Temps mural
synchronisé à l’entrée/sortie, aucune prétention de temps device. Le warmup
quatre opérations échauffe le chemin propre à chaque source avant chronométrage.
Le premier passage reste dans un pilote séparé ; il ne devient pas un échantillon
chaud. Les charges et flags restent identiques dans toute la campagne.

Quatre tailles f32 :1,256,4096,65536. À chaque taille :64 opérations add(1)
indépendantes, arm replace contre arm retain ; mêmes uploads hors région,
64allocations/soumissions/fences/passes/dispatches,0transfert dans la région.
Le bras retain garde au plus64 résultats jusqu’à la synchronisation finale,
soit16Mio demandés au maximum pour65536. Toutes les valeurs égales2 sont
contrôlées après arrêt du chronomètre ; les63 résultats non retournés sont
libérés avant retour du helper, inclus dans le chronomètre. Le résultat final
et les sources ont la même durée de vie dans les deux bras.

Contre-épreuve dépendante :64add(1) successifs, sortie65, mêmes nombres
opérations/commandes ; les parents peuvent être libérés selon fence.is_ready,
borne64résultats conservée. Ce bras n’est pas un substitut numériquement égal
aux bras indépendants, mais expose leur différence de dépendance/durée de vie.

Contrôle GFX :4096 appels buffer(size,storage) et libérations contre4096 lectures
de size sur un buffer déjà créé. Même checksum ; création du buffer de contrôle
et synchronisation initiale hors chronométrage, attente finale incluse. Ce témoin
isole l’enveloppe création/libération/paramétrage, pas des allocations physiques
Metal ni l’accélération d’un pool Tensor. Tensor.Profile ne compte pas ces
allocations GFX externes. La boucle de lecture constitue le coût de contrôle,
pas une charge de travail Tensor identique.

## Ordre, répétitions et règles

Pilote Debug/Release --verify avant campagne : sorties et compteurs exacts,
libération à chaque usage ; pas d’assertion chronométrique. Fixer les empreintes
sources/binaires et le commit du banc après ces gates, avant timings admis.

16 processus indépendants --measure, alternance équilibrée --reverse pour les
bras indépendants et buffer. Garder les16 paires A/B, puis huit paires A/A
(16 processus supplémentaires identiques, ordre identique dans chaque paire,
rotation de l’ordre entre paires). Conserver640 lignes brutes, médiane/MAD,
plages et différences appariées par taille/bras ; RSS processus en complément,
pas en guise de preuve de borne de propriété.

Signal causal exploitable : différence médiane relative d’au moins5%, supérieure
à3MAD des différences appariées ; direction concordante dans au moins14 des16
paires. Le contrôle A/A ne doit pas franchir les mêmes seuils de médiane et
3MAD, ni montrer une dérive systématique avec l’ordre. Un contrôle invalide ou
une mesure quantifiée à zéro rend le verdict indéterminé pour cette case ;
aucun échantillon éliminé ni bruit soustrait après coup. Rapporter tous les bras
et tailles, y compris régressions, neutralités et indéterminations.

Une différence de rétention prouve un coût de calendrier/destruction, pas
l’autorisation de garder arbitrairement tous les résultats en production.
Une différence du contrôle buffer ne prouve pas son poids dans un modèle.
Choisir seulement ensuite une réduction privée minimale, avec capacité et
achèvement sûrs, témoins adversariaux et avant/après sur mêmes charges ainsi
que modèles représentatifs. Si aucune attribution ne tient, changer le
discriminant ; ne pas clore silencieusement les mécanismes du contrat.
