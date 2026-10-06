# Protocole figé de la première gate précision

Le smoke observe 15 entrées float32 représentées par bits indépendants et leurs
conversions half : +0/−0, 1, −2, normal minimal, sous-normal minimal, moitié du
sous-normal minimal, maximum fini, premier arrondi en overflow, 1000,25, arrondi
à mi-distance autour de 1, valeur half suivante, ±Inf et NaN. Oracle Python
`struct.pack('>e')`, erreurs overflow converties en Inf signé selon le témoin
fixé ; NaN comparé par classification, pas par payload. Bits et retour float32
figés dans Artifacts/Task17-Conversion-Oracle.json avant exécution GPU.

HLSL public sur device réel : f32tof16/f16tof32, casts half/min16float et
addition conservée dans chacun des deux types. L’addition 1000+0,25 distingue
une précision half qui arrondit à 1000 d’un calcul float32 à 1000,25.
Le shader MSL réellement produit est conservé et inspecté pour distinguer
conversion packée, promotion et arithmétique. Aucun timing, support matériel,
convergence ou API Tensor n’est inféré de ce premier smoke.

Debug et Release, Metal validation, attente finale, lecture des valeurs et
destruction des ressources. Cette première preuve décide de la prochaine
expérience ; elle ne déclare pas encore la gate du contrat positive ou négative.


## Raffinement de l’addition avant conclusion matérielle

Le shader par défaut confirme des casts promus et des conversions réelles,
mais l’addition constante a été pliée par le compilateur. Conserver cette preuve
historique ; pour observer une addition exécutée, lire maintenant le zéro depuis
le buffer GPU puis ajouter 1000 et 0,25, mêmes bits attendus. Le nouveau shader
est compilé/exécuté Debug et Release. Aucune nouvelle tolérance ou conclusion.


## Contrôle natif pour départager matériel et traduction HLSL

Le SDK Shadercross installé ne propose pas d’option native16 dans son CLI/header,
et sa compilation explicite `float16_t` rejette ce type. La promotion dynamique
est prouvée en Debug/Release et dans le MSL généré. Avant toute conclusion,
un contrôle via l’API publique GPU ShaderFormat.msl réalise les mêmes conversions
et l’addition dynamique en vrai half Metal. Ce contrôle ne contourne aucune API
Tensor et ne qualifie pas le chemin HLSL : il permet de localiser la frontière.
Aucune mesure de vitesse, matmul, convergence ou mixed precision n’est acquise.
