# MASTER OPTIMIZATION — Modèle logiciel cible & axes d’amélioration (Déc 2025)

Ce document synthétise le **modèle architectural visé** et les **optimisations pérennes**.  
La planification opérationnelle détaillée vit désormais dans [`MASTER_OPTIMIZATION_PLAN.md`](./MASTER_OPTIMIZATION_PLAN.md).

---

## 1. Vision système
Pipeline continu piloté par sept couches cohésives :

```
S0 Navigation ──► S1 Capture ──► S2 Vision ──► S3 Tensor ──► S4 Solver ──► S5 Actionneur ──► S6 Pathfinder
          ▲                             │                                   │
          └─────────────── Ops & Trace ─┴─────────────── HintCache ──────────┘
```

- **Objectif** : boucle temps réel, zéro copie, décisions solver validées et tracées à chaque tick.
- **Principe** : chaque couche expose un contrat clair, partage ses résultats via TensorGrid/Hints, et reste découplée via services d’orchestration.

---

## 2. Flux logicielle (pseudo-code)

```python
def play_game():
    session = NavigationSession()
    tensor = TensorGrid()
    actions = ActionQueue()
    pathfinder = Pathfinder()

    while session.is_active():
        # S0 – Navigation
        viewport = session.position(pathfinder.next_vector())

        # S1 – Capture
        patches = CaptureService.capture(viewport)

        # S2 – Vision
        updates = SmartScan.process(patches, tensor.prev_frontier())
        tensor.apply(updates)

        # S3 – Tensor fusion
        dirty_sets = tensor.publish_dirty_sets()

        # S4 – Solver
        decisions = HybridSolver.solve(tensor.view(dirty_sets))

        # S5 – Actionneur
        executed = ActionExecutor.run(decisions, session.input_bus)
        ActionLogger.log(executed)

        # S6 – Pathfinder
        pathfinder.update(tensor.stats(), executed)

        TraceRecorder.snapshot(tensor, decisions)
```

**Clés** :
1. **SmartScan différencié** : premier tick = full scan ; ensuite = incremental dirty sets + full scan périodique ou sur expansion frontière.
2. **TensorGrid** fournit une vue read-only au solver (valeurs, confiance, frontier mask).
3. **HybridSolver** mélange propagation, CSP et Monte Carlo selon la taille des zones.
4. **ActionExecutor** confirme chaque action via TensorGrid et publie un rapport résolu/bloqué à Pathfinder.
5. **Pathfinder** planifie le prochain déplacement (sliding window) selon densité de frontières et besoins solver.

---

## 3. Interfaces et données structurantes

| Producteur → Consommateur | Payload | Utilité |
| --- | --- | --- |
| S0 → S1 | `ViewportSpec(x, y, zoom, usable_mask)` | Garantit des captures alignées grille. |
| S1 → S2 | `CapturePatch(image, bounds, usable_mask)` | Unités de travail vision indépendantes. |
| S2 → S3 | `TensorUpdate(bounds, codes, confidences, frontier_mask)` | Mise à jour zéro copie des tenseurs. |
| S3 → S4 | `SolverView(values, confidence, dirty_sets)` | Vue cohérente pour CSP/Monte Carlo. |
| S4 → S5 | `SolverDecision(actions, risk_profile)` | Actions ordonnées + méta confiance. |
| S5 → S6 | `ResolutionStatus(zone_id, state)` | Données nécessaires au path planning. |
| Sx → Ops | `TraceSnapshot(tick_id, tensor, decisions, metrics)` | Replays, debug, apprentissage. |

**Structures clés** :
- `TensorGrid` : buffers mémoire partagés (`values:int8`, `confidence:uint8`, `age:uint32`, `frontier_mask:bool`).
- `HintCache` : événements `dirty_sets`, `component_priority`, `solver_requests`.
- `ActionQueue` : file FIFO avec déduplication, associée à `ActionLogger`.

---

## 4. Mécanismes d’optimisation

