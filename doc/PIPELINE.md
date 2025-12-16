# 01 · Pipeline Capture → Solver → Pathfinder
Ce document fusionne les anciennes sections capture/vision, storage/solver et actionplanner/action pour offrir une vue unique du pipeline s0 → s6.

## 🔍 CLARIFICATIONS ARCHITECTURALES

Décisions clés validées pour éviter toute ambiguïté :

### Stockage (s3)
- **Représentation unique** : grille sparse dict `{(x,y) → GridCell}` + trois sets (revealed/unresolved/frontier), sans double base.
- **Stratification des cellules** :
  - `raw_state` (vision brute : UNREVEALED, NUMBER_1..8, FLAG, QUESTION, EMPTY, DECOR, EXPLODED),
  - `logical_state` (OPEN_NUMBER / CONFIRMED_MINE / EMPTY / UNREVEALED),
  - `number_value` (1‑8 ou `None`).
- **solver_status** normalisé (`JUST_REVEALED`, `ACTIVE`, `FRONTIER`, `SOLVED`, `NONE`, `OUT_OF_SCOPE`) + `action_status` (SAFE/FLAG/LOOKUP) pour synchroniser pathfinder/action.
- **Stockage passif** : Vision pousse revealed+`JUST_REVEALED`, Solver reclasse ACTIVE/FRONTIER/SOLVED et calcule frontier_add/remove.
- **Export JSON** obligatoire pour compatibilité WebExtension (pas de formats binaires propriétaires).

### Solver (s4)  
- **Étape 0 – Grid Analyzer (s40)** : Vision fournit les cellules `JUST_REVEALED`; cette étape en mémoire (grid_classifier + grid_extractor) reclasse ACTIVE/FRONTIER/SOLVED et construit les vues Frontier/Segmentation pour les solveurs.
- **s42 CSP Solver (OptimizedSolver)** :
  - Exécution exclusive du pipeline CSP via `CspManager.run_with_frontier_reducer()`
  - Extraction des composantes frontier avec filtrage configurable (`ComponentRangeConfig`)
  - Backtracking exact (≤15 variables) + probabilités pondérées
  - Option de bypass complet du filtre de stabilité (`use_stability=False`)
- **s41 Pattern Solver (futur)** : Intégration prévue pour accélérer la résolution des cas triviaux
- **Actions + storage update** : s4 retourne les actions à s5 et met à jour s3 via `StorageUpsert` (`unresolved_remove`, `frontier_add/remove` + métadonnées).
- **Contrat** : le solver consomme `FrontierSlice` + `get_cells(bounds)` et ne modifie s3 qu’au travers de `StorageUpsert`.
- **Centralise solver_status** : gère UNRESOLVED→TO_PROCESS→RESOLVED, la frontière reflète les cellules encore à traiter.

### Flux de données principal
```
s3(revealed + unresolved) ← s2(Vision) → s4(TO_PROCESS + actions) → s5(actions + frontière_anticipée) → s6(exécution + validation) → s2(confirmations) → s3(mise_à_jour_finale)
```

**Note** : Échec S6 = arrêt boucle de jeu (pas de retry complexe).

## 1. Diagramme global (runtime services)

```
┌────────────┐   tuiles canvas   ┌────────────┐   full_grid   ┌────────────┐   matches+bounds   ┌────────────┐   actions   ┌────────────┐
│ s0 Interface│ ────────────────▶│ s1 Capture │──────────────▶│ s2 Vision  │────────────────────▶│ s3 Storage │────────────▶│ s4 Solver  │
└────┬───────┘   JS toDataURL    └────┬───────┘   compositing └────┬───────┘   overlay s2_vision_overlay  └────┬───────┘   overlays s4  └────┬───────┘
     │ viewport plan                 │ meta                    │                       │ frontier         │ actions             │
     ▼                               ▼                         ▼                       ▼                 ▼                     ▼
┌────────────┐   heatmap plan     ┌────────────┐   actions   ┌────────────┐   macro     ┌────────────┐
│ s5 Pathfinder ────────────────▶  │ s6 Action  ─────────────▶│ Jeu (DOM) │◀───────────▶│ s0 Interface│
└────────────┘                    └────────────┘             └────────────┘             └────────────┘
```

