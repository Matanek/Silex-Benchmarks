# Task38 — protocole du cache prêt avant campagne d’admission

## Hypothèse et discriminant

Après la correction des constructions implicites livrée en Task19, le coût des
créations de buffers de stockage peut rester évitable. L’explication concurrente
est la domination des dispatches/fences ou le bookkeeping du cache. Ne conserver
le cache que si les mesures de charges identiques montrent un bénéfice admis.
Une baisse des allocations seule ne constitue pas une accélération mesurée.

Cache privé prêt : 32 entrées et 1048576 octets par device, taille/dtype exacts,
usage storage identique, attente de drop existante conservée. Pas de batching,
pas de pool de fences/staging, pas de parent Tensor conservé dans les entrées.
Dernier stockage : vider le cache même avec profils vivants. Une valeur, vue ou
branche vivante empêche toute réutilisation de son buffer.

## Configurations fixées

Baseline Tensor e7394c81b72ae86058bca7e9e5f1fc58674651ef, module avant pool.
Compilateur identique dans les deux bras : Silex direct d0834c70, ReleaseFast,
SHA256 9b5ceb5e1a951bb8a92190d690ed68a0b85ddb1c577b302c539f42dbc21e833c.
Bancs EagerResources et ResidentSteps : sources strictement identiques dans
les deux bras, gardes adaptées au comptage réel des buffers natifs. Construire
les deux binaires depuis la racine Worktree, avec son unique cache de Spec.
Capturer les empreintes des sources, HEADs, binaires et logs avant timing.
Aucun test, build ou diagnostic simultané à la campagne. Ne remplacer aucun
lien utilisateur ; une permutation temporaire des deux fichiers Module est
restaurée dans finally et vérifiée à l’octet, sans mouvement de Git HEAD.

macOS arm64 / Metal natif Debug et Release qualifiés. Ce changement est Silex
privé, consomme le contrat portable GPU.Buffer/Device/Fence existant et ne
modifie ni provider, ABI, archive, shaders ni sélection de cible. Les autres
cibles distribuées suivent la même politique de cache lorsqu’un device est
pris en charge ; aucune mesure ou preuve d’exécution Linux/Windows/x64 dans
cette tranche. Ne pas généraliser le gain hôte à ces cibles.

## Portes de correction

Valeurs et alias conservés sur 4096 dispatches ; isolation de dix dtypes à
32 octets identiques, deux devices, extrema signés/non signés ; 1536 cycles
booléens de tailles non multiples de quatre avec overwrite des queues.
Capacités/évictions, trop grand direct, mémoire nulle après destruction des
stockages, profil encore vivant. Snapshot/reset/déstruction de Profile sans
commandes ni mutation du cache. Defaults neutres pour construction antérieure
nommée de ProfileStatistics. Corpus Tensor positif complet, gradients, graphes,
états d’optimiseur et familles récurrentes, plus vérification des deux bancs en
Debug/Release avant campagne. Les exactes créations logiques anciennes deviennent
allocations natives + réutilisations ; les gardes de stockage utilisé conservent
leurs bornes, les buffers natifs incluent le cache. Toute borne dépendante de
la rapidité de complétion doit être réduite et justifiée séparément, sans cacher
un graphe conservé ni élargir une garde sans preuve.

ResidentSteps : six familles MLP/CNN/SimpleRNN/GRU/LSTM/Transformer, seeds481/482,
AdamW0.01, epsilon1e-4, deux étapes de warmup, trois étapes synchronisées mesurées.
1700 scalaires non vides (92/116/108/288/372/724), sorties/poids/gradients/deux
moments, compteurs5 ; tolérance CPU/Metal et avant/après2e-5 inchangée. Passes,
soumissions et états identiques ; allocations peuvent baisser et ne sont pas
une garde d’égalité entre bras. Transferts et compilation de pipelines nuls
dans la région résidente. Observations hors chronométrage.

EagerResources : quatre tailles, replace/retain/dependent,64 opérations et
64 passes/soumissions/fences, sorties complètes2/65, aucun transfert résident.
Avant eager exige64 créations effectives, après peut réutiliser ; contrôle
GFX inchangé4096 tailles consultées/créations sans Tensor. Vues vivantes et
pics de bytes utilisés protégés indépendamment du comptage natif.

## Admission fixée

Pour chaque banc,16 paires avant/après en ordre alterné,8 paires A/A de chaque
binaire ;64 processus au total. Même ordre des cas dans les bras d’une paire,
ordre des cas alterné entre paires. Médianes/MAD/plages brutes et différences
appariées conservées ; signal d’au moins5 %, supérieur à3MAD, direction14sur16,
tous A/A valides. Un dénominateur nul ou un A/A invalide rend le verdict
indéterminé ; aucune sélection, élimination ou soustraction du bruit.

Rapporter les cas sans gain et toute hausse de latence/mémoire. Ajouter les
coûts de démarrage/warmup synchronisés hors métrique chaude, sans remplacer la
métrique principale. RSS de processus et bytes natifs demandés/cachés restent
distincts de la VRAM physique. Conserver les sources/empreintes, raw/time, CSV,
configuration, contrôles et outil de recomputation. Aucun changement de seuil,
epsilon ou tolérance après observation du candidat.
