# Préparation CPU et commandes vides

32 processus Release,128 mesures sur macOS26.6.2/Apple M3 Pro ARM64, Silex9ba34c2/Tensor d6cff04. Toutes les vérifications Debug/Release et valeurs sont vertes.

Metadata1024fois : médiane4,59ms contre0,0595ms pour une table déjà préparée ; delta apparié−98,34%, MAD0,78%, signal diagnostique. Projeté à64appels :0,287ms, trop petit pour attribuer les≈100ms des additions Tensor. Commandes vides64fois :3,8735ms attente individuelle contre1,594ms finale ; delta−49,33%, MAD23,27%, verdict indéterminé. Contrôles A/A valides ; plages et tous points dans Summary.json/Rows.json. Aucune accélération Tensor ni absence de régression déduite.

La sonde appartient temporairement au namespace privé Tensor, puis est retirée. Probe.sx.txt et les logs qualifiés conservent sa recette. L'assertion initiale de taille a été corrigée de64à80octets avant cette campagne ; aucune source produit ou tolérance modifiée.

## Contrôler et reproduire

Depuis ce dossier, `python3 Verify.py` vérifie toutes les empreintes, les32exécutions et les verdicts5%/3MAD/14sur16. Les configurations enregistrent sources, compilateur, binaire et dépendances exactes.

Pour une nouvelle campagne, utiliser un workspace à ces commits et le compilateur indiqué dans Configuration.json. Les scripts OriginalQualification.py et OriginalCampaign.py sont les recettes historiques de la Spec : leurs chemins Memory/Artifacts doivent être adaptés au workspace de reproduction et cette adaptation conservée dans son résultat. La compilation reste à la racine du workspace avec le cache partagé `.silex`. Matérialiser Probe.sx.txt dans `Packages/Tensor/Module/@EagerAttribution.sx` ou `@EagerKernel.sx` selon ce dossier, compiler Debug/Release et vérifier, puis retirer la sonde dans un finally avant toute mesure. Ne pas exposer Layout ou les caches privés dans l'API Tensor. Une campagne avec un autre compilateur produit une nouvelle configuration, sans remplacer ces données.

Les binaires natifs et caches ne sont pas versionnés. Ces contrôles concernent Metal M3 et le temps mural synchronisé ; ils ne prouvent pas des performances sur les autres cibles ni la mémoire physique GPU.