## 2. s0 Interface – DOM + coordonnées
- Implémentation actuelle : `src/lib/s0_interface/` (BrowserManager, CoordinateSystem, GameController, ViewportMapper, StatusReader).
- Responsabilité : maintenir le cadre visible, appliquer les ordres de s5 (scroll, zoom, déplacements précis).
- Expose `ViewportState` (offset, zoom, résolution) et accepte `ViewportPlan` (liste d’ordres).
- Interfaces prêtes pour Selenium aujourd’hui / extension Native Messaging demain.

## 3. s1 Capture – Canvas → image (multi-canvases alignés)
- Méthode prioritaire : `canvas.toDataURL('image/png')` (1–2 ms) via JS injecté.
- `ZoneCaptureService.capture_canvas_tiles` orchestre la découverte (`CanvasLocator`) + capture de toutes les tuiles visibles (512×512) et les sauvegarde dans `{base}/s1_raw_canvases/`.
- `compose_from_canvas_tiles` délègue l’assemblage à `src/lib/s1_capture/s12_canvas_compositor.py` : alignement cell_ref, recadrage ceil/floor, assertions stride, recalcul `grid_bounds`, export `full_grid_*.png` vers `{base}/s1_canvas/`.
- Fallback : Chrome DevTools Protocol (`Page.captureScreenshot` + clip) ou Playwright headless.
- Selenium screenshot conservé uniquement en secours (20–40 ms).
- Nettoyage automatique des buffers temporaires pour éviter la saturation disque.

### Schéma capture
```
ViewportState ─▶ execute_script("return canvas.toDataURL()") ─▶ base64 PNG ─▶ decode → bytes
```

## 4. s2 Vision – CenterTemplateMatcher déterministe
- Templates centraux 10×10 générés par `s21_templates_analyzer/template_aggregator.py` (marge 7 px).
- Heuristiques uniformes (`UNIFORM_THRESHOLDS`) : `unrevealed=200`, `empty=25`, `question_mark=200`.
- Discriminant pixel : si une case uniforme n’a pas son anneau blanc, elle bascule `exploded`.
- Priorité & early exit : `unrevealed → exploded → flag → number_1..8 → empty → question_mark`, puis décor en dernier recours.
- Overlays Vision : question_mark affichés en blanc (comme unrevealed), decor en gris/noir, label + pourcentage compactés (font 11). Enregistrement par `VisionOverlay.save` sous `{base}/s2_vision_overlay/{stem}_vision_overlay.png` si overlay activé.
- Tests `tests/test_s2_vision_performance.py` garantissent <0,6 s/screenshot sur machine de référence.

### Diagramme vision
```
PNG bytes ─▶ CenterTemplateMatcher (zone 10×10, ordre prioritaire) ─▶ GridRaw + MatchResult
                                                    └──────▶ overlays_debug/ (vision overlay)
```

## 5. s3 Storage – Grille sparse unique + Trois sets
- Grille sparse dict : représentation unique de vérité pour toutes les cellules jamais vues.
- Trois sets : revealed (optimisation Vision), unresolved (UNRESOLVED→TO_PROCESS→RESOLVED), frontier (frontière analytique).
- Stockage passif : Vision pousse revealed+unresolved, Solver calcule frontier_add/remove.
- Export JSON pour compatibilité WebExtension (pas de formats binaires propriétaires).
- Mise à jour : s3 reçoit les confirmations de s2 après exécution par s6, pas de double mise à jour depuis s4.
- *Implémentation complète : voir `doc/SPECS/s03_STORAGE.md`*

## 6. s4 Solver – Grid Analyzer + CSP (OptimizedSolver)
- **s40 Grid Analyzer** : consomme le snapshot StorageUpsert pour produire les statuts (JUST_REVEALED → ACTIVE/FRONTIER/SOLVED) et les vues Frontier/Segmentation.
- **s42 CSP Solver (OptimizedSolver)** :
  - Exécution exclusive du pipeline CSP via `CspManager.run_with_frontier_reducer()`
  - Extraction des composantes frontier avec filtrage configurable (`ComponentRangeConfig`)
  - Backtracking exact (≤15 variables) + probabilités pondérées
  - Option de bypass complet du filtre de stabilité (`use_stability=False`)
