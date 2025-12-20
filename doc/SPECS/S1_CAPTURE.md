---
description: Chaîne de capture S1
---

# S01 CAPTURE – Spécification technique

s1_capture produit des images exploitables par la vision.

Elle est volontairement “bête” :
- elle récupère des pixels
- elle capture une zone alignée
- elle ne fait pas de classification (c’est s2)

## 1. Mission

- Capturer une image du canvas (ou d’une zone du canvas) via JS (`canvas.toDataURL`).
- Renvoyer une image alignée + ses métadonnées (bounds/stride), afin que s2_vision puisse mapper correctement les cellules.

## 2. Architecture (qui appelle qui)

```
Services
  └─ InterfaceController (s0)
       └─ CaptureController (s1)
            └─ CanvasCaptureBackend (JS)
```

## 3. Contrat (entrées / sorties)

### 3.1 Entrée

- `CaptureRequest` : zone à capturer + options (save, metadata, …).

### 3.2 Sortie

- `CaptureResult` : image (PIL/bytes) + infos de sauvegarde.

## 4. API utilisée par les services

Ces appels transitent par la façade s0 (`InterfaceController`) :

- `capture_zone(request: CaptureRequest) -> CaptureResult`
- `capture_grid_window(grid_bounds, *, save=False, annotate=False, filename=None, bucket=None) -> CaptureResult`

## 5. Flux d’exécution (résumé)

1) Service appelle `interface.capture_grid_window(bounds, ...)`.
2) s0 s’assure que la zone est visible (`ensure_visible`).
3) s1 construit/exécute la capture :
   - lit `capture_meta` via s0
   - valide la zone (`relative_origin`)
   - appelle `CanvasCaptureBackend.capture_tile`.
4) s1 retourne `CaptureResult` (image brute) aux services.
5) s2_vision consomme `CaptureResult` et produit `matches` + overlay (si activé).

## 6. Optimisations de performance (2025-12-20)

### Composite Aligné depuis IDs Canvas
- **Problème** : Les décalages spatiaux dans le composite étaient causés par l'utilisation des coordonnées DOM des canvas.
- **Solution** : Le composite `_compose_aligned_grid()` calcule maintenant les positions depuis les IDs (ex: `canvas_0x0` → position (0,0) × 512px).
- **Bénéfices** : Alignement parfait indépendant du viewport, cohérence spatiale garantie même après zoom/dézoom.

### Gestion des Mouvements Manuels
- **Problème** : Quand l'utilisateur bougeait manuellement, le bot continuait avec des données périmées.
- **Solution** : En cas de capture ignorée (mouvement détecté), `success=False` est retourné pour empêcher l'exécution du solver.
- **Bénéfices** : Robustesse accrue face aux interactions utilisateur, évite les actions basées sur des données obsolètes.

## 7. Invariants

- Toujours capturer via `InterfaceController` (pas d'accès direct aux composants internes depuis les couches supérieures).
- Pas d'overlay ici : s1 renvoie des pixels; les overlays sont produits par s2/debug.
- Pas de logique "grid" ici : s1 ne connaît pas `ACTIVE`, `frontier_set`, etc.
