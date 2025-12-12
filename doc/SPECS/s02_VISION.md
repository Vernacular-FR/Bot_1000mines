---
description: Spécification complète de la couche s2_vision
---

# S02 · Vision – Spécification

Cette fiche décrit l’architecture, les API et les invariants de la couche **s2_vision**. Elle prolonge `s02_VISION_SAMPLING.md` (détails techniques sur le sampling central) en documentant l’ensemble du pipeline de vision utilisé par le bot.

## 1. Mission & périmètre

- Convertir une capture alignée (issue de `ZoneCaptureService`) en **grille brute** (`GridRaw`) et produire les artefacts nécessaires au debug (overlays PNG/JSON).
- Garantir une classification **100 % déterministe** (pas de probas) avec des seuils documentés.
- Exposer une API stable pour les services (aujourd’hui `VisionAnalysisService`, demain un orchestrateur de boucle complète).

## 2. Entrées / Sorties officielles

| Élément | Producteur | Consommateur | Description |
| --- | --- | --- | --- |
| `GridCapture` (cf. `ZoneCaptureService`) | s1_capture | s2_vision | Image PNG alignée (cell_stride = 25) + `grid_bounds` et metadata |
| `VisionRequest` (`src/lib/s2_vision/facade.py`) | Services | Vision controller | `image`, `grid_bounds`, `cell_stride`, options overlay |
| `VisionResult` | Vision controller | s3_storage / services | `matches` (liste de `MatchResult`), overlay path facultatif |

### Invariants d’entrée
1. **Alignement** : l’image doit commencer sur un angle cellule (0,0 modulo stride). `lib/s1_capture/s12_canvas_compositor.py` garantit cette propriété.
2. **Stride constant** : `cell_stride = 25 px` = 24 px contenu + 1 px bordure. Toute variation doit être signalée dans `VisionRequest`.
3. **`grid_bounds` cohérents** : rectangle `[x_min, y_min, x_max, y_max]` couvrant exactement l’image recadrée (utilisé pour mapper les indices vision → storage).

### Sorties
- `matches`: liste ordonnée (ligne par ligne) de `MatchResult(symbol, distance, threshold, confidence, position)`.
- `grid_overlay_path` (optionnel) : PNG généré par `s22_vision_overlay.py`.
- `debug_json` (facultatif) : future extension pour stocker les distances et marges.

## 3. Architecture interne

```
GridCapture
   │
   ▼
VisionAnalysisService (src/services/s2_vision_analysis_service.py)
   │  prépare VisionRequest + options overlay
   ▼
VisionController (src/lib/s2_vision/controller.py)
   │ 1. charge templates via CenterTemplateMatcher
   │ 2. itère les cellules (pixel space) selon grid_bounds et stride
   │ 3. appelle classify_cell / classify_grid
   │ 4. transmet MatchResult + instructions overlay
   ▼
CenterTemplateMatcher (src/lib/s2_vision/s21_template_matcher.py)
   │  extractions 10×10, heuristiques uniformes, ordre prioritaire, anneau exploded
   ▼
VisionOverlay (src/lib/s2_vision/s22_vision_overlay.py)
   │  dessine rectangles + labels selon MatchResult
   ▼
PNG overlay (temp/games/{id}/s2_vision/…)
```

## 4. Modules & responsabilités

### 4.1 `VisionAnalysisService`
- **Fichier** : `src/services/s2_vision_analysis_service.py`
- **Rôle** : façade métier utilisée par les bots/scénarios.
- **Fonctions clés** :
  - `analyze_grid_capture(GridCapture, overlay=True)` → `VisionResult`
  - Convertit `GridCapture` en `VisionRequest` (pixel origin = (0,0)).
  - Gestion du dossier overlay (`paths["vision"]`).

### 4.2 `VisionController`
- **Fichier** : `src/lib/s2_vision/controller.py`
- **Entrées** : `VisionRequest`, `VisionOverlay` config.
- **Étapes** :
  1. Calcul des coordonnées pixel (`grid_bounds` × `cell_stride`).
  2. Itération `(row, col)` → extraction `cell_image`.
  3. Appel `CenterTemplateMatcher.classify_cell`.
  4. Accumulation `MatchResult`.
  5. Génération overlay via `VisionOverlay.render`.
