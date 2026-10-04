# Protocole du profil public

Référence : binaire Release issu de Tensor `e742c9a` (même Module que la baseline
locale acceptée `27f6cae`), benchmark `Neural.sx` avant ajout des options de profil.
Candidat : sources Task-02 instrumentées, même compilateur et dépendances.
La configuration conserve empreintes des binaires et sources, versions et heads.

Cinq triplets par famille MLP/CNN/RNN, ordre référence/inactif/actif alterné et
rotation des familles. Variantes inactives/actives du même binaire candidat ;
seules la construction du profil et son observation après chronométrage diffèrent.
Les modèles, seeds, grilles, étapes et attente explicite restent identiques.
Pas de build/test parallèle aux mesures. Temps et RSS par processus conservés.
Contrôle A/A : cinq paires supplémentaires du même binaire inactif par famille,
avec rotation et alternance ; son bruit borne l’interprétation des écarts.

Question : le suivi permanent des buffers et les incréments d’une période active
modifient-ils les valeurs/commandes ou les durées des parcours neuronaux ?
Les 54 lignes chronométrées/processus et leurs uploads/downloads/passes doivent
correspondre ; les sections résidentes ne transfèrent pas. Les profils doivent
produire six instantanés/processus et respecter passes=bindings=dispatches et
soumissions=fences. La suite CPU/GPU qualifie indépendamment les valeurs.

Rapporter, par phase/backend/famille/batch, médianes, min/max, MAD et écarts
appariés. Un écart >=5% dépassant les MAD et favorable dans au moins 4/5 paires
appelle une inspection avec le contrôle A/A ; ne pas présenter le bruit comme un
gain ou un coût garanti. Aucun GPU-time implicite, aucune extrapolation à un
nombre arbitraire de profils ou à une autre plateforme.
