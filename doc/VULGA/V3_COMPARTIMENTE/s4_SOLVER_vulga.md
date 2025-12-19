

## 19 décembre 2025 — Retour au concret : la topologie rebranchée dans le pipeline minimal

Sur le pipeline “minimal” (services simplifiés), j’ai retrouvé exactement le même symptôme qu’en V2 historique :

- la vision détecte parfaitement des nombres/vides/drapeaux,
- mais le solver n’a aucune action, parce que `active_set/frontier_set` restent vides.

La cause est structurante :
- La vision produit une observation brute (cases vues),
- mais **personne ne dérive la topologie** avant d’interroger le solver.

Donc j’ai réintroduit une **étape 0** explicite côté solver :

- `StateAnalyzer` (classification topologique) :
  - `OPEN_NUMBER` + voisin `UNREVEALED` → `ACTIVE`
  - `UNREVEALED` adjacent à une `ACTIVE` → `FRONTIER`
  - le reste → `SOLVED/UNREVEALED`

Et surtout :

- cette classification est **écrite dans storage** juste après la vision,
- puis seulement après on extrait `active_set/frontier_set` pour alimenter `solve()`.

Ce qui reste à faire (pour retomber sur le design complet décrit dans les analyses) :

- **FocusActualizer** : repromotions (réveiller les voisins) après reclustering post-vision et après les décisions solver.
- **TO_VISUALIZE** : quand une cellule est annoncée `SAFE`, elle doit passer en `TO_VISUALIZE` pour forcer la recapture.
- **Invariants storage** : centraliser une validation stricte (cohérence `solver_status` / focus levels / `number_value`).


Donc j’ai rebranché la **dérivation topologique** juste après la vision (avant d’appeler le solveur CSP).

### Ce qui se passe réellement maintenant (pipeline runtime)

1. **Vision → Storage**
   - chaque cellule vue est stockée avec un `raw_state` (symbole vision) et un `logical_state` (normalisé)
   - le `solver_status` initial est `JUST_VISUALIZED`

2. **Pipeline 1 (post-vision) : StatusAnalyzer + FocusActualizer**
   - `StatusAnalyzer` reclasse les `JUST_VISUALIZED` en :
     - `ACTIVE` : `OPEN_NUMBER` avec au moins une voisine `UNREVEALED`
     - `FRONTIER` : `UNREVEALED` adjacente à une `ACTIVE`
     - `SOLVED` : `EMPTY` et `OPEN_NUMBER` sans inconnues autour
     - `MINE` : `CONFIRMED_MINE`
   - `FocusActualizer` “réveille” les voisines pertinentes (focus `TO_REDUCE/TO_PROCESS`)
   - un overlay `status` est produit pour contrôler visuellement cette topo

3. **Solver CSP + reducer (CspManager)**
   - produit des décisions `SAFE/FLAG` (et éventuellement `GUESS`)

4. **Pipeline 2 (post-solver) : ActionMapper**
   - `FLAG` devient une mine confirmée (`logical_state=CONFIRMED_MINE`, `solver_status=MINE`)
   - `SAFE/GUESS` deviennent `TO_VISUALIZE` (on attend la recapture vision pour confirmer)
   - rétrogradation du focus sur les anciennes `ACTIVE/FRONTIER` non résolues
   - overlay combiné : zones + symboles (croix/rond blancs)

5. **Sweep (post-solver bonus)**
   - génération de clics `SAFE` bonus uniquement sur les voisines `ACTIVE` des cellules `TO_VISUALIZE`
   - objectif : rafraîchir/accélérer la propagation d’information sans “inventer” de nouvelles déductions

### 20 décembre 2025 — Snapshot runtime unique (SolverRuntime)

- Le solver travaille maintenant sur un **snapshot mutable interne** partagé entre ses sous-modules (post-vision → CSP → post-solver → sweep).
- Chaque sous-module renvoie un `StorageUpsert` appliqué immédiatement au runtime ; le **storage réel n’est mis à jour qu’une seule fois** à la fin avec les cellules modifiées (dirty flags).
- Résultat : plus de resnapshot intermédiaire, état cohérent pour tous les sous-modules, et overlays produits à partir du snapshot final.
✔ **Robuste** : snapshot cohérent tout au long du solve  
✔ **Optimisé** : zéro copies massives, une seule mise à jour storage  
✔ **Pragmatique** : aucune refonte d'API, modules existants inchangés  
✔ **Lisible** : pipeline clair et maintenable  
✔ **Extensible** : dirty flags prêts pour optimisations futures  
