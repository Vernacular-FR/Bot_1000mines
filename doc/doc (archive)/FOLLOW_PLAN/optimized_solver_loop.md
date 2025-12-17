Description: Boucle bypass CSP (réduction systématique, double-clic SAFE planner)

# S44 – Boucle bypass CSP (itératif, réduction systématique puis CSP si besoin)

## 0. Intention
- Exploiter un pipeline simple : **réduction de frontière déterministe** (très rapide) puis **CSP uniquement si nécessaire**.
- Quand la réduction produit suffisamment d’actions, **on contourne le CSP** et on passe directement au planner.
- Le planner applique ensuite ses heuristiques d’exécution (double-clic sur les SAFE, “ménage” local), puis on relance une itération.

## 1. États et définitions
- `ACTIVE` : OPEN_NUMBER avec au moins un voisin UNREVEALED. Indexé par `active_set` (storage s3).
- `FRONTIER` : UNREVEALED adjacent à une ACTIVE. Indexé par `frontier_set` (storage s3) + `zone_id`/ZoneDB.
- `SOLVED` : OPEN_NUMBER sans voisins UNREVEALED, ou EMPTY/CONFIRMED_MINE.
- `ActiveRelevance` : `TO_REDUCE / REDUCED` (porté par GridCell, filtrage solver pour la réduction de frontière).
- `FrontierRelevance` : `TO_PROCESS / PROCESSED` (porté par GridCell sur FRONTIER, homogène par zone).
- `productive_click` : un clic (ou double-clic) qui révèle de nouvelles cases ou fait disparaître des ACTIVE.

## 2. Boucle maître (par itération de jeu)
1) Vision → statut des cases → Storage (sets + topologie)
2) **Réduction de frontière déterministe** (toujours) :
   - produit des actions sûres (`FLAG`/`CLICK`) à partir des contraintes locales (type “frontier reducer”)
3) Décision (pilotée par s4) :
   - si la réduction fournit **assez d’actions** → bypass CSP et envoyer au planner
   - sinon → exécuter CSP sur les zones `TO_PROCESS` (frontière “fraîche”) puis envoyer au planner
   - `allow_guess` (bool, défaut ON) : autorise l’émission d’une GUESS si aucune action sûre
4) Action Planner :
   - exécute les flags
   - exécute les safe en double-clic (heuristique)
   - exécute les cleanup_actions (bonus) si `enable_cleanup` est ON côté solver (clic simple)
   - peut exécuter un “ménage” local (heuristique) autour des SAFE / ACTIVE à réduire
5) Vision → mise à jour Storage, et on recommence

Paramètres suggérés :
- `BYPASS_CSP_THRESHOLD = à calibrer` (critère de “assez d’actions” sur la réduction)
- `CSP_THRESHOLD = à calibrer` (volume/qualité de `TO_PROCESS` pour justifier CSP)

## 3. Astuce action planner (auto-résolution par double-clic)
- L’Action Planner peut **recliqueter** les actions SAFE plusieurs fois dans le même batch :
  - Pour chaque cellule marquée **SAFE** par le solver (source de vérité = storage), générer **2 actions** successives sur la même case (double-clic).
  - Objectif : laisser le moteur appliquer les règles “toutes mines flaggées” / “toutes cases fermées égal mines restantes”.
- Même si le solver ne “sait pas” que la case est prête, le double-clic opportuniste déclenche la cascade si les conditions sont réunies.
- En cas d’inaction (pas de reveal), le coût est faible : un double-clic de plus.

## 4. Critères de déclenchement CSP (centré Storage)

Principe : la réduction est systématique. Le CSP n’est appelé que si la réduction n’apporte pas suffisamment de matière.

Note : le solver réactive de façon déterministe les cellules/zonages impactés :
- si un voisinage a changé et que la cellule est **ACTIVE** → `TO_REDUCE`
- si une zone a changé et que la cellule est **FRONTIER** → `TO_PROCESS` (propagé à la zone)

- Le solver maintient (via `FocusLevel`) un statut de pertinence :
  - ACTIVE : `TO_REDUCE/REDUCED`
  - FRONTIER : `TO_PROCESS/PROCESSED`
