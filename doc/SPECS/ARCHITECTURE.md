# ARCHITECTURE – Référence officielle

Cette spécification décrit l’architecture cible du bot 1000mines après la simplification radicale. Elle constitue la référence unique pour les décisions techniques.

## 1. Vue d’ensemble des couches

1. **s0_viewport** – Pilote le navigateur/canvas (DOM, coordonnées). Réutilise `lib/s0_navigation` comme base. Fournit offsets, zoom et callbacks DOM. Doit rester interchangeable (Selenium aujourd’hui, extension demain).
2. **s1_capture** – Récupère l’image la plus rapidement possible (`canvas.toDataURL`, CDP, Playwright). Gère la purge des buffers et expose `CaptureMeta` (timestamp, offset, cell_size).
3. **s2_vision** – Convertit l’image en grille brute via sampling déterministe (LUT couleurs, offsets fixes). Exporte `GridRaw` + overlays PNG/JSON. Peut intégrer un mini-CNN pour les cas bruités localisés.
4. **s3_storage** – Conserve l’archive globale (toutes les cellules vues) + une frontière compacte (épaisseur 2 cases révélées + 1 couche fermée). Expose densité/attracteurs pour pathfinder. Pruning uniquement sur la frontière.
5. **s4_solver** – Enchaîne motifs déterministes (lookup 3×3/5×5) puis solveur exact local (backtracking SAT-like sur composantes ≤15 variables). Au-delà, heuristique/Monte-Carlo. Sort `ActionBatch` sûrs.
6. **s5_pathfinder** – Calcule la heatmap/barycentres pour décider des déplacements viewport et prioriser les zones. Gère les cases révélées hors écran en ordonnant les déplacements nécessaires.
7. **s6_action** – Applique les clics/drapeaux (macro-actions) et remonte l’état par action. Interface unique pour remplacer Selenium par une WebExtension.

### Schéma pipeline

```
┌─────────────────┐
│ s0 Interface     │ ← pilote le navigateur / canvas (DOM, coords)
├─────────────────┤
│ s1 Capture      │ ← canvas → raw image (bytes)
├─────────────────┤
│ s2 Vision       │ ← PixelSampler + LUT → grille brute
├─────────────────┤
│ s3 Storage      │ ← Grid global + Frontier + pruning (alimenté par s2)
├─────────────────┤
│ s4 Solver       │ ← PatternEngine + LocalSolver (lit/écrit storage)
├─────────────────┤
│ s5 Pathfinder   │ ← calcule heatmap + trajets (lit storage, pilote s6)
├─────────────────┤
│ s6 Action       │ ← exécute clics/scroll envoyés par solver/pathfinder
└─────────────────┘
```

## 2. Partage des données

- `CaptureMeta` : timestamp, offset viewport, taille de cellule, zoom.
- `GridRaw` : dict[(x,y)] = code int (0 fermé, -1 drapeau, 1..8 num, 9 vide).
- `FrontierSlice` : sous-ensemble compact + densité/priorités + metadata viewport.
- `ActionBatch` : liste ordonnée d’actions sûres (flags/open) avec priorité et contexte.
- `ViewportPlan` : ordres multi-étapes (scroll, zoom, reposition) envoyés par s5 vers s0/s6.

## 3. Précisions clés

- **Capture directe** : priorité au canvas (toDataURL) et CDP. Selenium classique uniquement en secours.
- **Vision déterministe** : LUT calibrée automatiquement au démarrage (scan d’une grille connue). Filtre de stabilité (vote sur captures successives).
- **Storage dual** : archive jamais purgée, frontière recalculable. La frontière inclut systématiquement les 8 voisins autour des dernières cases révélées.
- **Solveur exact** : composants extraites sur la bordure ; backtracking avec pruning (bornes min/max par contrainte). Les actions renvoyées doivent être 100 % sûres.
- **Pathfinder** : doit pouvoir fonctionner même si la vision ne peut pas relire certaines cases (zones hors écran). S’appuie sur densité/frontière pour choisir les déplacements (fonction attracteur à définir).
- **Action** : support des macro-clics, ordonnancement précis, remontée d’état pour mettre à jour storage/vision.

## 4. Migration Extension

- Préparation Native Messaging : l’extension envoie `capture` / `solve` / `act` au backend Python via JSON.
- Option translation Rust/C++ → WebAssembly pour embarquer la logique côté extension. Décision à prendre après stabilisation complète.
- Overlays conservés (PNG/JSON) pour être ré-exploités dans une UI pédagogique.

## 5. Roadmap (rappel)

Itération 0 : nettoyage + création arborescence s0→s6 + `main_simple.py`.
Itération 1 : s0_viewport refactor.
Itération 2 : s1_capture (canvas toDataURL).
Itération 3 : s2_vision (sampler + calibration + debug).
Itération 4 : s3_storage (double structure + pruning).
Itération 5 : s4_solver.
Itération 6 : s5_pathfinder.
Itération 7 : s6_action.
Itération 8 : Extension-ready (interfaces isolées, proto Native Messaging).

## 7. Arborescence cible (référence)

```
src/
├─ app/                      # points d’entrée (cli / scripts)
├─ services/                 # orchestrateurs (session, boucle…)
└─ lib/
    ├─ s0_viewport/
    │  ├─ viewport_controller.py      # DOM + coords + déplacements
    │  ├─ interface.py
    │  └─ __init__.py
    ├─ s1_capture/
    │  ├─ canvas_capture.py           # toDataURL / CDP / extension
    │  ├─ interface.py
    │  └─ __init__.py
    ├─ s2_vision/
    │  ├─ pixel_sampler.py
    │  ├─ calibration.py
    │  ├─ interface.py
    │  ├─ __init__.py
    │  └─ debug/
    │       ├─ overlay_renderer.py
    │       └─ json_exporter.py
    ├─ s3_storage/
    │  ├─ grid_store.py
    │  ├─ serializers.py
    │  ├─ interface.py
    │  └─ __init__.py
    ├─ s4_solver/
    │  ├─ pattern_engine.py
    │  ├─ local_solver.py
    │  ├─ interface.py
    │  ├─ __init__.py
    │  └─ debug/
    │       ├─ overlay_renderer.py
    │       └─ json_exporter.py
    ├─ s5_pathfinder/
    │  ├─ pathfinder.py
    │  ├─ interface.py
    │  └─ __init__.py
    ├─ s6_action/
    │  ├─ click_executor.py
    │  ├─ interface.py
    │  └─ __init__.py
    └─ main_simple.py                 # boucle while simple (entry prototype)
```

## 6. Règles d’implémentation

- Chaque dossier `src/sX_*` contient `interface.py` décrivant son contrat officiel.
- Tests unitaires par couche, référencés dans `tests/` avec README spécifique.
- Journaliser les décisions majeures dans `SPECS/DEVELOPMENT_JOURNAL.md` après chaque itération.
- Aucune duplication documentaire : `doc/` = résumés, `SPECS/` = référence technique.
