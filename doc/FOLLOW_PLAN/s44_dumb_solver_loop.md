---
Description: Boucle Dumb Solver (ACTIVE multi-cycles, double-clic auto-résolution)
---

# S44 – Dumb Solver Loop (itératif, sans CSP jusqu’au blocage)

## 0. Intention
- Exploiter le moteur du jeu comme solver local : **double-clic (ou clic) sur toutes les cases ACTIVE**, plusieurs cycles par itération, pour déclencher l’auto-résolution native (chord).
- Ne pas invoquer le CSP tant que la boucle ACTIVE produit de l’information.
- Limiter la logique à la distinction **ACTIVE vs SOLVED** (pas de frontière/contraintes), pour rester brutal et robuste.

## 1. États et définitions
- `ACTIVE` : OPEN_NUMBER avec au moins un voisin UNREVEALED. Indexé par `active_set` (storage s3).
- `FRONTIER` : UNREVEALED adjacent à une ACTIVE. Indexé par `frontier_set` (storage s3) + `zone_id`/ZoneDB.
- `SOLVED` : OPEN_NUMBER sans voisins UNREVEALED, ou EMPTY/CONFIRMED_MINE.
- `ActiveRelevance` : `TO_TEST / TESTED / STERILE` (porté par GridCell.focus_level, filtrage solver).
- `FrontierRelevance` : `TO_PROCESS / PROCESSED / BLOCKED` (porté par GridCell sur FRONTIER, homogène par zone).
- `productive_click` : un clic (ou double-clic) qui révèle de nouvelles cases ou fait disparaître des ACTIVE.

## 2. Boucle maître (par itération de jeu)
1) Vision → statut des cases
2) Extraire `ACTIVE` via `active_set` (storage) puis filtrer `ActiveRelevance`
3) **Micro-cycles de clics** (2 ou 3)
   - Pour chaque ACTIVE, envoyer un **double-clic** (ou clic chord) pour forcer l’auto-résolution native.
   - L’ordre importe peu : on clique tout.
4) Vision → mise à jour Storage (topologie + sets)
5) Tant qu’il reste des **ACTIVE pertinentes** à cliquer → recommencer des micro-cycles
6) Quand la frontière devient **à (re)traiter** (`frontier_to_process`) → déclencher CSP (s42) sur ces zones (zones `TO_PROCESS` dans ZoneDB)

Paramètres suggérés :
- `MICRO_CYCLES_PER_ITER = 2 ou 3`
- `ACTIVE_CLICK_MODE = double_click` (ou chord si dispo)
- `FRONTIER_TO_PROCESS_THRESHOLD = à calibrer` (volume de frontière à traiter pour justifier le CSP)

## 3. Astuce action planner (auto-résolution par double-clic)
- L’Action Planner peut **recliqueter** les actions SAFE plusieurs fois dans le même batch :
  - Pour chaque cellule marquée **SAFE** par le solver (source de vérité = storage), générer **2 actions** successives sur la même case (double-clic).
  - Objectif : laisser le moteur appliquer les règles “toutes mines flaggées” / “toutes cases fermées égal mines restantes”.
- Même si le solver ne “sait pas” que la case est prête, le double-clic opportuniste déclenche la cascade si les conditions sont réunies.
- En cas d’inaction (pas de reveal), le coût est faible : un double-clic de plus.

## 4. Critères de déclenchement CSP (centré Storage)

Principe : le solver click-based agit sur les **ACTIVE**. Le CSP s’applique quand la frontière est **explicitement marquée à traiter**.

- Le solver maintient (via `FocusLevel`) un statut de pertinence :
  - ACTIVE : `TO_TEST/TESTED/STERILE`
  - FRONTIER : `TO_PROCESS/PROCESSED/BLOCKED`
- Le CSP est déclenché quand :
  - `|frontier_to_process|` dépasse un seuil (ou qu’une zone vient d’être réactivée `BLOCKED → TO_PROCESS`)
  - et/ou quand on n’a plus de `active_to_test` significatif

Note : `delta_revealed`/`delta_active` restent des métriques utiles de debug, mais ne sont pas la règle de vérité pour “passer CSP”.