- Le CSP est déclenché quand :
  - la réduction de frontière ne produit pas assez d’actions
  - et que la frontière contient suffisamment de zones `TO_PROCESS`

Note : `delta_revealed`/`delta_active` restent des métriques utiles de debug, mais ne sont pas la règle de vérité pour “passer CSP”.

## 4bis. Focalisation par FocusLevel (pas de focus zone)
- Alignement avec `doc/SPECS/s3_STORAGE.md` : topologie (ACTIVE/FRONTIER/SOLVED/OUT_OF_SCOPE…) + pertinence (TO_REDUCE/REDUCED pour ACTIVE, TO_PROCESS/PROCESSED pour FRONTIER).
- Solver (s4) fournit : actions déterministes (réduction, et CSP si exécuté), et met à jour les focus levels.
- Action planner (s5) ne gère **pas** l’état ; il applique ses heuristiques d’exécution sur les actions reçues (double-clic SAFE, etc.).
- Pas de focus zone géographique : le périmètre vient du filtrage par pertinence.

## 4ter. Articulation solver / action planner (architecture)
- **Solver (s4)** : décide *quoi* cliquer (sets ACTIVE + pertinence, ordre logique haut→bas éventuellement), et choisit quand passer au CSP (frontier TO_PROCESS importante).
- **Action Planner (s5)** : décide *comment* exécuter (click / double_click / move / timing), à partir des décisions du solver (SAFE/FLAG/GUESS). Ne repositionne pas le viewport pour exécuter ; recadre la vision après exécution si besoin.
- **Boucle GameLoop** : exécute l’itération (capture→vision→storage→solver→planner→action), sans porter la décision “dumb vs CSP”.

### Données minimales à partager
- Sets : `frontier_to_process` = union des cellules de zones `TO_PROCESS` (ZoneDB s3) vs `PROCESSED`.
- Sets s3 : `active_set = ACTIVE ∪ TO_VISUALIZE`, `to_visualize` pour cadrage vision.
- Métriques : `delta_revealed`, `delta_active`, volumes `frontier_to_process`.
- Tags topologiques : ACTIVE/FRONTIER/OUT_OF_SCOPE déjà présents dans Storage.

### Flux proposé
1) Vision → Storage (topologie) ; Solver calcule pertinence (`TO_REDUCE/REDUCED`, `TO_PROCESS/PROCESSED`) et les ensembles dérivés utiles (ex: `frontier_to_process`).
2) Solver (OptimizedSolver) exécute la réduction de frontière (toujours), et décide ensuite de lancer ou non le CSP.
3) Action Planner → ordonne, choisit le mode (double-clic DOM pour SAFE, clic droit pour FLAG, guess en dernier), exécute, puis applique les cleanup_actions en bonus si fournis.
4) Solver marque `TO_VISUALIZE` pour les cellules annoncées SAFE (amenées à changer, potentiellement hors champ), puis Vision recapture.
5) Action Planner consomme `TO_VISUALIZE` pour cadrer la re-capture, puis Vision → Storage → Solver met à jour pertinence (TO_REDUCE↔REDUCED, PROCESSED→TO_PROCESS si zone réactivée).

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

    reducer_actions = solver.run_frontier_reducer(storage)
    if solver.should_bypass_csp(reducer_actions):
        planner.execute(reducer_actions)
        continue

    frontier_to_process = solver.get_frontier_to_process(storage)
    csp_actions = solver.run_csp(frontier_to_process)
    planner.execute(reducer_actions + csp_actions)
```

## 7. Risques / limites
- Double-clic sur une case non prête : coût minime mais possible clic redondant.
- Nécessité de gérer le timing DOM (peut nécessiter un `delay_between_iterations`).
- Si le jeu interprète mal des double-clics rapides, fallback sur clic simple répété.

## 8. Tâches suivantes
- [ ] Définir `should_bypass_csp()` (critère simple puis raffinable)
- [ ] Brancher la réduction de frontière systématique avant CSP
- [ ] Stabiliser l’heuristique planner (double-clic SAFE + “ménage” local)
- [ ] Ajouter métriques `delta_revealed` / `delta_active` (debug + calibration seuils)
