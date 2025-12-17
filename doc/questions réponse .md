


Voici les questions critiques pour lever les ambiguïtés d’implémentation, organisées par couche :

## s2 Vision – Frontière et responsabilités

1. **Frontière locale vs topologique** : Dans `matches_to_upsert`, le code calcule une `frontier` locale (voisins UNREVEALED). Est-ce que cela respecte la règle « Vision ne calcule pas la frontière » ou faut-il supprimer ce calcul et laisser le solver tout faire ?

2. **JUST_VISUALIZED** : Vision pose `solver_status = JUST_VISUALIZED` sur les nouvelles observations. Le reclustering (JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED) doit-il avoir lieu :
   - dans `apply_upsert` (côté storage) ?
   - ou au début du solver (avant extraction) ?

## s3 Storage – Invariants et timing

3. **FocusLevel invariants** : Les invariants stricts (ACTIVE ↔ focus_active, FRONTIER ↔ focus_frontier) sont-ils appliqués dans `apply_upsert` ou y a-t-il une validation séparée ? Avez-vous rencontré des erreurs d’incohérence ?

4. **Set `to_visualize`** : Qui écrit exactement dans ce set ? Le solver marque les SAFE en `TO_VISUALIZE`, mais quand est-il nettoyé ? Après la capture suivante ou après le upsert vision ?

## s4 Solver – Repromotion et triggers

5. **Repromotion triggers** : La doc archive dit que la repromotion (REDUCED→TO_REDUCE, PROCESSED→TO_PROCESS) est déclenchée post-vision et post-solver. Dans le code actuel, est-ce bien le cas ? Où se fait cette repromotion ?

6. **TO_VISUALIZE flow** : Le solver écrit `TO_VISUALIZE` sur les SAFE, mais comment s’assurer que ces cellules sont bien re-capturées ? Est-ce géré par `active_set` (qui inclut `to_visualize` dans `get_active`) ?

## Pipeline global – Timing et état

7. **Ordre des opérations** : Dans une itération, l’ordre actuel est : capture → vision → upsert storage → solver → upsert solver → actions. Est-ce que l’upsert solver (qui contient les repromotions) doit être appliqué avant de calculer les actions suivantes ou bien en parallèle ?

8. **Bug rencontré** : Quel était le symptôme du bug qui t’a fait revenir à l’ancienne version ? Était-ce :
   - des cellules qui ne changeaient pas de statut (JUST_VISUALIZED persistant) ?
   - des focus levels qui ne se repromaient pas (zones stériles) ?
   - des actions en boucle sur les mêmes cellules ?

## Overlays et debug

9. **Overlays de cohérence** : Les overlays (states, segmentation) montraient-ils des incohérences entre les sets et les `solver_status` ? Si oui, à quel moment apparaissaient-elles ?

10. **SessionContext** : Les métadonnées de capture (`capture_saved_path`, `bounds`, `stride`) sont-elles bien mises à jour avant chaque analyse vision ? Sinon, cela peut créer des décalages dans les overlays.


# REPONSES
1- ,oui il est necessaire de passer l'entièreté des déterminations d'état topologiques dans state analyzer : vision ne fait que récupérer la capture et known_set étudier l'état réel de chque cellule hors known_set. mapper l'état observé avec l'état logique (et noméro le cas échéant) et, pur les cellules ainsi révélées (donc hors unrevelated), il inscrit le label temporaire JUST_VISUALIZED dans le champ topological state et ensuite il pousse tout ça a grid cells (y compris les unrevelated au cas où elle soient nouvelles) et peut être au solver (sans les unrevelated de préférence, peut importe) la prchaine étape est sensé les igniorer explicitement, je ne sais plus. il ajoute aussi les cellules révélées à known_set pour ne pas les réévaluer à la prochaine itération. c'est tout il me semble

2-Le reclustering (JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED) a 100% lieu dans le state analyzerr !!!! meme pour les mines et flags observés. vision ne discrimine que les unrevelated pour éviter que le solver n'ai à les recathégoriser toutes alors que par défintion, elles n'ont pas changé. la frontière est déterminées par le voisinage d'une active, donc pas besoin d'étudier quoi que ce soit en partant des unrevelated, elles n'aprtent aucune informations. 

3-c'est uen simple sécurité plus ou moins passive à ajouter dans storage !!!!! pour que la strcuture de donnée soit absoluement respectée, on ne sais jamais, il faut faire de mem avec les chiffre et open_number je pense, plus précisement forcer le none en number_value si ce n'est pas open_number en état logique. et assurer aussi que tous les autres états toopologiques, hors active et frontiere n'a que none en focus state ! 