- **s41 Pattern Solver (futur)** : Intégration prévue pour accélérer la résolution des cas triviaux
- **Actions + storage update** : s4 retourne les actions à s5 et met à jour s3 via `StorageUpsert` (`unresolved_remove`, `frontier_add/remove` + métadonnées).
- **Contrat** : le solver consomme `FrontierSlice` + `get_cells(bounds)` et ne modifie s3 qu’au travers de `StorageUpsert`.
- **Centralise solver_status** : gère UNRESOLVED→TO_PROCESS→RESOLVED, la frontière reflète les cellules encore à traiter.
- **Overlays runtime** : `GameSolverServiceV2.solve_from_analysis_to_solver` passe seulement `export_root={base}` aux générateurs. Les modules produisent : `s40_states_overlays/{stem}_{suffix}.png`, `s42_segmentation_overlay/{stem}_segmentation_overlay.png`, `s42_solver_overlay/{stem}_solver_overlay.png`, `s43_csp_combined_overlay/{stem}_combined_solver.png`. Actions reducer + CSP opaques, guesses avec croix blanche. States overlay généré en amont via `FrontierClassifier`.

## 7. s5 Pathfinder – Heatmap & trajets multi-étapes
- Entrées : coordonnées frontière (set), archive pour zones hors écran, état viewport, batch d’actions solver.
- Calcule des attracteurs (barycentre pondéré par distance/densité locale) pour garder un maximum de frontier visible.
- Planifie les déplacements multi-étapes (scrolls successifs, zoom éventuel) et s’assure que les cases révélées hors écran repassent devant la caméra.
- Émet un `ViewportPlan` (liste ordonnée d’ordres) + priorisation des actions solver.

### Schéma heatmap
```
FrontierSlice (coords) ─▶ fonction attracteur(distance, densité calculée) ─▶ heatmap
                                                      │
                                                      └─▶ ordres viewport (dx/dy, zoom)
```

## 8. s6 Action – Exécuteur multi-clics
- Implémentation actuelle : Selenium (ActionChains limités) ou `execute_script` pour cliquer via JS.
- Doit pouvoir chaîner plusieurs actions (ex. flag + clic central), gérer les timing et rapporter succès/erreur.
- Interface unique pour pouvoir remplacer Selenium par une WebExtension (DOM direct) sans toucher aux couches amont.

## 9. Interface Extension & futur
- Architecture recommandée :
  1. Extension (content script) capture le canvas + affiche overlays.
  2. Communication via Native Messaging (JSON) ou WebSocket local avec le backend Python (s2→s6).
  3. Backend exécute capture/vision/solver/actionplanner/action et renvoie instructions.
- Alternative long terme : traduire s3–s6 en Rust/C++ → WebAssembly pour tout embarquer côté extension.
- L’extension réutilisera les overlays PNG/JSON pour visualiser les décisions.

## 10. Résumé des données échangées

| Donnée | Producteur | Consommateur | Description |
| --- | --- | --- | --- |
| `ViewportState` | s0 | s1/s5 | offset, zoom, viewport bounds |
| `CaptureMeta` | s1 | s2/s3 | timestamp, cell size, alignement |
| `GridRaw` | s2 | s3 | grille brute (int codes) |
| `StorageUpsert` | s2/s4 | s3 | revealed/unresolved/frontier updates |
| `FrontierSlice` | s3 | s4/s5 | coordonnées frontière (sans métriques) |
| `ActionBatch` | s4 | s5/s6 | actions sûres (flags/open) |
| `ViewportPlan` | s5 | s0/s6 | déplacement multi-étapes |

---

**À retenir :** garder ce pipeline déterministe, testable et prêt pour une migration extension. Toute modification de couche doit préserver les interfaces décrites ci-dessus.
