# Protocole figé — fusion add-sqrt

## Question et configurations

La région layer_norm GPU float32 évite une passe et un temporaire pour
variance.add(epsilon).sqrt. Une règle Autograd privée garde la dérivée eager.
Explication concurrente : le backward ou la rétention pourrait déplacer le coût.
Aucun changement des réductions, API, providers ni flags compiler.
Baseline Tensor7d91f411, candidat cinq sources Module + six tests ciblés.
Même compiler d0834c70, binaire SHA2569b5ceb5e1a951bb8a92190d690ed68a0b85ddb1c577b302c539f42dbc21e833c.
Release natif macOS arm64 M3 ; autres cibles : composition/shaders, gain non mesuré.

## Charges et preuves

Micro : vecteurs1,7,257,4096,65536 et vue transpose+narrow7x7 depuis7x9,
valeurs périodiques index%13 /3 -2, epsilon0.25, dimensions1.
Un processus par charge.16 appels warmup,512 appels chauds petites charges/vues,
64 grosses charges. Même source NormalizationFusion.sx dans les deux bras.
Observer chaque sortie après timing, oracle CPU2e-5 et entrée intacte ;
conserver temps froid (setup/upload/warmup) séparé du mur achevé chaud.
Attendre explicitement device.wait_until_idle avant/après la région.
Profil actif identique : avant7 passes et allocations+reuses par appel, après6 ;
zéro transfert/compilation chaude, cache32 buffers/1MiB, fences=submissions=passes.

Modèles : source ResidentSteps.sx inchangée, six familles MLP/CNN/RNN/GRU/LSTM/
Transformer, seeds481/482,2 warmups+3 étapes mesurées, AdamW epsilon1e-4.
1700 scalaires complets paramètres/gradients/moments/outputs/step par processus,
tolérance2e-5 déjà fixée. Les cinq familles hors layer_norm servent de contrôle.
Ne pas imposer les anciens comptes Transformer si les deux normalisations
évitent exactement leurs deux add forward par étape (six passes sur trois étapes) ;
le backward add-scalaire était déjà sans passe.
Qualifier les écarts de comptes effectifs, aucune tolérance mémoire élargie.

## Admission inchangée

16 paires avant/après alternées,8 A/A par binaire, ordre des charges alterné.
Temps mural achevé en millisecondes ; CSV/JSON/logs/time/RSS/processus complets.
Delta pairé médian absolu>=5%, supérieur à3 MAD, même signe>=14/16.
A/A invalide si déplacement médian absolu>=5% et supérieur à3 MAD.
Contrôle invalide => indéterminé, sans correction postérieure ni sélection.
Froid, chaud et mémoire séparés ; RSS processus n’est pas la mémoire GPU.
Au moins un bénéfice admis et aucune régression admise non résolue pour retenir.
Même compiler/binaires/hashes/modules/protocole vérifiés avant et après.
Les deux bras Debug/Release passent les valeurs complètes avant les timings.
Tests/builds hors campagne ; corpus global et shader six cibles verts avant admission.
