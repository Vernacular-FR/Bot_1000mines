---
description: Planification d’actions et recadrage vision (s5_actionplanner)
---


# PLAN S5 ACTIONPLANNER – Analyse & feuille de route

Ce document aligne s5 sur la structure des plans “V2” (Mission → Architecture → API → Flux → Plan → KPIs → Références).

Point clé V2 : **les actions sont exécutées via JS**, donc elles peuvent s’appliquer hors écran.
Conséquence : s5 **ne gère plus** le viewport pour “pouvoir cliquer” mais pour **cadrer la vision** après exécution.

## 1. Mission

- Recevoir des actions brutes de s4 (`SolverAction`) et produire un plan d’exécution simple pour s6.
- Appliquer une stratégie d’exécution :
  - double-clic DOM sur les `CLICK` (safe) pour déclencher l’auto-résolution du jeu si possible
  - ordre d’exécution cohérent (flags / clicks / guesses + tri interne)
  - shuffle léger optionnel (anti-pattern)
- Produire la liste des cellules **à re-visualiser** après exécution : `TO_VISUALIZE`.
- En fin de cycle : décider d’un **recadrage vision** (quelle zone capturer ensuite), basé sur `TO_VISUALIZE` et/ou des zones jugées pertinentes par le solver.

## 2. Architecture cible

```
 s5_actionplanner/
 ├─ facade.py              # PathfinderAction / PathfinderPlan / Protocol
 ├─ controller.py          # façade s5
 ├─ s50_minimal_planner.py # ordonnancement minimal (implémenté)
 └─ debug/                 # overlays éventuels (futur)
```

Note : la planification “viewport” (au sens déplacement pour exécution) est désormais hors-scope.
La suite consiste plutôt à planifier un cadrage de vision (post-actions) et à exploiter `TO_VISUALIZE`.

## 3. API (facade)

Entrée : `actions: list[SolverAction]`

Sortie : `PathfinderPlan` :
- `actions: list[PathfinderAction]` (exécutable)
- `overlay_path: Optional[str]` (optionnel)

Extension envisagée (futur) :
- exposer aussi un `vision_reframe_request` (bounds à capturer) ou un set de coords `to_visualize`.

## 4. Flux de données

1) **Solver (s4)** → s5 : liste d’actions (CLICK/FLAG/GUESS) et, plus tard, focus levels (PENDING/STERILE, TO_PROCESS/UNSOLVED).
2) **s5 ActionPlanner** :
   - ordonne
   - transforme les safe-click en double-clic DOM (deux actions successives)
   - produit un `PathfinderPlan`
   - marque `TO_VISUALIZE` (besoin de re-capture) côté storage/contexte
3) **s6 ActionExecutor** : exécute bêtement les actions.
4) **Fin de cycle** : s5 propose un recadrage vision (pas de déplacement requis pendant l’exécution).

## 5. Plan d’implémentation

1) **Phase 1 – Double-clic SAFE**
   - Implémenter la génération “double clic” dans le plan pour les actions `CLICK`.
   - Flags inchangés (pas d’astuce associée).
2) **Phase 2 – Ordonnancement**
   - Tri `FLAG` → `CLICK` → `GUESS` + tri interne par valeur/densité si disponible.
   - Shuffle léger paramétrable.
3) **Phase 3 – TO_VISUALIZE & cadrage vision**
   - À chaque action susceptible de révéler des cellules, marquer les zones/cells à re-capturer.
   - Calculer un “best capture window” (bounds) en fin de cycle (futur).
4) **Phase 4 – Overlays**
   - Overlays d’audit : actions planifiées, focus levels, to_visualize.

## 6. Validation & KPIs

- Double-clic SAFE : améliore le taux de révélation “gratuit” sans repasser par une vision intermédiaire.
- Stabilité : l’action planner ne doit pas modifier l’état logique (s3/s4 restent la source).
- Sécurité : aucune action planifiée ne doit dépendre de la position du viewport (actions JS).

## 7. Références

- `doc/SPECS/s3_STORAGE.md`
- `src/lib/s4_solver/s44_dumb_solver/s44_dumb_solver_loop.md`
- `doc/PIPELINE.md`