- **Invariants** :
  - Utilise les mêmes coordonnées pixel pour classification et overlay (pas de décalage).
  - Ne modifie jamais `grid_bounds` (ils représentent la zone transmise par s1_capture).

### 4.3 `CenterTemplateMatcher`
- **Fichier** : `src/lib/s2_vision/s21_template_matcher.py`
- **Artefacts** : `template_artifact/central_templates_manifest.json` + `template_artifact/<symbol>/mean/std`.
- **Pipeline** :
  - Extraction zone **10×10** (marge 7 px) depuis `cell_image`.
  - Ordre de test prioritaire : `unrevealed → exploded → flag → number_1..8 → empty → question_mark → decor`.
  - Heuristiques uniformes (`UNIFORM_THRESHOLDS`) + discriminant pixel `exploded`.
  - Early exit : si un symbole passe son seuil et respecte la priorité, la boucle se termine.
  - `MatchResult` contient `symbol`, `distance`, `threshold`, `confidence` (1 - dist/threshold).
- **Tests** :
  - `tests/test_s2_vision_performance.py`
  - Échantillons manuels via `debug_question_mark/`.

### 4.4 `VisionOverlay`
- **Fichier** : `src/lib/s2_vision/s22_vision_overlay.py`
- **Rôle** : dessin runtime.
- **Caractéristiques** :
  - Couleurs explicites (question_mark/unrevealed = blanc, decor = gris/noir, flags/mine = rouge/noir, numbers = palette bleue).
  - Labels compacts (`symbol`, `confidence%`).
  - Support de la transparence (`opacity` configurable).
- **Entrées** : `MatchResult` + config overlay (`font`, `margin`, `cell_stride`).

### 4.5 Artefacts & outils
- `s21_templates_analyzer/variance_analyzer.py` : validation marge 7 px, heatmaps.
- `s21_templates_analyzer/template_aggregator.py` : création manifest + npy.
- `s02_VISION_SAMPLING.md` : documentation complète du sampling central (référence à ce document).

## 5. API publique (facade)

### 5.1 `VisionRequest` (src/lib/s2_vision/facade.py)
```python
@dataclass
class VisionRequest:
    image: Image.Image
    grid_bounds: tuple[int, int, int, int]
    cell_stride: int
    overlay: bool = False
    overlay_config: OverlayConfig | None = None
```

### 5.2 `VisionResult`
```python
@dataclass
class VisionResult:
    matches: list[MatchResult]
    overlay_path: str | None = None
```

### 5.3 `MatchResult`
```python
@dataclass
class MatchResult:
    symbol: str
    distance: float
    threshold: float
    confidence: float
    cell_coordinates: tuple[int, int]
```

## 6. Flux de données détaillé

1. **Capture alignée** : `ZoneCaptureService` produit `GridCapture` (image + `grid_bounds`).
2. **Service vision** : `VisionAnalysisService` crée `VisionRequest`.
3. **Controller** : `VisionController` itère les cellules, appelle le matcher, collecte les résultats.
4. **Overlay** : si `overlay=True`, `VisionOverlay` dessine rectangles + labels et sauvegarde `full_grid_*_overlay.png`.
5. **Retour** : `VisionResult` contient `matches` (injecté ensuite dans le storage/solver) et l’éventuel overlay.

## 7. Tests & validation

- **Unitaires** :
  - `tests/test_s2_vision_performance.py` (benchmark + précision).
  - Tests internes des analyzers (non automatisés, scripts `variance_analyzer.py` et `template_aggregator.py`).
- **Validation manuelle** :
  - Inspecter `temp/games/{id}/s2_vision/full_grid_*_overlay.png`.
  - Vérifier les logs `[VISION]` dans `bot_1000mines.py`.

## 8. Roadmap / Extensions

- **Anneau exploded amélioré** : heuristique couleur 6–8 px autour du centre (pré-filtre).
- **Overlay JSON** : export des distances pour chaque symbole (à destination du solver).
- **CNN local (optionnel)** : module annexe pour cas bruités, branché derrière l’API actuelle.
- **Migration extension** : `VisionController` restera inchangé si l’image provient d’un content-script; seul `VisionRequest` changera sa source.

---

**Références associées**
- `doc/SPECS/s02_VISION_SAMPLING.md` – détails algorithmiques sur le sampling et les heuristiques.
- `doc/PIPELINE.md` – schéma global capture → vision → solver.
- `doc/META/CHANGELOG.md` – historique des évolutions vision.
