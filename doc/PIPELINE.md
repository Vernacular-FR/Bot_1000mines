# 01 · Pipeline Capture → Solver → Pathfinder

Ce document fusionne les anciennes sections capture/vision, storage/solver et pathfinder/action pour offrir une vue unique du pipeline s0 → s6.

## 🔍 CLARIFICATIONS ARCHITECTURALES

Décisions clés validées pour éviter toute ambiguïté :

### Stockage (s3)
- **Représentation unique** : grille NumPy infinie en RAM + frontière compacte (set), sans double base archive/frontière.
- **Export JSON** obligatoire pour compatibilité WebExtension (pas de formats binaires propriétaires).
- **NumPy interne** pour performance, JSON uniquement pour export/import.
- **Mise à jour frontière** : uniquement par Vision (batch) et Actioner (validation Pathfinder), pas par Solver.
- **Set revealed** : pour optimisation Vision, évite de re-scanner les cases déjà connues.
- **solver_status** : géré par Solver (UNRESOLVED/TO_PROCESS/RESOLVED), storage passif.

### Solver (s4)  
- **Auto-calcul des composantes** : le solver extrait lui-même les composantes connexes depuis la FrontierSlice (pas de pré-groupage).
- **Actions uniquement** : s4 retourne seulement les actions (clics/drapeaux) à s5, PAS de mise à jour de frontière.
- **Lecture seule** : le solver accède en lecture à la frontière mais ne la modifie jamais.
- **Centralise solver_status** : gère UNRESOLVED→TO_PROCESS→RESOLVED, frontière = TO_PROCESS uniquement.

### Flux de données principal
```
s3(revealed + UNRESOLVED) → s4(TO_PROCESS + actions) → s5(actions + frontière_anticipée) → s6(exécution + validation) → s2(confirmations) → s3(mise_à_jour_finale)
```

**Note** : Échec S6 = arrêt boucle de jeu (pas de retry complexe).

## 1. Diagramme global

```
┌────────────┐   screenshot    ┌────────────┐   grid raw   ┌────────────┐   actions   ┌────────────┐
│ s0 Interface│ ───────────────▶ │ s1 Capture │ ────────────▶ │ s2 Vision  │ ──────────▶ │ s3 Storage │
└────┬───────┘   Canvas DOM     └────┬───────┘   PNG bytes  └────┬───────┘   GridRaw   └────┬───────┘
     │ viewport plan               │ meta                  │ overlays         │ frontier
     ▼                             ▼                       ▼                  ▼
┌────────────┐   heatmap plan   ┌────────────┐   actions   ┌────────────┐   macro     ┌────────────┐
│ s5 Pathfinder ───────────────▶ │ s6 Action  ────────────▶ │ Jeu (DOM) │ ◀──────────▶ │ s0 Interface│
└────────────┘                  └────────────┘             └────────────┘               └────────────┘
```

## 2. s0 Interface – DOM + coordonnées
- Réutilise `lib/s0_navigation` comme base (CoordinateConverter, ViewportMapper).
- Responsabilité : maintenir le cadre visible, appliquer les ordres de s5 (scroll, zoom, déplacements précis).
- Expose `ViewportState` (offset, zoom, résolution) et accepte `ViewportPlan` (liste d’ordres).
- Interfaces prêtes pour Selenium aujourd’hui / extension Native Messaging demain.

## 3. s1 Capture – Canvas → image (multi-canvases alignés)
- Méthode prioritaire : `canvas.toDataURL('image/png')` (1–2 ms) via JS injecté.
- `ZoneCaptureService.capture_canvas_tiles` orchestre la découverte (`CanvasLocator`) + capture de toutes les tuiles visibles (512×512) et les sauvegarde dans `temp/games/{id}/s1_raw_canvases/`.
- `compose_from_canvas_tiles` délègue l’assemblage à `lib/s1_capture/s12_canvas_compositor.py` : alignement cell_ref, recadrage ceil/floor, assertions stride, recalcul `grid_bounds`, export `full_grid_*.png`.
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
- Overlays Vision : question_mark affichés en blanc (comme unrevealed), decor en gris/noir, label + pourcentage compactés (font 11).
- Tests `tests/test_s2_vision_performance.py` garantissent <0,6 s/screenshot sur machine de référence.

### Diagramme vision
```
PNG bytes ─▶ CenterTemplateMatcher (zone 10×10, ordre prioritaire) ─▶ GridRaw + MatchResult
                                                    └──────▶ overlays_debug/ (vision overlay)
```

## 5. s3 Storage – Grille NumPy unique + Frontière compacte
- Grille NumPy infinie en RAM : représentation unique de vérité pour toutes les cellules jamais vues.
- Frontière compacte : ensemble des cellules fermées adjacentes aux ouvertes (set), suffisant pour résoudre les contraintes locales.
- Maintient des métriques de densité/attracteur par cellule (nb d'actions, distance viewport) utilisées par s5.
- Export JSON pour compatibilité WebExtension (pas de formats binaires propriétaires).
- Mise à jour : s3 reçoit les confirmations de s2 après exécution par s6, pas de double mise à jour depuis s4.

## 6. s4 Solver – Motifs déterministes + solveur exact local
- Bibliothèque de motifs 3×3/5×5 (rotations/reflets) encodés en base 16 → lookup O(1).
- Propagation classique : si chiffre == nb de drapeaux, ouvre toutes les autres cases adjacentes.
- Extraction de composantes frontier (groupe contraintes/variables) → backtracking SAT-like sur ≤15 variables (pruning min/max).
- Au-delà : heuristique (Monte-Carlo contraint ou mini-CNN probabiliste local).
- Sortie : `ActionBatch` (flags, open sûrs) + zones d’intérêt pour pathfinder.

## 7. s5 Pathfinder – Heatmap & trajets multi-étapes
- Entrées : frontière compacte (densité/actions en attente), archive pour zones hors écran, état viewport, batch d’actions solver.
- Calcule des attracteurs (barycentre pondéré par distance/densité) pour garder un maximum de frontier visible.
- Planifie les déplacements multi-étapes (scrolls successifs, zoom éventuel) et s’assure que les cases révélées hors écran repassent devant la caméra.
- Émet un `ViewportPlan` (liste ordonnée d’ordres) + priorisation des actions solver.

### Schéma heatmap
```
FrontierSlice + Densité ─▶ fonction attracteur(distance, actions) ─▶ heatmap
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
  3. Backend exécute capture/vision/solver/pathfinder/action et renvoie instructions.
- Alternative long terme : traduire s3–s6 en Rust/C++ → WebAssembly pour tout embarquer côté extension.
- L’extension réutilisera les overlays PNG/JSON pour visualiser les décisions.

## 10. Résumé des données échangées

| Donnée | Producteur | Consommateur | Description |
| --- | --- | --- | --- |
| `ViewportState` | s0 | s1/s5 | offset, zoom, viewport bounds |
| `CaptureMeta` | s1 | s2/s3 | timestamp, cell size, alignement |
| `GridRaw` | s2 | s3 | grille brute (int codes) |
| `FrontierSlice` | s3 | s4/s5 | projection compacte avec densité |
| `ActionBatch` | s4 | s5/s6 | actions sûres (flags/open) |
| `ViewportPlan` | s5 | s0/s6 | déplacement multi-étapes |

---

**À retenir :** garder ce pipeline déterministe, testable et prêt pour une migration extension. Toute modification de couche doit préserver les interfaces décrites ci-dessus.
