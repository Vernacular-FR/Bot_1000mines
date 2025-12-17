# Architecture V2 - Pipeline Modular

## Vue d'ensemble

L'architecture V2 implémente un pipeline modulaire clair avec séparation des responsabilités :
- **Vision** : reconnaissance pure, pas de calcul topologique
- **Storage** : gestion centralisée des sets avec invariants stricts
- **Solver** : consommation de la frontière depuis storage, focus_actualizer stateless

## Flux principal

```
capture → vision → storage → state_analyzer → solver → executor → recapture
```

### Étape 1 - Capture
- Capture des canvases bruts
- Composition en grille unique
- Publication des métadonnées dans SessionContext

### Étape 2 - Vision (s2)
- `matches_to_upsert()` retourne seulement les cellules reconnues
- `solver_status` : JUST_VISUALIZED/NONE/SOLVED
- **Ne calcule plus** frontier/active/known_set

### Étape 3 - Storage (s3)
- `apply_upsert()` valide les invariants (focus levels cohérents)
- `_recalculate_sets()` reconstruit les sets depuis les cellules modifiées
- Purge automatique de TO_VISUALIZE de active_set
- Sets gérés : known_set, revealed_set, active_set, frontier_set, to_visualize

### Étape 4 - State Analyzer (s4)
- Classification topologique via FrontierClassifier
- Promotions : JUST_VISUALIZED → ACTIVE/FRONTIER/SOLVED
- Initialisation des focus levels (TO_REDUCE/TO_PROCESS)
- FocusActualizer gère les promotions de focus (stateless)

### Étape 5 - Solver (s4)
- Utilise SolverFrontierView construite depuis storage
- Consomme frontier_set et frontier_to_process
- Ne recalcule plus la frontière localement
- `compute_frontier_from_cells()` supprimé

### Étape 6 - Executor
- Exécute les actions (flags, clics)
- Met à jour l'état du jeu

## Modules clés

### GridStore (s31)
- Sparse grid avec délégation à SetManager
- Validation des invariants dans `_validate_cells()`
- Recalcul incrémental des sets dans `_recalculate_sets()`

### SetManager (s32)
- Gère les 5 sets (known, revealed, active, frontier, to_visualize)
- Opérations individuelles pour mises à jour incrémentales
- Purge TO_VISUALIZE de active_set dans `apply_set_updates()`

### FocusActualizer (s45)
- Module stateless pour les promotions de focus
- Retourne StorageUpsert avec focus levels mis à jour
- REDUCED → TO_REDUCE, PROCESSED → TO_PROCESS

### StateAnalyzer (s40)
- Combine classification topologique et promotions focus
- Instance réutilisable dans GameLoopService
- Retourne StorageUpsert avec active/frontier mis à jour

### FrontierView Factory
- Construit SolverFrontierView depuis storage snapshot
- Filtre frontier_to_process (TO_PROCESS)

## SessionContext enrichi

```python
@dataclass
class SessionContext:
    # ... champs existants ...
    historical_canvas_path: Optional[str] = None  # Pour overlays historiques
```

## Avantages de l'architecture V2

1. **Séparation claire** : chaque module a une responsabilité unique
2. **Pas de doublons** : storage est la source de vérité pour les sets
3. **Extensible** : focus_actualizer peut être enrichi indépendamment
4. **Testable** : chaque module peut être testé isolément
5. **Performance** : recalcul incrémental des sets, pas de calculs redondants

## Points d'attention

- La frontière est reconstruite à chaque passe (délai d'une itération après actions solver)
- `frontier_add`/`frontier_remove` vides dans compute_solver_update (géré par storage)
- Focus levels doivent être initialisés lors des promotions dans StateAnalyzer

## Fichiers modifiés/créés

### Nouveaux
- `src/lib/s4_solver/s45_focus_actualizer.py`
- `src/lib/s4_solver/s40_states_analyzer/state_analyzer.py`
- `src/lib/s4_solver/s40_states_analyzer/frontier_view_factory.py`

### Modifiés
- `src/lib/s3_storage/s31_grid_store.py` : ajout `_recalculate_sets()`
- `src/lib/s3_storage/s32_set_manager.py` : ajout méthodes individuelles et purge TO_VISUALIZE
- `src/lib/s2_vision/s23_vision_to_storage.py` : simplifié `matches_to_upsert()`
- `src/lib/s4_solver/s49_optimized_solver.py` : suppression `compute_frontier_from_cells()`
- `src/lib/s4_solver/controller.py` : utilisation frontier depuis storage
- `src/lib/s3_storage/s30_session_context.py` : ajout `historical_canvas_path`
- `src/services/s5_game_loop_service.py` : intégration StateAnalyzer

Cette architecture V2 est maintenant conforme aux SPECS archivées et prête pour les évolutions futures (pattern engine, CNN patches, etc.).
