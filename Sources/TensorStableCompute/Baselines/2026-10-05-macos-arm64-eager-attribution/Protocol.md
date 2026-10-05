# Contrôle19 — préparation CPU et soumissions vides

Nouveau discriminant après rétention indéterminée, pas une relance du même
contrôle pour sélectionner un résultat favorable. Protocole fixé avant timings.

Sonde temporaire dans Module/@EagerAttribution.sx, namespace propriétaire :
fonctions Layout/elementwise_metadata d’origine inchangées et sans nouvelle
visibilité. Snapshot source épinglé ; retirer la sonde après compilation
Debug/Release et vérification. Les binaires seuls servent aux timings ;
les empreintes des sources de production originales restent celles d6cff04.
Première assertion de la sonde supposait64octets ; les routines pad8shape+
pad8stride plus4mots produisent80octets. Correction du témoin seulement,
pas de correction produit ni tolérance élargie. Première tentative conservée.

Premier bras :1024 générations du même metadata(operation7,shape256), contre
1024 usages d’une table existante construite hors région. Champs op/count/rank,
taille80 et checksum90112 vérifiés ; warmup16générations. Ce contrôle n’impose
pas la mise en cache d’une metadata ni sa réutilisation avec un autre layout.

Second bras :64 commandes vides avec fence, attente par commande contre
rétention des64fences et une attente finale. Aucun kernel, transfert ou passe ;
les64fences sont libérées dans la région mesurée dans les deux cas. Warmup4
commandes. La différence mesure aussi la gestion de la collection retenue,
pas une attente pure ; les commandes sans dispatch ne sont pas une charge
numériquement identique aux64add Tensor du premier banc.

Release, macOS ARM64 / Metal M3.16 processus --measure à ordre alterné et
8paires A/A (16processus supplémentaires),128 lignes brutes. Médiane/MAD,
plage, signes et contrôles, règle préalable5%/3MAD/14sur16 du protocole initial.
Tout conserver, aucun build/test concurrent, identité source/binaire après
mesure. Déclarer indéterminées les cases au contrôle invalide ou temps nul.
Normaliser les coûts par appel pour examiner un propriétaire ; ne pas additionner
les contrôles séparés comme attribution causale exacte du parcours Tensor.
Si les deux coûts sont trop petits, examiner encodage/binding/dispatch plutôt
que forcer un pool. Les exigences J3 restent intégralement ouvertes.
