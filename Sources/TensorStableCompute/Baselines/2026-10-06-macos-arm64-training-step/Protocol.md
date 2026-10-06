# Protocole public de l’étape complète MSE/AdamW

Figé avant toute série. Une seule source et un seul binaire Release pour les deux
bras, compiler lane a41bf8b (binaire fb51966…). Aucun build, test ou benchmark
concurrent. Empreintes du binaire et de tous les sources Tensor contrôlées avant
et après. Candidat public TrainingStep MSE/AdamW ; aucune généralisation hors ARM64
macOS/Metal ne résulte seule de cette campagne. Source canonique TrainingStep.sx.

Deux bras : eager complet zero_grad/forward/MSE/backward/AdamW et TrainingStep public
fermé forward préparé/MSE préparée/backward de référence/AdamW préparé.
Les deux préparent les mêmes pipelines avant16 étapes d’échauffement, puis
synchronisent. Plan et cache possédés, taux0.001, beta1=0.8,beta2=0.9,
epsilon0.01, decay0.07. Poids et moments courants relus. Aucun Profile dans la
mesure ; compteurs natifs et mémoire RSS séparés, préparation hors temps chaud.

Trois cas : MLP(2,2,4,2),128 étapes ; MLP(16,16,32,8),64 étapes ;
Dense–LayerNorm–tanh–Dense(4,2,4,2),64 étapes. Même ordre eager des expressions,
même état initial et entrées/cibles déterministes. CPU eager indépendant exécuté
hors chronomètre sur16+N étapes, comparaison finale des sorties/loss/gradients/
poids/moments/compteurs et hyperparamètres, tolérance absolue2e-5 inchangée.
Toutes les valeurs GPU finales sont imprimées pour recomparaison exacte entre
les deux bras. Entrées et cibles intactes. Synchronisation finale incluse.

Chaque cas16 paires A/B et8 A/A par bras, ordre équilibré AB/BA/BA/AB.
Aucun échantillon exclu ni relancé opportunistement. Admission locale si médiane
≤−5%, amplitude>3MAD et14/16 paires favorables, contrôles A/A valides.
Contrôle invalide si médiane absolue≥5% et>3MAD. Sinon résultat indéterminé.
Ressources et capture sans effet restent prouvées séparément Debug/Release ;
les2048 reprises ne sont pas des échantillons temporels.

Révision du candidat après preuve Before : la provenance incoming refuse
callbacks personnalisés, graphs consommés et plus de4096 nœuds avantzero_grad.
Les sources privées/publiques précédentes et campagnes restent historiques ;
aucune relance opportuniste de ces séries. Cette campagne concerne le nouveau
candidat corrigé et les mêmes16 paires/8 A/A, seuils et charges.
