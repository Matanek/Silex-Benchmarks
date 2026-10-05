# Kernel identique et enveloppe Tensor

32 processus Release,128 mesures sur macOS26.6.2/Apple M3 Pro ARM64, Silex9ba34c2/Tensor d6cff04. Même shader élémentaire et sortie2,64passes/soumissions,0transfert résident ; Debug/Release corrects.

| Bras64opérations | Médiane ms | MAD ms |
|---|---:|---:|
| Tensor/Profile inactif |103,5235|6,0285|
| Tensor/Profile actif |109,0885|8,3290|
| GPU direct/attente individuelle |17,2625|1,0445|
| GPU direct/attente finale |3,8915|1,0145|

Profile actif/inactif : delta apparié+1,1083%, MAD6,9973%, indéterminé. Tensor vers GPU individuel :−83,6722%, MAD1,5148%, signal diagnostique. GPU individuel vers final :−79,5202%, MAD4,8534%, signal diagnostique. Tous contrôles A/A valides ; aucune mesure supprimée.

GPU direct prépare pipeline/metadata hors région et réutilise un seul buffer : il ne remplace pas les valeurs Tensor immuables. Ces observations localisent l'enveloppe à diagnostiquer ; aucun pool ou batching Tensor admis. Source privée temporaire retirée avant timings ; Probe.sx.txt, protocoles et logs préservent le contrôle.

## Contrôler et reproduire

Depuis ce dossier, `python3 Verify.py` vérifie toutes les empreintes, les32exécutions et les verdicts5%/3MAD/14sur16. Les configurations enregistrent sources, compilateur, binaire et dépendances exactes.

Pour une nouvelle campagne, utiliser un workspace à ces commits et le compilateur indiqué dans Configuration.json. Les scripts OriginalQualification.py et OriginalCampaign.py sont les recettes historiques de la Spec : leurs chemins Memory/Artifacts doivent être adaptés au workspace de reproduction et cette adaptation conservée dans son résultat. La compilation reste à la racine du workspace avec le cache partagé `.silex`. Matérialiser Probe.sx.txt dans `Packages/Tensor/Module/@EagerAttribution.sx` ou `@EagerKernel.sx` selon ce dossier, compiler Debug/Release et vérifier, puis retirer la sonde dans un finally avant toute mesure. Ne pas exposer Layout ou les caches privés dans l'API Tensor. Une campagne avec un autre compilateur produit une nouvelle configuration, sans remplacer ces données.

Les binaires natifs et caches ne sont pas versionnés. Ces contrôles concernent Metal M3 et le temps mural synchronisé ; ils ne prouvent pas des performances sur les autres cibles ni la mémoire physique GPU.
