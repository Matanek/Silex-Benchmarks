# Construction des dépendances GPU — micro-banc

Comparaison Release macOS arm64, Apple M3 Pro, à travail identique. Le
frontend après correction garde les références de classe fournies à init sans
créer préalablement une instance implicite. Initialiseurs explicites et
constructeurs automatiques gardent leurs effets. Tensor Module reste inchangé.

16 paires avant/après à ordre équilibré, huit paires A/A par binaire ;
64 processus, 1280 lignes. Sources, binaires et protocoles figés ;
aucune compilation/test concurrent, aucun sample éliminé. Règle 5 % / 3 MAD /
14 sur 16, deux contrôles A/A valides. Médianes des temps muraux synchronisés ;
les différences appariées ne sont pas un ratio des deux médianes.

| Cas | Avant ms | Après ms | Écart apparié % | MAD de l’écart | Verdict |
|---|---:|---:|---:|---:|---|
| buffer_control / create_release / 1 | 91.903499 | 95.580000 | 1.436 | 5.605 | indéterminé |
| buffer_control / create_release / 256 | 52.588499 | 55.130999 | 5.477 | 6.954 | indéterminé |
| buffer_control / create_release / 4096 | 87.992500 | 91.065000 | 1.526 | 9.632 | indéterminé |
| buffer_control / create_release / 65536 | 90.363002 | 89.176498 | -0.894 | 8.274 | indéterminé |
| buffer_control / existing / 1 | 0.020500 | 0.024000 | 0.000 | 72.813 | indéterminé |
| buffer_control / existing / 256 | 0.015500 | 0.050000 | 0.000 | 31.250 | indéterminé |
| buffer_control / existing / 4096 | 0.032000 | 0.037500 | 14.020 | 86.000 | indéterminé |
| buffer_control / existing / 65536 | 0.052000 | 0.027500 | -17.377 | 55.436 | indéterminé |
| resident / dependent / 1 | 110.098000 | 6.050500 | -94.433 | 0.952 | baisse admise |
| resident / dependent / 256 | 103.474000 | 7.305000 | -92.896 | 2.303 | baisse admise |
| resident / dependent / 4096 | 105.464997 | 6.886000 | -93.146 | 1.058 | baisse admise |
| resident / dependent / 65536 | 102.699997 | 7.885500 | -92.693 | 1.210 | baisse admise |
| resident / replace / 1 | 102.336500 | 11.023000 | -89.523 | 1.341 | baisse admise |
| resident / replace / 256 | 105.467500 | 9.227000 | -91.457 | 1.088 | baisse admise |
| resident / replace / 4096 | 104.586000 | 9.047000 | -91.424 | 0.431 | baisse admise |
| resident / replace / 65536 | 106.432000 | 10.444000 | -89.714 | 0.779 | baisse admise |
| resident / retain / 1 | 98.283500 | 4.183500 | -95.372 | 0.868 | baisse admise |
| resident / retain / 256 | 104.751997 | 4.112000 | -95.626 | 1.191 | baisse admise |
| resident / retain / 4096 | 97.217502 | 4.352000 | -95.424 | 1.358 | baisse admise |
| resident / retain / 65536 | 106.936495 | 4.944000 | -94.885 | 1.146 | baisse admise |

Tous les contrôles A/A sont valides ; tous leurs écarts et les plages
restent dans Summary.json. Les raw logs et fichiers time conservent chaque
processus et son RSS. La baisse de temps ne prouve pas une réduction de VRAM.

## Compteurs et mémoire

Les douze cas résidents conservent exactement 64 allocations/passes/
soumissions/fences et zéro transfert. Sorties analytiques 2 ou 65 vérifiées ;
tous les buffers libérés après usage. Les huit contrôles GFX ne montrent
aucun signal. Aucun pool ni regroupement de commandes n’est démontré.
RSS processus before : médiane 7.62348e+07 bytes, MAD 57344, plage 76103680–76480512.
RSS processus after : médiane 7.67345e+07 bytes, MAD 212992, plage 76382208–77922304.

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
python3 Silex-Benchmarks/Sources/TensorStableCompute/Baselines/2026-10-05-macos-arm64-constructor-dependencies/Run.py micro --before-binary /absolute/before-bin \
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
