# Construction des dépendances GPU — six modèles résidents

Comparaison Release macOS arm64, Apple M3 Pro, à travail identique. Le
frontend après correction garde les références de classe fournies à init sans
créer préalablement une instance implicite. Initialiseurs explicites et
constructeurs automatiques gardent leurs effets. Tensor Module reste inchangé.

16 paires avant/après à ordre équilibré, huit paires A/A par binaire ;
64 processus, 384 lignes. Sources, binaires et protocoles figés ;
aucune compilation/test concurrent, aucun sample éliminé. Règle 5 % / 3 MAD /
14 sur 16, deux contrôles A/A valides. Médianes des temps muraux synchronisés ;
les différences appariées ne sont pas un ratio des deux médianes.

| Cas | Avant ms | Après ms | Écart apparié % | MAD de l’écart | Verdict |
|---|---:|---:|---:|---:|---|
| cnn | 99.019500 | 9.697000 | -90.244 | 0.124 | baisse admise |
| gru | 320.576990 | 28.565000 | -91.031 | 0.301 | baisse admise |
| lstm | 304.886500 | 28.195500 | -90.782 | 0.179 | baisse admise |
| mlp | 98.690994 | 8.960000 | -91.035 | 0.250 | baisse admise |
| rnn | 142.473000 | 13.240500 | -90.779 | 0.251 | baisse admise |
| transformer | 412.954000 | 39.781000 | -90.510 | 0.126 | baisse admise |

Tous les contrôles A/A sont valides ; tous leurs écarts et les plages
restent dans Summary.json. Les raw logs et fichiers time conservent chaque
processus et son RSS. La baisse de temps ne prouve pas une réduction de VRAM.

## Compteurs et mémoire

1 700 observations par processus, 108 800 au total : sorties, valeurs des
paramètres, gradients et deux moments AdamW, compteur exactement cinq.
Tolérance 2e-5, epsilon explicitement 1e-4 avant mesures ; voir Protocol.md
et le diagnostic de biais de clés, identique sur les deux compilateurs.
Aucun gain au réglage epsilon par défaut n’est revendiqué.

| Famille | Passes | Soumissions | Allocations | Pic bytes avant | Pic bytes après |
|---|---:|---:|---:|---:|---:|
| cnn | 327 | 327 | 327 | 1792 | 2928 |
| gru | 888 | 996 | 1032 | 3764 | 7368 |
| lstm | 900 | 972 | 990 | 4160 | 8524 |
| mlp | 321 | 321 | 321 | 744 | 1736 |
| rnn | 474 | 474 | 474 | 1016 | 2130 |
| transformer | 1353 | 1365 | 1365 | 7984 | 16972 |

Les pics demandés augmentent : le CPU soumet plus vite, donc davantage
d’ancêtres peuvent rester retenus jusqu’aux fences. Les bornes avec ancêtres
retenus, l’absence de transferts cachés et la libération complète après
destruction passent dans les tests de durée de vie. Les releases de période
peuvent inclure des buffers nés au warmup ; elles ne se déduisent pas du seul
nombre d’allocations de cette période. Aucune fuite ni baisse de mémoire
n’est inférée du temps ou du RSS.
RSS processus before : médiane 7.59562e+07 bytes, MAD 73728, plage 75792384–76316672.
RSS processus after : médiane 7.88808e+07 bytes, MAD 335872, plage 77987840–79986688.

## Provenance et reproduction

Configuration.json conserve les sept HEADs et les empreintes des deux
compilateurs, binaires, sources et protocole. Le compilateur baseline est
`9ba34c2415b1e1cd33bc9b3c69c16c3247d92957`, le candidat
`d0834c70c46244c4775f3711aaf1e5d9f0e8bb8d`. Le HEAD des sources du groupe
ne remplace pas l’identité du compilateur utilisé pour le bras baseline.

Qualifier les deux binaires en Debug/Release avec --verify avant toute
nouvelle campagne. OriginalQualification.py et OriginalCampaign.py sont des
recettes historiques du groupe Spec ; leurs chemins Artifacts demandent une
adaptation explicite. Run.py reçoit des chemins explicites de binaires,
compilateurs, protocole et résultat, depuis la racine du groupe workspace :

```sh
python3 Silex-Benchmarks/Sources/TensorStableCompute/Baselines/2026-10-05-macos-arm64-resident-constructor-dependencies/Run.py models --before-binary /absolute/before-bin \
  --after-binary /absolute/after-bin --before-compiler /absolute/before-cli \
  --after-compiler /absolute/after-cli --before-commit <full-before-sha> \
  --protocol /absolute/Protocol.md --out /absolute/new-campaign
```

Les dépôts doivent être propres, les binaires construits depuis les sources
enregistrées et tous les autres builds/tests arrêtés. Ne pas mélanger des
machines ou réglages différents. Rejouer la preuve scellée avec
`python3 Verify.py` ; elle vérifie empreintes, CSV, statistiques et, pour
les modèles, chaque observation scalaire. Binaires et caches restent hors Git.
Aucune disponibilité publiée ni performance hors de ce M3 Pro n’est affirmée.
