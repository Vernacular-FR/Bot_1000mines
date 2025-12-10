# 01 · Pipeline Capture → Solver → Pathfinder

Ce document fusionne les anciennes sections capture/vision, storage/solver et pathfinder/action pour offrir une vue unique du pipeline s0 → s6.

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

## 3. s1 Capture – Canvas → image
- Méthode prioritaire : `canvas.toDataURL('image/png')` (1–2 ms) via JS injecté.
- Fallback : Chrome DevTools Protocol (`Page.captureScreenshot` + clip) ou Playwright headless.
- Selenium screenshot conservé uniquement en secours (20–40 ms).
- Nettoyage automatique des buffers temporaires pour éviter la saturation disque.

### Schéma capture
```
ViewportState ─▶ execute_script("return canvas.toDataURL()") ─▶ base64 PNG ─▶ decode → bytes
```

## 4. s2 Vision – PixelSampler déterministe
- LUT couleurs + offsets internes (centre ± 4 px) → classification OPEN/CLOSED/FLAG/NUM.
- Calibration automatique au démarrage (scan d’une grille de référence) + recalibrage à la demande.
- Filtre de stabilité : vote sur 2 captures successives pour éviter le bruit.
- Fallback optionnel : mini-CNN 3×3/4×4 appliqué uniquement sur la bordure bruitée.
- Sorties : `GridRaw` (dict[(x,y)] = code), overlays PNG/JSON pour debug.

### Diagramme vision
```
PNG bytes ─▶ sampler(sample_offsets, LUT) ─▶ GridRaw + Confidence map
                                 └──────▶ overlays_debug/
```

## 5. s3 Storage – Archive + Frontière compacte
- Archive globale : conserve toutes les cellules jamais vues (grid infinie) avec provenance et timestamps.
- Frontière compacte : bande de 2 cases révélées + 1 couche fermée (inclut les 8 voisins). Suffit pour résoudre toutes les contraintes locales.
- Maintient des métriques de densité/attracteur par cellule (nb d’actions, distance viewport) utilisées par s5.
- Pruning strict : uniquement sur la frontière (recalculable), jamais sur l’archive.
- Sérialisation interchangeable (JSONL ou SQLite) via `serializers.py`.

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