### 4.1 Court terme (Phases 2 → 5)
1. **TensorGrid + HintCache**  
   - API `update_region` + vues solver read-only.  
   - Snapshots `.npz` pour replays/tests.
2. **SmartScan incrémental**  
   - Masques `UNKNOWN/UNREVEALED`, matching hiérarchique couleur→variance→template, hash pixel.
3. **HybridSolver 2.0**  
   - Propagation vectorielle 3×3, CSP exact <40 cases, heuristiques 40–120, Monte Carlo ≥120.
4. **Actionneur structuré**  
   - `s51_action_queue`, `s52_action_executor`, `s53_action_logger`.  
   - Validation post-action via TensorGrid.
5. **Pathfinder dédié**  
   - Analyse densité (`s61_density_analyzer`), barycentre, scheduler sliding window.
6. **Instrumentation continue**  
   - KPI `scan_ratio`, `dirty_ratio`, `actions_success_rate`, `viewport_shift_latency`.  
   - Logs append-only + TraceRecorder.

### 4.2 Long terme / R&D
1. **Architecture distribuée** : TensorGrid via `multiprocessing.shared_memory`, séparation Vision/Solver/Pathfinder.  
2. **GPU Vision & Solver** : FFT/corrélation CUDA, Monte Carlo CuPy/Torch, flag `--enable-gpu`.  
3. **Neural solving** : modèle CNN/ViT consommant TensorGrid (self-play, fine-tuning, inference TorchScript).  
4. **Constraint Learning / #SAT** : génération CNF (`TensorFrontier` → solveur externe → probabilités exactes).  
5. **Speculative solving & latency hiding** : préparer les coups sûrs pendant les actions UI, rollback si divergence.  
6. **Ops headless** : migration Selenium → Playwright/WebGPU, dashboards temps réel.  
7. **Trace Learning** : datasets `.npz` + décisions solver pour entraînement offline.

---

## 5. Patterns d’implémentation

### 5.1 Smart Scan incrémental
```python
def process(patches, frontier_mask):
    for patch in patches:
        mask = patch.usable_mask & frontier_mask.extract(patch.bounds)
        roi = patch.image[mask]
        candidates = classifier.fast_filter(roi)
        refined = template_matching(candidates, roi)
        yield TensorUpdate(patch.bounds, refined.codes, refined.confidence, refined.frontier)
```

### 5.2 Hybrid Solver
```python
def solve(view):
    zones = FrontierSegmenter.split(view.frontier)
    actions = []
    for zone in zones:
        if zone.size < 40:
            actions += ExactCSP.solve(zone)
        elif zone.size < 120:
            actions += HeuristicPropagator.solve(zone)
        else:
            actions += MonteCarlo.rank(zone, budget_ms=120)
    return prioritize(actions)
```

### 5.3 Actionneur + Pathfinder
```python
def run(decisions, input_bus):
    played = []
    for action in deduplicate(decisions):
        if not tensor.is_action_needed(action):
            continue
        outcome = input_bus.execute(action)
        ActionLogger.append(action, outcome)
        tensor.mark_pending(action.target)
        played.append((action, outcome))
    pathfinder.ingest_feedback(played)
    return played
```

---

## 6. Observabilité & garde-fous
- **TraceRecorder** obligatoire à chaque tick (tensor snapshot + décisions solver + stats actionneur).
- **Append-only logs** pour les actions et métadonnées de capture.
- **Fenêtre glissante TensorGrid** pour contenir la mémoire quand le viewport glisse.
- **Compatibilité** : adaptateurs GridDB ↔ Tensor tant que les services historiques ne sont pas retirés.
- **Rejeu déterministe** : `temp/games/{id}` conserve captures, overlays, Tensor snapshots, logs actions.

---

## 7. Résumé
- **Court terme** : livrer TensorGrid + SmartScan + Solver 2.0 + Actionneur/Pathfinder dédiés.
- **Long terme** : architecture distribuée, GPU/Neural solving, ops headless, apprentissage depuis TraceRecorder.
- **Référence planning** : voir `MASTER_OPTIMIZATION_PLAN.md` pour le séquencement détaillé des phases.
