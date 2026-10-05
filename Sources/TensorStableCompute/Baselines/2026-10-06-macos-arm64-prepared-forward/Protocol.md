# Protocole du candidat de plan forward

Figé avant les séries. Candidat Tensor complet possédé par Layer, compilateur
Silex lane a24a01d, SHA2562400fe01906ad2e49bbad32d8baefe449762e06b54b65ca2f4454bdb71776059.
Un seul binaire Release et les mêmes sources pour les deux bras ; les empreintes
sont enregistrées avant et contrôlées après. Pas de build/test parallèle aux mesures.

Comparer le forward public de Sequential sans plan au même forward avec plan.
Les deux processus préparent d’abord le même plan et chauffent les mêmes pipelines ;
le bras eager efface son plan avant l’échauffement. Cela isole la reprise chaude,
pas un gain de démarrage. Le temps de préparation avec compilation des pipelines
est observé séparément, hors temps chaud ; aucune réduction de ce coût n’est revendiquée.

Trois cas Dense–tanh–Dense trainables : (batch2,in2,hidden4,out2,512 reprises),
(16,16,32,8,256), (32,64,64,16,128). Seize échauffements, synchronisation GPU,
puis toutes reprises et attente finale dans le chronomètre. Profil Tensor désactivé.
Chaque reprise garde les cinq passes eager ; soumission commune et propriétaires
qualifiés auparavant Debug/Release. Toutes les valeurs de sortie sont comparées
au CPU eager après mesure, tolérance absolue2e−5, et toutes entrées restent exactes.

Chaque cas :16 paires A/B,8 A/A par bras, ordre équilibré AB/BA puis BA/AB.
Gain admis localement si médiane≤−5%, amplitude>3 MAD, au moins14/16 favorables,
et contrôles A/A valides. Un contrôle est invalide si sa médiane absolue≥5%
et>3 MAD. Pas d’exclusion d’échantillon ou relance opportuniste d’une série.

Quatrième cas distinct : petit plan actif dans les deux bras, Profile désactivé
puis activé. Mêmes paires et contrôles ; rapporter le surcoût observé du profil,
sans l’attribuer à un changement numérique ou à un gain de tous les modèles.
Les statistiques du plan restent présentes dans les deux bras. Mémoire et
ressources sont qualifiées séparément, hors chronomètre ; les bornes de reprise
sont128 buffers/32768 octets demandés, ressources nulles après propriétaires.

Cette première admission couvre une famille fermée. Elle ne prouve ni une étape
d’entraînement préparée, ni les six familles de modèles, ni float16/mixed precision.
Ces obligations restent dans les Tasks16–18 et le contrat inchangé.
