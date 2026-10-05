# Task19 — construction des dépendances, protocole avant candidat mesuré

Cause réduite : GPUStorage.scalar consacre97,258ms sur105,808ms à construire
GPUStorage dans le pilote instrumenté, contre7,671ms cumulés avant la
construction et0,467ms pour63destructions. Le second bras donne93,525ms pour
la construction. Instrumentation retirée, @Storage.sx restauré à l’octet.
Ce diagnostic ne compte pas comme gain produit.

Le compilateur9ba émet un appel au constructeur sans argument pour un champ
de classe `var` sans expression, puis le remplace par le paramètre de `init`.
GPUStorage et GPUKernelCache stockent ainsi GPU.Device ; GPUProfileState aussi.
Cas réduit interprète/Debug/Release : une Resource fournie à deux propriétaires
produit3créations et2destructions transitoires. Ce coût relève de
Semantic/Constructors.zig, pas des buffers Metal ni de l’autograd.

`let` n’est pas la correction : le langage exige var pour les champs qui
atteignent une classe. Aucun optionnel artificiel ni wrapper n’est introduit.
Tranche verticale : dans un constructeur explicite, une référence de classe
n’a pas de valeur intrinsèque ; elle attend une affectation sur chaque chemin.
`var resource:Resource = Resource()` garde ses effets déclarés. L’initialiseur
automatique sans `init` garde sa construction d’objets. Null des optionnels,
collections dynamiques vides et valeurs primitives restent intrinsèques.
La règle se propage aux structures sans constructeur composées de champs de
classe en attente, avec les gardes d’initialisation existantes.

## Correction et portée

Quatre nouvelles preuves comptent créations/destructions et identité :
références fournies/structure imbriquée, initialiseur explicite avec remplacement,
constructeur automatique et deux branches. Ancien compilateur :2passed/2failed,
échecs exacts des créations inutiles, contrôles déclarés/automatiques verts.
Ajouter diagnostics lecture prématurée, chemin manquant et fuite de self,
interprète, natif Debug/Release et backend LLVM sur le cas réduit. Exécuter
zig build check/test et corpus de propriété existant. Documentation FR puis EN
et notes Silex explicites ; pas de nouvelle syntaxe ni mot-clé.

Propriétaire : frontend/IR commune ; aucune branche système, ABI, layout ou
runtime modifiée. Le chemin des champs de classe en attente est déjà celui
des dépendances à constructeur requis. Applicable aux six cibles distribuées ;
correction portable et exécution native macos-arm64 qualifiées dans cette
tranche, aucune mesure x64/Linux/Windows ni prétention de gain sur ces cibles.
L’ancien compilateur exact est conservé dans Artifacts/Silex-Before-Constructor-Dependencies.

Module Tensor d6cff04 reste inchangé ; les trois gardes asynchrones adoptent
des bornes retenues/analytique, sans changement de production. Qualifier les familles GPU existantes/modernes,
vues/alias, gradients/consommation, profils, deux devices et durées de vie.
Les plafonds récurrents sont les bornes déterminées avec parents retenus,
pas des premières itérations dépendantes de la vitesse du CPU.

## Admission de performance

Après toutes les gates, sceller les HEADs propres, empreintes compilateurs,
sources et binaires avant/ après. Le changement comparé appartient au
compilateur : ne pas annoncer une campagne à compilateur identique.
Banc public EagerResources.sx inchangé, Release, quatre tailles et trois
durées de vie, contrôles buffer GFX. Avant : binaire9b8b8588… épinglé à9ba,
après : reconstruit avec le candidat. Exactes sorties2/65,64passes/allocations/
soumissions/fences,0transfert résident, conservation des ressources dans les
deux configurations. Aucune soumission évitée ni pool prouvé par cette tranche.

16paires de processus avant/après, ordre alterné et huit paires A/A de chaque
binaire. Même région synchronisée et warmup, aucune compilation/test concurrent.
Médiane/MAD/plages et différences appariées ; signal au moins5%, supérieur à
3MAD et direction14sur16, tous contrôles A/A valides. Zéro ou contrôle invalide
rend la case indéterminée, aucune élimination/soustraction ni sélection de gain.
Rapporter les contrôles/régressions aussi. RSS processus ne prouve pas la
mémoire physique GPU. Conserver raw/time et leurs checksums.

Étendre ensuite aux étapes résidentes de modèles représentatifs existants
et modernes sur la même règle, sources et états finaux observables identiques.
Les timings micro ne constituent pas leur bénéfice. Aucun gain global admis
avant ces résultats ; pools/groupements, fusion/plans et gate float16 demeurent
ouverts après cette première réduction des créations de ressources.

## Banc des six modèles, réglages fixés avant mesures

ResidentSteps.sx utilise MLP, CNN, SimpleRNN, GRU, LSTM et Transformer ; seeds
481/482, données asymétriques, AdamW 0.01, deux étapes de warmup puis trois
étapes synchronisées chronométrées. Observation complète ensuite : sorties,
paramètres, gradients, deux moments et compteurs d’étape exactement cinq.
Tolérance CPU/Metal et avant/après 2e-5, ni readback ni compilation de pipeline
dans la région résidente. Commandes de copie GPU internes comptées parmi les
soumissions et fences, séparées des passes ; nombres de passes, allocations
et soumissions identiques vérifiés entre toutes les exécutions avant/après.
Les pics peuvent varier avec la complétion ; leur variation ne prouve pas une
réduction de la mémoire physique GPU. Le temps inclut zero_grad, forward,
cross_entropy, backward et step, puis l’attente finale. Familles en ordre
alterné entre paires, même ordre dans les deux bras d’une paire.
