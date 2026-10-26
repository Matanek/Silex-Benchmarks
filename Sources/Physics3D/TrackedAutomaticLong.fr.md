# Conduite chenillée prolongée

Depuis la racine du groupe de travail :

```sh
python3 Silex-Benchmarks/Sources/Physics3D/TrackedAutomaticLongRun.py --mode both
```

Le parcours dure20s :2s de stabilisation,8s de gaz à80%,10s de frein à4%.
Quatre cas comparent marche avant, arrière, absence de friction et contrôle
sans gravité. Pas60/120Hz, un sous-pas,48itérations de vitesse et4de position
dans les deux moteurs. Le châssis100kg porte six roues rayon et deux bandesI2,
rayon0,3m ; moteur15Nm et boîte1/2/3/2/1/point mort. Déplacement chargé environ
176m et pointe proche25m/s. Aucune correction de cap n’est appliquée.

Le profil48/4 est explicite. La contre-épreuve initiale12/4 reste non qualifiée :
environ7,04cm de différence entre moteurs, au-delà du budget5cm. L’étude de
convergence12/24/48/96 a ramené la dérive latérale absolue des deux moteurs à
moins de0,14mm au profil48. Ce résultat ne modifie pas le défaut du monde et
ne garantit pas ce parcours avec12itérations. Les historiques courts restent
inchangés. Le SDK n’est pas modifié pour obtenir cette trace.

La référence est Jolt e77f175595e64cb44218cc9d9d56fc365ad0e36a avec la variante
[stable-brakes](TrackedBrakeOracle.py) explicite : bornes symétriques de friction
statique accumulée, original et bibliothèques conservés. Aucun autre patch.
Le rapport enregistre commandes, sources, empreintes et configuration.

Les budgets de parité restent5cm/0,1m/s/0,02rad/0,15rad/s ; rapports à50ms,
fenêtres1s20N/30Nm/20N/0,1rad. Le témoin vérifie aussi les bilans d’impulsion,
rotors, normales, contacts et reprise sur six appuis au repos. Les deux cas
chargés ont un contrôle absolu supplémentaire5mm/0,0001rad. Les14408états par
moteur/mode et121corruptions sont contrôlés ; sorties D/R identiques par moteur.

Les traces brutes et le rapport `tracked-automatic-long-qualification.json`
sont produits dans le cache racine `.silex/physics3d-oracle/`. Ce protocole
ne qualifie pas les virages à grande vitesse, terrains ou contacts volumiques.
