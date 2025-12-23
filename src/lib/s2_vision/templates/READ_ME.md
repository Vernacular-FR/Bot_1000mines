# Center Sampling README

Ce document sert de point d’entrée rapide pour la stratégie “Template Matching Central” utilisée dans `s21_templates_analyzer`. Les détails exhaustifs se trouvent dans `doc/SPECS/s02_CENTER SAMPLING.md`.

---

## Sommaire
- [Center Sampling README](#center-sampling-readme)
  - [Sommaire](#sommaire)
  - [Contexte rapide](#contexte-rapide)
  - [Pipeline TL;DR](#pipeline-tldr)
  - [Comment lancer les scripts](#comment-lancer-les-scripts)
  - [Artefacts produits](#artefacts-produits)
  - [Utilisation côté classifieur](#utilisation-côté-classifieur)
  - [Tests recommandés](#tests-recommandés)
  - [Roadmap express](#roadmap-express)
  - [Références](#références)

---

## Contexte rapide
- Les éclats de mines détruisent ~7 px sur chaque bord ⇒ seule la zone centrale 10×10 reste stable.
- Motifs décoratifs peuvent copier les couleurs d’un chiffre sur 1 ou 2 pixels ⇒ sampling ponctuel trop risqué.
- Objectifs : < 0,1 ms/cellule, 0 faux positifs critiques, pipeline 100 % déterministe.

Historique (échecs) :
| Approche | Motif d’abandon |
|----------|-----------------|
| 4 pixels globaux | Sép. = 0.000, aucun pixel rejet décor |
| Smart Fingerprint | Trop lent (~10s), optimisation non déterministe |
| Sampling ponctuel | Décor avec mêmes couleurs aux points ⇒ faux positif immédiat |

Conclusion : conserver la zone centrale complète + couleur RGB + seuils basés sur statistiques.

---

## Pipeline TL;DR
```
dataset (s21_templates_analyzer/data_set)
    ↓ variance_analyzer.py      → valide marge 7 px, heatmaps, rapports JSON
    ↓ template_aggregator.py    → génère mean/std + manifest + previews
    ↓ center classifier (à venir) charge manifest + npy pour matcher
```

---

## Comment lancer les scripts
```powershell
cd src/lib/s2_vision/s21_templates_analyzer

# Heatmaps + analyse marge
python variance_analyzer.py

# Templates centraux + manifest
python template_aggregator.py
```

---

## Artefacts produits
| Fichier | Contenu | Usage |
|---------|---------|-------|
| `variance_results/*.png` | Heatmaps par symbole + superposé | Validation visuelle |
| `variance_results/simple_variance_results.json` | Stats variance/marges | Documentation |
| `template_artifact/<symbol>/mean_template.npy` | Matrice 10×10×3 moyenne | Matching L2 |
| `template_artifact/<symbol>/std_template.npy` | Écart-type pixel/canal | Pondération / tolérance |
| `template_artifact/<symbol>/preview.png` | Image preview du template | Debug |
| `template_artifact/central_templates_manifest.json` | Manifest JSON (marge, seuil suggéré, chemins) | Loader runtime |

> Manifest = index lisible, `.npy` = données brutes. Les deux sont nécessaires.

---

## Utilisation côté classifieur (CenterTemplateMatcher)
```python
from src.lib.s2_vision.s21_template_matcher import CenterTemplateMatcher

matcher = CenterTemplateMatcher()  # charge central_templates_manifest.json
result = matcher.classify_cell(cell_image)
print(result.symbol, result.confidence)
```
- Matching : heuristiques uniformes (`unrevealed`, `empty`), discriminant pixel pour `exploded`, puis distances L2 ordonnées avec early exit.
- Seuils runtime = `suggested_threshold` sinon `UNIFORM_THRESHOLDS` (ex. `empty=25`).
- Les overlays Vision consomment directement `MatchResult` (question_mark en blanc, decor gris/noir).

---

## Tests recommandés
1. Masquage simulé (7 px) : vérifier >98 % de précision sur chiffres.
2. Décors extrêmes (≥100 variantes) : distance > seuil.
3. Variations ±20 % luminosité/contraste : recalibrer seuils si besoin.
4. Benchmark latence : viser ≈0,1 ms/cellule via NumPy pur.
5. Inspection visuelle : `preview.png` et heatmap annotée pour la marge.

---

## Roadmap express (mise à jour 2025‑12‑12)
1. Regénérer les templates (`template_aggregator.py`) à chaque ajout d’échantillon.
2. CenterTemplateMatcher est désormais le moteur officiel (un seul manifest, ordre prioritaire, early exit).
3. Vision API + overlays utilisent ce matcher (question_mark visibles, decor lisibles).
4. Dès qu’un seuil runtime change (ex. `empty` resserré), mettre à jour `s02_VISION_SAMPLING.md` et le CHANGELOG.

---

## Références
- Specification détaillée : `doc/SPECS/s02_CENTER SAMPLING.md`
- Scripts source : `src/lib/s2_vision/s21_templates_analyzer/`
- Résultats récents : `template_artifact/central_templates_manifest.json`
