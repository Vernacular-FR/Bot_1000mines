---
description: Spécification du pipeline Center Sampling / Template Matching Central
---

# SPEC – Center Sampling & Template Matching Central

## 1. Contexte et contraintes
- **Masquage** : éclats de mines détruisent ≈7px sur chaque bord → zone centrale 10×10 exploitable uniquement.
- **Motifs décoratifs** : couleurs très variées pouvant imiter des chiffres sur 1 ou 2 pixels.
- **Objectifs runtime** : <0,1 ms par cellule, 0 faux positifs critiques, pipeline déterministe sans dépendances lourdes.
- **Dataset actuel** : 1546 échantillons (numbers_1→8, empty, decor, flag, exploded, unrevealed).

## 2. Enseignements des tentatives précédentes
| Approche | Motif d'abandon |
|----------|-----------------|
| 4 pixels globaux (s212) | Séparation = 0.000, aucun pixel disjoint décor/chiffre |
| Smart Fingerprint (générateur d’empreintes) | Optimisation trop lourde (~10 s), non déterministe |
| Sampling ponctuel centre | Décor possédant les mêmes couleurs aux points sondés ⇒ faux positif immédiat |

**Leçons clefs** :
1. L’information spatiale complète (zone 10×10) est indispensable.
2. Il faut conserver la couleur RGB (passage en niveaux de gris = perte de signature).
3. Les seuils doivent être ancrés sur des mesures statistiques (et non constants arbitraires).

---

## 2bis. Position dans le pipeline (rappel)

s2_vision fournit une **observation déterministe** (symboles) à partir d’une image alignée.

Elle ne calcule pas :
- la topologie (`ACTIVE/FRONTIER/SOLVED`)
- les index storage (`active_set/frontier_set`)

Ces traitements relèvent de s4_solver et sont décrits dans `doc/SPECS/s3_STORAGE.md` et `doc/SPECS/s4_SOLVER.md`.

Pour le contrat global (entrées/sorties, overlays), voir `doc/SPECS/s2_VISION.md`.

## 3. Fondations analytiques (s21_templates_analyzer)
1. **Variance analyzer** (`variance_analyzer.py`) :
   - Génère les heatmaps par symbole.
   - Superpose toutes les cases chiffrées + vides, valide la marge 7px.
   - Produit `variance_results/*.png + simple_variance_results.json`.
2. **Template aggregator** (`template_aggregator.py`) :
   - Reprend le même dataset et extrait la zone centrale `image[7:17,7:17,:]`.
   - Calcule mean/std par symbole + distances intra-symbole.
   - Sauvegarde tous les artefacts dans `template_artifact/`.

```powershell
cd src/lib/s2_vision/s21_templates_analyzer
python template_aggregator.py  # génère tous les templates
```

## 4. Artefacts générés
| Fichier | Rôle | Chargé par |
|---------|------|------------|
| `template_artifact/<symbol>/mean_template.npy` | Matrice 10×10×3 moyenne de la zone centrale | Classifieur |
| `template_artifact/<symbol>/std_template.npy` | Variabilité pixel/canal (tolérance locale) | Classifieur |
| `template_artifact/<symbol>/preview.png` | Visualisation dev/debug | Dev/QA |
| `template_artifact/central_templates_manifest.json` | Index JSON : marge, stats (μ, σ, max L2), seuil suggéré, chemins relatifs | Loader runtime |

**Pourquoi conserver les `.npy` ?**  
Le manifest ne contient que les métadonnées. La comparaison L2 en runtime nécessite les matrices brutes (`np.load`). Format minimaliste ⇒ lecture directe + sérialisation simple.

## 5. Algorithme de classification
### 5.1 Chargement
```python
import json, numpy as np
from pathlib import Path

def load_templates(manifest_path: str):
    manifest = json.load(open(manifest_path, "r", encoding="utf-8"))
    templates = {}
    base_dir = Path(manifest_path).parent
    for name, info in manifest["templates"].items():
        templates[name] = {
            "mean": np.load(base_dir / info["mean_template_file"]),
            "std": np.load(base_dir / info["std_template_file"]),
            "threshold": info["suggested_threshold"],
        }
    return templates, manifest["margin"]
```

### 5.2 Matching central
```python
def classify_cell(cell_image, templates, margin=7):
    zone = cell_image[margin:-margin, margin:-margin, :].astype(np.float32)
    best_symbol, best_dist = None, float("inf")
    for name, tpl in templates.items():
        dist = np.linalg.norm(zone - tpl["mean"])
        if dist < tpl["threshold"] and dist < best_dist:
            best_symbol, best_dist = name, dist
    return best_symbol or "unknown", best_dist
```

### 5.3 Exploitations possibles du `std_template`
- Pondérer les différences par `1 / (std + ε)` pour ignorer les pixels naturellement instables.
- Générer automatiquement une carte de confiance (faible variance = confiance élevée).

## 6. Tests & validation
1. **Masquage simulé** : appliquer un masque 7px aléatoire, vérifier qu’on conserve >98 % de précision chiffres.
2. **Motifs décoratifs** : injecter >100 décors extrêmes (couleurs proches du 1 ou 2) ⇒ distance > seuil.  
   - Depuis 2025‑12‑12, le seuil `empty` a été resserré (`UNIFORM_THRESHOLDS["empty"]=25`) pour couper les décors gris très clairs.
3. **Variations photométriques** : ±20 % luminosité/contraste ⇒ calibrer les seuils sorties aggregator.
4. **Benchmark** : comparer latence vs sampling ponctuel (attendu ≈0,1 ms/cellule avec NumPy).  
   - Le matcher runtime applique désormais un ordre de priorité strict (uniformes → flag → chiffres → empty → question_mark → decor) avec **early exit** pour limiter les comparaisons.
5. **Inspection visuelle** : vérifier `preview.png`, heatmaps superposées et overlays (question_mark en blanc, decor gris/noir) pour documenter la marge.

## 7. Roadmap technique (mise à jour 2025‑12‑12)
1. **s21_templates_analyzer** : scripts variance + aggregator restent la source de vérité dataset.
2. **CenterTemplateMatcher** (en place) :
   - Chargement manifest + npy.
   - Heuristiques uniformes (`unrevealed`, `empty`) suivies d’un échantillonnage de bord pour forcer `exploded` si le pixel périmétrique n’est pas blanc.
   - Ordonnancement/early exit par probabilité, decor évalué seulement en dernier recours.
3. **Overlay runtime** :
   - Question marks dessinés comme les unrevealed (blanc) pour visualiser leur présence.
   - Décors forcés en gris/noir pour éviter les confusions.
   - Label + pourcentage compactés (font 11, interligne réduit).
4. **Intégration services** :
   - Vision API consomme désormais ce matcher unique et produit des overlays validés.
   - Les tests `tests/test_s2_vision_performance.py` servent de validation de non-régression (<0,6s / capture en moyenne sur la machine de référence).
5. **Documentation** :
   - `s02_VISION_SAMPLING.md` (ce fichier) = référence technique.
   - `s21_templates_analyzer/READ_ME.md` = guide opérateur pour régénérer les templates.
   - `PLAN_S2_VISION_PURGE.md` suit l’état du chantier et est désormais marqué “vision validée”.

## 8. Résumé
- Le **Template Matching Central L2** est implémenté et validé en production bot (question_mark compris).
- Les artefacts `.npy + manifest` sont la source unique, avec des seuils runtime pouvant être resserrés (ex. empty=25) pour couvrir des cas décor inattendus.
- L’overlay vision reflète fidèlement les symboles reconnus, ce qui permet d’auditer rapidement les captures.