4-le solver procède à la réduction de frontière puis au csp (le cas échéant) et ensuite une fois tous les falg et safe (et guess) trouvés, il les met à disposition de planner et pousse les safe en unrevelated/unrevelated/to_visualize/none (ou ne pousse que to_visualize à la palce de frontière sur cette case, c'est pareil) et les safe en flag/flag/solved/none. puis cleanup fait une passe là dessus et met cleanup à disposition de planner. Planner consommera les to visualize le jour où il y aura le système de navigation et quand une case to vizualize se trouve dans le champ de vision de solver, il va être automatiquement écrasé par JUST_VISUALIZED + states sans besoin de faire quoi que ce soit pour. 

5-pas post vision et post solver, mais post state analyzer !!!! et post solver. c'est à optimized solver d'y faire appelle mais toute cette logique de focus reevaluation est à mettre dans un fichier .py a part dans solver ! et oui je crois que ça a été un gros sujet d'incohérences. 

6-to visualize doit être exclus de active set pour le moment, je crois... pour éviter des faux positifs. mais comme il est exclus de known (tout comme les flag trouvés par le solver d'aillieurs) alors s'il passae dans le champ de vision il sera automatiquement réévalué apr vision. c'est un processus passif, si ce n'est que planner aura à cadrer le champ de vision pour essayer de limiter les indonnues à l'avenir (pour le moment je le fait à la main. )

7- le pipline est sensé être : capture → vision → upsert storage → states analyzer → upsert storage (dont repromotion pour toute voisine de active ou solved ainsi poussée) → solver (exctract frontiere et active, travaille uniquement sur les to_* du lot) → upsert solver (repromotion) → cleanup → actionplanner (récupère directement safe flag guess cleanup) → actions ! le tout en séquentiel, on ne parallélise pas pour le moment. 

8- des problèmes d'overlays sur aoutur des state analyser et repromotion, ce qui est le sujet actuel.

9- je ne sais aps je n'ai pas réussit à les faire focntionner

10- assure toi qu'elles soint bien mises à jour, mais normalement ce n'est pas ça que j'avais touché. 












Questions complémentaires (courtes) pour verrouiller la ré-implémentation :
1) `matches_to_upsert` : veux-tu supprimer totalement la frontière opportuniste (voisins UNREVEALED) ou simplement la laisser en place mais clairement documentée comme non-topologique ?
2) Repromotion : on crée un module dédié (ex. `s4_solver/relevance_manager.py`) appelé (a) après state analyzer, (b) après solver. OK ?
3) TO_VISUALIZE : on l’exclut de `active_set` comme tu le préconises ; confirmes-tu qu’il reste hors `known_set` et sera écrasé par vision dès recapture ?
4) Overlays : souhaites-tu une priorisation pour rétablir les overlays states/segmentation (ex. activer d’abord l’overlay state analyzer, puis CSP) ou est-ce secondaire tant que la logique est corrigée ?
5) SessionContext : on garde l’actuelle mise à jour (`capture_saved_path`, `bounds`, `stride`) avant chaque vision ; besoin d’un log/trace supplémentaire pour vérifier ?


REPONSES 
1- supprime, je ne savais meme pas que c'était là ça. 
2- ok, mais appelle le "focus_actualizer"
3- oui  et oui, de toute manière solver ne gère pas known_set ! 
4- on corrige toute la logique et on varra pour adapter l'overlay state analyser ensuite. le reste est ok. 
5- il faut peut être mettre à jour session context avec le path du historical canvas pour servir de base aux overlays actions combined et states !!!!!














Analyse de cohérence (archive SPECS vs tes réponses dans `doc/questions réponse .md`) :

- **Vision (s2)** : L’archive est cohérente avec tes réponses : vision ne calcule pas la frontière, ne décide pas de topo, marque JUST_VISUALIZED et pousse dans storage. Le seul écart à corriger côté code/doc actuelle : enlever la frontière opportuniste dans `matches_to_upsert` (conforme à ta consigne de suppression).
- **Storage (s3)** : L’archive prévoit bien les invariants (focus_level ↔ solver_status ; number_value=None si pas OPEN_NUMBER ; focus_level=None hors ACTIVE/FRONTIER). Aligné avec tes réponses : il faut s’assurer que `apply_upsert` joue le rôle de pare-feu.
- **Solver (s4)** : L’archive place la topo (JUST_VISUALIZED→ACTIVE/FRONTIER/SOLVED) dans le Grid/State Analyzer et prévoit la gestion de focus/relevances. Cohérent avec tes réponses (reclustering et repromotions dans le state analyzer + post-solver). L’archive ne nomme pas le module, mais créer un `focus_actualizer` dédié respecte l’intention.
- **TO_VISUALIZE** : Archive : écrit par solver pour SAFE, consommé ensuite. Cohérent avec tes réponses (exclure de active_set, hors known_set, reclassé par vision).
- **Pipeline** : Archive : séquentiel capture → vision → storage → solver → actions. Cohérent avec tes réponses qui ajoutent explicitement le passage state analyzer + repromotions entre vision et solver, et après solver.
- **Overlays/SessionContext** : Archive décrit les chemins overlay et SessionContext. Tes réponses ajoutent un besoin : inclure le chemin du “historical canvas” dans SessionContext pour overlays combined/states — ce point n’est pas explicité dans l’archive, donc à documenter/implémenter.

