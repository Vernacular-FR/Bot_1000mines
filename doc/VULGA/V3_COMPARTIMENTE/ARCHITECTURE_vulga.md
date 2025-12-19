# Journal architectural — V3 (compartimenté)

Ce journal correspond à la **V3 “compartimentée”** : même pipeline, mais documentation découpée par briques (interface/capture/vision/storage/solver/planner + efficacité).

L’idée n’est pas de réécrire l’histoire :

- je conserve les décisions fondatrices prises pendant la V2 (à partir du 10 décembre 2025),
- puis je documente les bascules V3 (refactorisation + stabilisation),
- et surtout je renvoie vers des journaux dédiés par composant pour éviter le “fourre‑tout”.

## À lire en V3 (journaux par brique)

Dans cette V3, l’architecture est volontairement “compartimentée” :

- `S0_INTERFACE_vulga.md` : contrat navigateur/coords/clics
- `S1_CAPTURE_vulga.md` : capture canvas + composite aligné
- `s2_VISION_vulga.md` : reconnaissance déterministe (template matching)
- `s3_STORAGE_vulga.md` : cohérence, sets, invariants
- `s4_SOLVER_vulga.md` : topologie (StateAnalyzer), reducer, CSP
- `s5_ACTION_PLANNER.md` : ordonnancement des actions et astuces d’exécution
- `ARCHITECTURE_efficacité.md` : pourquoi le bot est devenu très rapide (anti‑régressions)

## 18 décembre 2025 – Refactoring Architectural Complet

Après 3 semaines de développement intensif, le codebase avait accumulé de la complexité technique. J'ai lancé une opération de nettoyage et refactoring en deux phases pour assurer la maintenabilité à long terme.

### Phase 1 – Nettoyage Drastique

**Suppressions (7 éléments)**
- Overlays debug : `s49_overlays/` (34KB de visualisations)
- Tests dispersés : `test_unitaire/` dans chaque module
- Code mort : `s49_cleanup.py`, `s6_action/facade.py` (0 bytes)
- Services doublons : `s3_storage_solver_service.py`

**Nettoyages de code**
- Imports overlay supprimés dans 4 fichiers du solver
- Méthodes `emit_overlays()`, `emit_states_overlay()` éliminées
- Enums `CellSource` et `ActionStatus.LOOKUP` purgés
- Doublons unifiés : `ViewportState`, `CanvasDescriptor`, `ScreenshotManager`

### Phase 2 – Refactoring Architectural

**Unification StateManager**
```python
# AVANT : 2 classes dupliquées
class StateManager:        # Gestion ACTIVE/SOLVED
class FrontierClassifier:  # Détection frontières

# APRÈS : 1 classe unifiée
class StatusClassifier:    # Gestion complète des états
```

**Division GameLoopService**
```python
# AVANT : Service monolithique (400 lignes)
class GameLoopService:
    # Capture + Vision + Storage + Solver + Action + Loop

# APRÈS : 2 services spécialisés
class SingleIterationService:  # 1 passe complète (200 lignes)
class GameLoopService:         # Orchestrateur simple (100 lignes)
```

### Résultats

- **Bot 100% fonctionnel** : Pipeline complet opérationnel, 112 actions exécutées
- **Codebase optimisé** : -8 fichiers supprimés, +3 fichiers modulaires
- **Architecture propre** : Faible couplage, haute cohésion, zéro doublons

### Leçons apprises

1. **Purger tôt** : Le code mort s'accumule vite et coûte cher à maintenir
2. **Unifier les doublons** : 2 classes similaires = 1 bug garanti à terme
3. **Séparer les responsabilités** : Services monolithiques = difficile à tester
4. **Documenter les décisions** : `PHASE1_DECISIONS.md` a guidé le refactoring

## 19 décembre 2025 — Stabilisation du pipeline minimal (retour au concret)

À ce stade, la V2 avait une vision très stable, mais un symptôme bloquant :
la boucle “voyait” parfaitement la grille… et pourtant le solver n’arrivait pas à se mettre en mouvement (frontier/active vides).

Le correctif n’était pas “améliorer la vision”. C’était de remettre une étape oubliée au bon endroit :
 
- **La vision observe** et marque les cellules vues comme “fraîches”.
- **Le solver dérive la topologie** (ACTIVE/FRONTIER/SOLVED) à partir de ces observations.

Concrètement, on a verrouillé 3 points :

- **Init session propre** : sélection du mode **Infinite** + difficulté via les mêmes gestes que le legacy (attente explicite + clic direct).
- **Repères corrects** : la vision travaille sur un composite aligné dont les `GridBounds` sont absolus (donc des coordonnées négatives sont normales si l’origine n’est pas visible).

Résultat attendu :

- `active_set` et `frontier_set` deviennent non vides (donc le solver retrouve des actions).

Ce qui reste à faire (hors overlays) :

- **Invariants storage** : formaliser/centraliser la validation dans `s3_storage/invariants.py`.
- **FocusActualizer** : repromotions (réveiller les voisins) après reclustering post-vision et après décisions solver.
- **TO_VISUALIZE** : propagation des cases SAFE pour cadrer la recapture.

## État actuel (fin 2025)

Le refactoring architectural a transformé le projet en une base solide :
- **Modules autonomes** : `lib/*` = logique pure, `services/*` = orchestration
- **Documentation unique** : `SPECS/` comme référence technique
- **Tests centralisés** : `tests/` (pas de dispersion)

La V3 est maintenant prête pour les prochaines étapes :
- **V3-PERFORMANCES** : Optimisations algorithmiques
- **V4-FEATURES** : Nouvelles fonctionnalités
- **V5-TESTS** : Suite de tests automatisée