## 4bis. Focalisation par FocusLevel (pas de focus zone)
- Alignement avec `doc/SPECS/s3_STORAGE.md` : topologie (ACTIVE/FRONTIER/SOLVED/OUT_OF_SCOPE…) + pertinence (TO_TEST/TESTED/STERILE pour ACTIVE, TO_PROCESS/PROCESSED/BLOCKED pour FRONTIER).
- Solver (s4) fournit : `active_to_test` (clics à faire), `active_sterile` (clics “par acquis de conscience” voisins), `frontier_to_process` (pour CSP).
- Action planner (s5) ne gère **pas** l’état, il consomme les sets fournis et clique tout ce qui est ACTIVE, en priorisant les TO_TEST puis les stériles voisines des TO_TEST.
- Pas de focus zone géographique : le périmètre vient du filtrage par pertinence.

## 4ter. Articulation solver / action planner (architecture)
- **Solver (s4)** : décide *quoi* cliquer (sets ACTIVE + pertinence, ordre logique haut→bas éventuellement), et choisit quand passer au CSP (frontier TO_PROCESS importante).
- **Action Planner (s5)** : décide *comment* exécuter (click / double_click / move / timing), à partir des décisions du solver (SAFE/FLAG/GUESS). Ne repositionne pas le viewport pour exécuter ; recadre la vision après exécution si besoin.
- **Boucle GameLoop** : exécute l’itération (capture→vision→storage→solver→planner→action), sans porter la décision “dumb vs CSP”.

### Données minimales à partager
- Sets : `active_to_test`, `active_sterile`, `frontier_to_process` = union des cellules de zones `TO_PROCESS` (ZoneDB s3) vs BLOCKED/PROCESSED.
- Métriques : `delta_revealed`, `delta_active`, volumes `frontier_to_process`.
- Tags topologiques : ACTIVE/FRONTIER/OUT_OF_SCOPE déjà présents dans Storage.

### Flux proposé
1) Vision → Storage (topologie) ; Solver calcule pertinence et sélectionne `active_to_test` (+ stériles voisines) et `frontier_to_process`.
2) Solver (OptimizedSolver) choisit la phase : boucle ACTIVE (click-based) ou CSP (sur `frontier_to_process`).
3) Action Planner → ordonne, choisit le mode (double-clic DOM pour SAFE, clic droit pour FLAG, guess en dernier), et exécute.
4) Exécution → Vision → Storage → Solver met à jour pertinence (TO_TEST→TESTED/STERILE, BLOCKED→TO_PROCESS si zone réactivée).

## 5. Interface modules
- Entrée : snapshot vision (cells + statuses)
- Sortie : batch d’actions (clic gauche/droit ou double-clic) vers s6_action
- Pas d’usage du CSP dans cette phase ; la frontière peut rester un signal (ex: `frontier_to_process`) pour décider quand basculer vers s42.
- Option overlay : marquer les ACTIVE cliquées, cycles et deltas (debug léger).

## 6. Pseudocode (micro-cycles)
```python
for iter in range(max_game_iters):
    grid = vision.read()
    storage = vision_to_storage(grid)

    active_to_test = solver.get_active_to_test(storage)      # filtré par ActiveRelevance=TO_TEST
    frontier_to_process = solver.get_frontier_to_process(storage)  # zones TO_PROCESS (ZoneDB)

    if frontier_to_process and len(frontier_to_process) >= FRONTIER_TO_PROCESS_THRESHOLD:
        solver.run_csp(frontier_to_process)   # s42 CSP sur zones TO_PROCESS
    else:
        for cycle in range(MICRO_CYCLES_PER_ITER):
            safe_cells, flag_cells = solver.get_safe_flag_from_actives(active_to_test)
            planner.execute(safe_cells=safe_cells, flag_cells=flag_cells)
```

## 7. Risques / limites
- Double-clic sur une case non prête : coût minime mais possible clic redondant.
- Nécessité de gérer le timing DOM (peut nécessiter un `delay_between_iterations`).
- Si le jeu interprète mal des double-clics rapides, fallback sur clic simple répété.

## 8. Tâches suivantes
- [ ] Brancher un mode “ACTIVE only” dans GameLoop (bypass CSP tant que non bloqué)
- [ ] Ajouter `double_click` (ou clic répété) dans ActionExecutor / planner pour `CLICK` (safe)
- [ ] Ajouter métriques `delta_revealed` / `delta_active` pour la détection de stagnation
- [ ] Garde-fou : après `K` itérations sans progrès, appeler CSP ou guess contrôlé
