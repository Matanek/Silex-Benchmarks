from pathlib import Path
import csv, json, math
from statistics import median
root=Path(__file__).resolve().parent
def load(folder):
    rows=list(csv.DictReader((folder/"measurements.csv").open()))
    assert len(rows)==810
    result={}
    for row in rows:
        key=(row["family"],int(row["batch"]),row["backend"],row["phase"])
        process=int(row["process"]);value=float(row["per_iteration_ms"])
        assert math.isfinite(value) and value>=0
        result.setdefault(key,{})[process]=value
        if row["backend"]=="gpu" and row["phase"] not in ["loss_read","step_end_to_end"]:
            assert row["uploads"]==row["downloads"]=="0"
    assert all(set(values)=={1,2,3,4,5} for values in result.values())
    return result

def compare(left,right):
    assert left.keys()==right.keys()
    rows=[]
    for key in sorted(left):
        a,b=left[key],right[key];am,bm=median(a.values()),median(b.values())
        amad=100*median(abs(v-am) for v in a.values())/am if am else None
        bmad=100*median(abs(v-bm) for v in b.values())/bm if bm else None
        gain=100*(1-bm/am) if am else None
        paired=median(100*(1-b[i]/a[i]) for i in a) if all(a.values()) else None
        favourable=sum(b[i]<a[i] for i in a)
        admitted=(gain is not None and amad is not None and bmad is not None and
                  gain>=5 and gain>max(amad,bmad) and favourable>=4)
        rows.append(dict(zip(["family","batch","backend","phase"],key)) |
                    {"reference_ms":am,"candidate_ms":bm,"reference_min":min(a.values()),"reference_max":max(a.values()),
                     "candidate_min":min(b.values()),"candidate_max":max(b.values()),
                     "reference_mad_percent":amad,"candidate_mad_percent":bmad,"gain_percent":gain,
                     "paired_median_gain_percent":paired,"favourable_pairs":favourable,"passes_admission_rule":admitted})
    return rows

rows=compare(load(root/"reference"),load(root/"candidate"))
control=compare(load(root/"NegativeControl/a"),load(root/"NegativeControl/b"))
for filename,values in [("Comparisons.csv",rows),("NegativeControl/Comparisons.csv",control)]:
    with (root/filename).open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(values[0]),lineterminator="\n");writer.writeheader();writer.writerows(values)
def table(backend,phase):
    lines=["| Famille / batch | Référence ms | Candidat ms | Gain des médianes | MAD réf. / cand. | Paires favorables | Règle |",
           "|---|---:|---:|---:|---:|---:|---|"]
    for family in ["mlp","cnn","rnn"]:
        for row in rows:
            if (row["family"],row["backend"],row["phase"])!=(family,backend,phase):continue
            lines.append(f"| {family} / {row['batch']} | {row['reference_ms']:.4f} | {row['candidate_ms']:.4f} | {row['gain_percent']:.1f} % | {row['reference_mad_percent']:.1f} / {row['candidate_mad_percent']:.1f} % | {row['favourable_pairs']}/5 | {'admise' if row['passes_admission_rule'] else 'non admise'} |")
    return "\n".join(lines)