Synthèse : l’archive est globalement cohérente avec tes réponses. Les écarts à traiter sont :
1) Supprimer la frontière opportuniste dans `matches_to_upsert` (non conforme à l’archive et à tes réponses).
2) Documenter/implémenter le `focus_actualizer` (repromotions post state analyzer et post solver).
3) Ajuster SessionContext pour inclure le chemin du “historical canvas” (pour overlays combined/states), point non couvert dans l’archive.












Voici les mises à jour minimales à appliquer dans les SPECS de l’archive avant écrasement, pour coller à tes réponses et aux comparaisons :

1) **s2_VISION.md**
   - Supprimer toute mention/calcul de frontière côté vision. Préciser que `matches_to_upsert` ne calcule plus de frontière opportuniste.
   - Rappeler : vision mappe observation ↔ logique, marque `JUST_VISUALIZED`, pousse les révélées dans `known_set`, ne touche pas à topo/focus/TO_VISUALIZE.
   - Mentionner que le reclustering se fait exclusivement dans le state analyzer (s4).

2) **s3_STORAGE.md**
   - Rendre explicites les invariants imposés par `apply_upsert` :
     - `logical_state != OPEN_NUMBER` ⇒ `number_value = None`
     - Hors ACTIVE/FRONTIER ⇒ `focus_level = None`
     - Cohérence focus_level ↔ solver_status (ACTIVE↔focus_active, FRONTIER↔focus_frontier).
   - Rappeler que solver ne gère pas `known_set`; `TO_VISUALIZE` reste hors `known_set` et peut être exclu de `active_set` si tu confirmes ce choix.
   - Garder l’esprit “pare-feu” : storage valide ces invariants systématiquement.

3) **s4_SOLVER.md**
   - Décrire le pipeline séquentiel explicite : capture → vision → upsert storage → **state analyzer (reclustering + repromotions voisines)** → upsert storage → solver (réduction + CSP sur les `to_*`) → upsert solver (repromotions) → cleanup → planner → actions.
   - Introduire un module nommé **`focus_actualizer`** (ou équivalent) appelé post state analyzer et post solver pour gérer les repromotions (REDUCED→TO_REDUCE, PROCESSED→TO_PROCESS).
   - Préciser que `TO_VISUALIZE` est écrit par le solver pour les SAFE, reste hors `known_set`, et peut être exclu de `active_set` pour éviter les faux positifs ; sera reclassé par vision dès recapture.

4) **ARCHITECTURE.md / PIPELINE.md**
   - Aligner le schéma/steps avec l’étape **state analyzer + focus_actualizer** entre vision et solver, et après solver.
   - Mentionner que la frontière est déterminée côté solver/state analyzer, jamais par vision.

5) **SessionContext (référence)**  
   - Ajouter le besoin d’inclure le chemin du “historical canvas” pour alimenter les overlays combined/states/actions.

6) **CHANGELOG.md**
   - Conserver/restaurer l’entrée du 17/12/2025 (reclustering + repromotions) et toute l’historique archive.

Si tu valides, je peux appliquer ces ajustements directement dans les fichiers de l’archive avant l’écrasement.











Voici les questions clés pour lever les ambiguïtés avant de remplacer la doc actuelle par les SPECS archivés :

## 1) Storage – recalcul des sets dans [apply_upsert](cci:1://file:///c:/Users/robin/Desktop/%28ATELIER%29/7-Code/Bot_demineur/Bot%201000mines-com/src/lib/s3_storage/s31_grid_store.py:24:4-38:9)
- **Performance** : Faut-il un dirty tracking ou un recalcul limité au voisinage des cellules modifiées ? Le code actuel utilise des add/remove explicites ; passer à un recalcul complet à chaque upsert pourrait être coûteux.
- **Portée** : Le voisinage pour `frontier_set` doit-il être 8-directionnel comme actuellement ? Faut-il inclure les diagonales ?
- **known_set** : Doit-il inclure toutes les cellules avec `topological_state != NONE` ou seulement celles avec `solver_status != NONE` ?

