# Qualification finale des modèles

## Configuration et question

La lane et les checkouts directs sont propres et concordent à la livraison37 :
Tensor `0ceb199`, Silex `a41bf8b`, benchmarks `80248b7`, documentation `8fcc835`,
STD `4112bb5`, GFX `4dbdac9`, GFX.GPU `fb17a0c`.
Le compilateur de lane est inchangé ; aucun produit n’est modifié par ce banc.

Comparer les six fixtures de ResidentSteps (seeds481/482, entrées asymétriques)
avec MSE float32 et AdamW epsilon0.01, comme le témoin figé de TrainingStep.
Cinq étapes : deux eager avant préparation, puis trois étapes confrontées.
CPU eager est l’oracle indépendant (tolérance absolue2e-5), GPU eager la
référence exacte des chemins forward préparé et TrainingStep. Une répétition
GPU eager prouve le déterminisme. À chaque étape : sorties/perte avant update,
poids, gradients, moments, compteurs, noms, trainabilité, modes et hyperparamètres.
Sur les cinq familles hors domaine, les deux préparations doivent échouer après
les étapes chaudes et préserver l’état entier avant reprise eager explicite.
Aucun test n’adapte epsilon, tolérance ou workload après un résultat.

Le profil porte uniquement sur les trois étapes chaudes, en dehors des
observations CPU. Il exige zéro transfert/compilation, passes natives cohérentes,
et destruction totale après chaque cas. Aucun temps ni gain nouveau n’est admis.
Les chemins doivent avoir les mêmes valeurs complètes et des compteurs explicables.

## Contrôle de fusion

Une variante privée diagnostique retire seulement le branchement GPU vers
`variance.shifted_square_root(epsilon)` dans Tensor.layer_norm. Elle conserve
la même réduction et l’ordre add puis sqrt, et tous les autres modules inchangés.
Le runner garde les octets originaux, les restaure dans finally avant tout test
candidat, et conserve la variante/source/binaire/empreintes exacts. Cette variante
ne se committe pas et n’est jamais une option API. Elle exécute uniquement eager
et se compare au candidat sur les états imprimés : diminution de passes attendue
pour Transformer, égalité pour les cinq autres familles. Les preuves de microgain
existantes restent les seules admissions de performance de cette fusion.

ResidentSteps original est aussi rejoué Debug/Release : cross-entropy, epsilon1e-4,
tolérance2e-5*(1+abs), sans modification. Le corpus470tests/112sources et les gates16
sont réutilisés seulement si les empreintes Tensor restent identiques.

## Audit de compatibilité

Les versions publiées ne changent pas pendant ce développement. Le range historique
`>=0.44.1` du manifeste ne prouve pas que les nouvelles capacités sont disponibles
avec une release ancienne : des correctifs Silex non publiés sont nécessaires.
La documentation doit préciser le compilateur source exact qualifié et distinguer
ce développement local de la compatibilité de la prochaine publication. Aucun
nouveau numéro de release ni disponibilité installable n’est annoncé par la Spec.