text="""# Adam : suppression des moments nuls recalculés

## Résultat borné

Tensor e742c9a1f55d3dcb4a3d64199607f023e512a193 évite deux calculs temporaires
par paramètre actif après sa première étape Adam. L’initialisation, les formules,
les valeurs et la numérotation des états restent identiques. Ce résultat ne crée
ni API, ni pool, ni regroupement de commandes. Les vérifications et sources sont
liées au [protocole](Protocol.md).

Sur ce M3 Pro / Metal, les pas Adam GPU admis progressent de 5,5 à 9,8 % ; les
pas complets résidents admis progressent de 5,3 à 8,3 %. CNN batch 16 Adam seul
(3,0 %) et RNN batch 16 complet (2,3 %) ne satisfont pas le seuil. Adam CPU
progresse également sur la grille (5,6 à 8,6 %). Aucun gain portable ou gain de
forward/backward n’est revendiqué. La baisse exacte des ressources est commune
aux chemins GPU : deux passes, allocations et fences par paramètre chaud.

## Méthode et règle d’admission

Même machine, même compilateur, mêmes dépendances, même Neural.sx. Cinq paires
indépendantes par famille, ordre des deux binaires alterné et rotation des
familles. Chaque processus vérifie son fonctionnement. Les régions résidentes
ont zéro transfert. Les temps sont muraux synchronisés, pas des timestamps GPU.

La règle fixée avant mesure demande un gain des médianes >=5 %, supérieur aux
MAD relatifs des deux configurations et au moins quatre paires favorables sur
cinq. La règle est un critère d’admission local, pas une preuve statistique de
performance universelle. Le CSV conserve aussi médiane des gains par paire et
min/max ; les RSS sont dans les résumés de chaque configuration. Les phases
Adam mélangent première étape et suivantes, comme le banc de départ.

## Adam GPU

"""+table("gpu","step_adam")+"""

## Étape complète résidente GPU

"""+table("gpu","step_resident")+"""

## Adam CPU

"""+table("cpu","step_adam")+"""

## Contrôle des phases non modifiées et limite de mesure

La première comparaison signale des écarts défavorables de 15,8 % sur le forward
GPU CNN batch 4, 6,7 % CNN batch 16, 5,1 % RNN batch 64 et 15,2 % sur backward
CNN batch 16, ainsi que 6–7 % sur forward/backward CPU RNN batch 4. Leur code
et leurs comptes de passes sont inchangés ; ces faits seuls ne prouvent pas
une origine expérimentale plutôt qu’un effet indirect de configuration.

Un contrôle négatif refait cinq paires **du même binaire de référence** par
famille, avec le même ordre alterné et les mêmes tailles. Les MAD des forwards
GPU CNN 4 montent à 8,2/4,3 %, CNN 16 à 2,6/12,2 %, RNN 64 à 5,0/7,1 % ; le
backward CNN 16 atteint 9,9/2,4 %. Les temps de candidat des phases signalées
restent dans les plages de ce contrôle. Les faibles MAD de cinq échantillons
lors de la première comparaison ne capturent donc pas toute la variabilité.
Cette expérience n’attribue pas individuellement chaque écart : elle interdit
de qualifier ici une accélération ou une non-régression universelle des kernels.

Les phases principales sont plus stables dans ce contrôle : Adam GPU donne des
écarts des médianes de 0,4–5,2 % entre labels identiques (maximum MLP batch 16),
les pas complets de -0,8 à +2,2 %. Les gains retenus restent supérieurs à leur
écart A/A correspondant et aux MAD A/A correspondants. Le contrôle et toutes
ses données sont conservés dans [NegativeControl](NegativeControl/Comparisons.csv),
sans choisir ou retirer des échantillons. Cette conclusion borne le gain à
Adam et aux étapes résidentes admises ; elle ne prétend pas annuler le bruit.

## Compteurs, correction et limites

La garde AdamWarmState prouve 16 passes/allocations/fences à la première étape
par paramètre, puis 14 ; les paramètres sans gradient consomment zéro passe et
leur initialisation différée reste qualifiée. Les pas chauds complets du banc
passent de 111 à 103 passes (MLP/CNN), de 243 à 233 (RNN). Les phases forward,
backward et SGD conservent leurs comptes. Aucun readback caché n’est ajouté.

107 tests passent, dont les oracles différentiels déjà générés, la première
mise à jour des très petits gradients et les moments signés CPU/GPU. Debug et
Release vérifient le banc avant mesures ; le rejet d’état sur un mauvais
placement est préservé. Les logs de qualification sérialisée sont conservés.
Une qualification concurrente a auparavant reçu trois shaders vides ; son
rejeu isolé et toute la suite sérialisée passent. Aucun sample en échec n’est
admis ; cette possible fragilité de concurrence n’est pas diagnostiquée comme
une erreur numérique d’Adam.

Les trois objectifs de la Spec restent ouverts : profil public, pools/commandes,
fusion/plans et float16 pour J3 ; lots/reprise pour J1 ; composition et modèles
modernes pour J2. Les autres cibles ont le même changement de source pure Silex,
mais leurs performances et leurs backends GPU ne sont pas mesurés ici.
"""
(root/"Summary.md").write_text(text)
print("COMPARISON_VALID",len(rows),"rows; A/A",len(control),"rows")
