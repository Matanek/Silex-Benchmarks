# Attribution des ressources eager — résultat

macOS26.6.2 / Apple M3 Pro / arm64 / Metal, Silex9ba34c2, Tensor
d6cff04, banc5fea4a7, Release. Configuration.json épingle les sept dépôts,
les empreintes de Module, le banc, le compilateur et le binaire. Aucun build
ou test concurrent. Debug/Release --verify verts, sortie/compteurs/libérations.

32 processus,640 timings :16 comparaisons des bras, huit paires A/A, ordres
alternés, aucun échantillon retiré. Warmup quatre opérations hors timing ;
64add résidents, attente finale, aucune lecture dans la région. Les résultats
analytiques sont vérifiés après chronométrage. Voir Protocol.md, Measurements.csv,
Rows.json et Runs.json ; tous les logs et temps/RSS sont conservés.

## Durée de vie des mêmes résultats

| Éléments f32 | Replace ms/64 | Retain ms/64 | Δ apparié médian | MAD Δ | Plage Δ | Verdict |
|---|---:|---:|---:|---:|---:|---|
| 1 | 102.551 | 103.784 | +1.65% | 5.50% | -15.37 à +70.29% | Indéterminé |
| 256 | 101.268 | 101.289 | -0.68% | 7.01% | -11.27 à +20.85% | Indéterminé |
| 4096 | 104.149 | 103.091 | -1.03% | 3.83% | -20.00 à +4.89% | Indéterminé |
| 65536 | 108.396 | 103.115 | -1.92% | 4.94% | -14.01 à +7.72% | Indéterminé |

Aucune case ne franchit la règle fixée : médiane≥5%, supérieure3MAD,
direction dans14/16paires et contrôle valide. Les contrôles A/A ne franchissent
pas leurs seuils ; cela ne transforme pas un résultat indéterminé en parité.
Replace et retain conservent64allocations/passes/soumissions/fences, sortie2 et
aucun transfert. Retain garde jusqu’à64résultats, maximum16Mio pour65536 ;
aucune recommandation de retenir les sorties arbitrairement en production.
La chaîne dépendante donne65, mêmes64opérations ; ses chiffres distincts dans
Summary.json ne sont pas un comparateur numériquement identique.

## Contrôle création/libération GFX

| Éléments | Création/libération ms/4096 | Buffer existant ms/4096 | µs par appel création/libération | Projection64appels ms |
|---|---:|---:|---:|---:|
| 1 | 94.359 | 0.050 | 23.04 | 1.474 |
| 256 | 53.939 | 0.015 | 13.17 | 0.843 |
| 4096 | 89.291 | 0.051 | 21.80 | 1.395 |
| 65536 | 88.381 | 0.051 | 21.58 | 1.381 |

Ce contrôle montre un signal sur l’enveloppe des appels GFX, sans dispatch :
checksum identique, buffer existant déjà créé. La projection linéaire64appels
est une estimation de diagnostic (≈0.8–1.5ms), pas une attribution causale
exacte aux ≈100ms du parcours Tensor. Elle n’inclut pas le suivi Tensor,
la soumission, les uniforms ou le travail shader. Tensor.Profile ne compte
pas les buffers GFX externes ; aucune taille physique Metal/VRAM revendiquée.
Le contrôle de lecture peut être fortement optimisé par le compilateur ;
le résultat ne démontre ni le bénéfice ni la sûreté d’un pool Tensor.

## Suite justifiée

Les deux explications initiales ne suffisent pas à identifier le coût dominant.
Pas de pool introduit. Départager préparation CPU (métadonnées et appels) et
soumission GPU par contrôles réduits, avant un mécanisme privé borné. Cette
réorientation conserve ressources/commandes, fusion/plans et précision du
contrat ; J3 n’est pas clos. Les mesures n’attestent que cet hôte et ces commits.

Summarize.py régénère Summary.json depuis les640lignes ; le pilote brut
CampaignDriver.py.txt conserve les commandes exactes. Pour reproduire, partir
d’un nouveau répertoire, compiler depuis la racine du groupe et fixer les
versions/empreintes ; ne pas mélanger des échantillons de nouveaux candidats.