## 2) `focus_actualizer` – dépendances et état
- **Stateless vs stateful** : Doit-il retourner un `StorageUpsert` (stateless) ou modifier directement storage (stateful) ?
- **Cycle d’appel** : Éviter la dépendance circulaire entre state analyzer et solver. Faut-il l’appeler via storage controller ou directement ?
- **Portée des repromotions** : Doit-il gérer seulement les repromotions de focus (REDUCED→TO_REDUCE, PROCESSED→TO_PROCESS) ou aussi les reclassements topo ?

## 3) `TO_VISUALIZE` vs `active_set`
- **Impact** : Modifier [get_active()](cci:1://file:///c:/Users/robin/Desktop/%28ATELIER%29/7-Code/Bot_demineur/Bot%201000mines-com/src/lib/s3_storage/s31_grid_store.py:48:4-50:38) pour exclure `TO_VISUALIZE` pourrait casser des services qui s’attendent à les voir.
- **Alternative** : Créer `get_active_excluding_to_visualize()` ou un flag dans [get_active(include_to_visualize=False)](cci:1://file:///c:/Users/robin/Desktop/%28ATELIER%29/7-Code/Bot_demineur/Bot%201000mines-com/src/lib/s3_storage/s31_grid_store.py:48:4-50:38) ?
- **Purge** : Faut-il purger `TO_VISUALIZE` de `active_set` dans [apply_upsert](cci:1://file:///c:/Users/robin/Desktop/%28ATELIER%29/7-Code/Bot_demineur/Bot%201000mines-com/src/lib/s3_storage/s31_grid_store.py:24:4-38:9) ou simplement les exclure à la lecture ?

## 4) `historical_canvas_path` – propagation
- **Stockage** : Dans `SessionContext` uniquement ou aussi dans les snapshots storage ?
- **Initialisation** : Qui renseigne ce chemin ? Capture service après assemblage ou un service dédié ?
- **Overlays** : Faut-il l’ajouter à tous les services d’overlay ou seulement à ceux qui génèrent des images combinées ?

## 5) Solver – désactivation du recalcul frontière
- **Rollback** : Garder le code `compute_frontier_from_cells` commenté avec un flag `USE_FRONTIER_FROM_STORAGE = True` ?
- **Interface** : Le solver doit-il consommer `frontier_set` ou `frontier_to_process` ? Les deux existent.
- **FrontierView** : Doit-on instancier [SolverFrontierView](cci:2://file:///c:/Users/robin/Desktop/%28ATELIER%29/7-Code/Bot_demineur/Bot%201000mines-com/src/lib/s4_solver/s40_states_analyzer/grid_extractor.py:17:0-64:36) directement dans le solver ou via un helper ?

## 6) Migration et rollback
- **Feature toggles** : Ajouter des flags dans `SessionContext` pour basculer entre ancien et nouveau comportement pendant les tests ?
- **Méthodes legacy** : Conserver les anciennes méthodes avec préfixe `_legacy_` commentées ou supprimer purement ?
- **Tests** : Faut-il écrire des tests de non-régression avant la migration ou se baser sur les tests existants ?

Ces points déterminent la complexité de l’implémentation et le risque de régression. Vos réponses permettront d’affiner le plan d’action.






1- non mais on fait juste des diff : storage recois des actualisation e supprime automatiquement les cellules ainsi modifiées des sets concernées, pas besoin de mettr à jours les voisins ou quoi. la cathégorisation en fonction du voisinage je l'ai mis dans solver. pour garder storage passif. passif si ce n'est poru la mise a jours des sets. afin d'assurer la cohérence desdonnées !!!!! dit moi su j'ai rété un truc
peu importe le vosinage pour storage, le frontiere set est calculé par le state analyzer une fosi et puis c'est tout. il l'envoie à storage qui met à jour la db et les set automatiquement. 

2- bin en fait on va passer toute la logique métier du projet en stateless tant qu'à faire pour que storage garantisse la cohérence des états entre db et sets !!
pas de circularité
seulement promotion focus

3- personne ne doit travailler sur les to_visualize au milieus des actives, c'est plu simple de l'exclure
to visualize doit etre purgé de active set ! 

4-uniquement session context
capture service peut rensigner le chemin c'est plus simple ! 
il est la base de tous les overlays solver. mais normalement c'est déjà le cas / pas la base de l'overlay vision qui lui ne peut rien dire en dehors de ce que vision voit ! 

5- non masi on supprime directement en fait. c'est plus simple. 
csp peut consommer frontiere to process a priori pouisque l'entiereté des zones est sensé avoir été promus en to process à chaque changement !!!!! (cf. focus actualizer)
via un helper/factory pour frontierview

6-non que nouveau comportement l'ancien est à purger
on supprime purement, on verra après si ça casse
je ferait les tests à la main 


