# Contrôle19 — kernel identique, enveloppes différentes

Nouveau discriminant : première attribution640mesures et contrôle128mesures
n’identifient pas de coût dominant du buffer, des seules métadonnées ou commandes
vides. Le pilote kernel indique un écart, sans gain produit admis.

Sonde privée temporaire @EagerKernel.sx, Debug/Release vérifiés puis source
retirée. Même shader élémentaire de GPUKernelCache, metadata80octets de
Layout([1]) et BinaryOperation.add, float32input1 et scalar1 : sortie2.
64passes et64soumissions par bras,0transfert dans région, observations hors
chronométrage. Native GPU emploie un buffer de sortie partagé, donc ce contrôle
n’est pas une implémentation valable de valeurs Tensor immuables. La réutilisation
ne prouve aucun pool sûr ; elle isole une enveloppe à diagnostiquer.

Quatre bras : Tensor en remplacement, collecte Profile inactive ou active ;
encodage GFX direct du même kernel, attente par commande ou finale. Dans le bras
GPU direct, buffers, metadata et pipeline sont préparés hors région, warmup4 ;
64fences libérées dans la région. Le profil public ne compte pas ces appels GFX
externes ; un Profile propriétaire assure la retraite de l’entrée privée du cache.
Tous les registres Tensor sont revenus à zéro après chaque vérificateur.

Tensor conserve son suivi de buffers même sans période Profile. La comparaison
active/inactive utilise le même Tensor et protège le coût de la collecte : aucun
profil gratuit présumé. WarmupTensor1add avant région ; conditions identiques
dans les deux bras. Source et résultat Tensor gardent leurs durées de vie.

16 processus Release à ordre alterné et8paires A/A (32processus/128lignes).
Règle préalable5%/3MAD/14sur16 et contrôles valides comme aux protocoles19.
Médiane/MAD et plage, aucune élimination de sample ni soustraction du bruit,
aucun build/test concurrent, empreintes après campagne. CPU/GPU n’utilisent
pas de clocks device ; rapporter seulement le temps mural synchronisé de cet
hôte macOS ARM64 / Metal M3 et de ces versions exactes.

Si la collecte explique l’écart, examiner son propriétaire et ne pas contourner
l’observabilité. Sinon, isoler constructions/releases Tensor et encodage réel
avant une modification produit. Les observations de contrôles aux enveloppes
différentes ne sont pas un avant/après d’accélération Tensor.
