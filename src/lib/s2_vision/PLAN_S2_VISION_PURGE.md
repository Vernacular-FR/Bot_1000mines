---
description: Diagnostic et plan de purge s2_vision
---

# PLAN S2 VISION – ÉTAT ACTUEL & PROCHAINES ACTIONS

## 1. État du chantier s21_templates (2025‑12‑12)

- ✅ **Legacy archivé** : `s21_pixel_sampler.py` et ses dépendances OpenCV/manifeste ne sont plus utilisés.
- ✅ **Variance analyzer** opérationnel (`s21_templates_analyzer/variance_analyzer.py`) :
  - Heatmaps par symbole + superposition numbers+empty.
  - Analyse quantitative de la marge (7 px validés).
  - Rapports `variance_results/*.png` + `simple_variance_results.json`.
- ✅ **Template aggregator** opérationnel (`template_aggregator.py`) :
  - Génération des templates centraux (10×10×3), écarts-types, previews.
  - Manifest unique `template_artifact/central_templates_manifest.json` avec seuil suggéré par symbole.
- ✅ **Exploitation runtime** : `CenterTemplateMatcher` charge le manifest, applique les heuristiques uniformes + discriminant pixel `exploded`, priorise les symboles (early exit) et envoie les résultats aux overlays.
- ✅ **Overlays Vision** : question_marks affichés comme unrevealed (blanc), decor forcé gris/noir, labels + pourcentage reformatés.
- ✅ **Tests d’intégration** : `tests/test_s2_vision_performance.py` valide précision/latence (<0,6s en moyenne sur machine de référence).  
→ **Conclusion** : le système de vision est validé à 100 %, prêt à être figé dans la roadmap principale.

## 2. Raison du pivot (rappel synthétique)

| Ancienne approche | Motif d’abandon |
|-------------------|-----------------|
| 4 pixels globaux / smart fingerprint | Sép.=0.000, incapable de rejeter les décors ; optimisation trop lourde |
| Template matching hybride OpenCV | Couplage fort aux assets legacy, dépendances lourdes, performances aléatoires |
| Sampling ponctuel | Faux positifs massifs dès qu’un décor partage les mêmes couleurs sur quelques pixels |

**Décision** : adopter le **Template Matching Central** basé sur la zone 10×10 stable, en conservant l’information RGB et des seuils issus de mesures statistiques (mean + 2σ).

## 3. Plan d’action vision (clôturé)

1. **Loader runtime** → ✅ `CenterTemplateMatcher` charge manifest + npy et expose `classify_cell`.
2. **Matcher central** → ✅ extraction zone centrale, distances L2 avec early exit + heuristique discriminante (pixel bord `exploded`).
3. **Service vision** → ✅ Vision API intégré au bot via `s21_template_matcher`.
4. **Intégration pipeline** → ✅ Le pipeline runtime n’utilise plus aucun sampler legacy, overlay mis à jour.
5. **Tests & validation** → ✅ Bench + overlays validés, seuil `empty` resserré pour les décors.
6. **Pipeline capture aligné** → ✅ Les captures multi-canvases sont composées via `lib/s1_capture/s12_canvas_compositor.py`, garantissant un alignement parfait pour la vision (cell_ref, ceil/floor, recalcul `grid_bounds`). Le debug overlay legacy a été supprimé.

### Options étudiées pour distinguer `exploded` vs `unrevealed` avec marge 9 px

1. **Heuristique d’anneau (pré-filtre couleur)**  
   - Vérifie l’anneau 6‑8 px autour du centre (pixels rouges/noirs spécifiques).  
   - Coût ~5‑10 µs/cellule, s’exécute avant les heuristiques uniformes.  
   - 100 % compatible avec l’optimisation “ordre + early exit” (on court-circuite le matching si anneau détecté).  
   - Recommandation actuelle : implémenter en priorité (faible complexité, deterministe).

2. **Marge différenciée par symbole**  
   - Les templates conservent leur marge native (10×10 pour mines, 6×6 pour chiffres).  
   - Nécessite de stocker/extraire plusieurs sous-zones et complique l’ordre de test.  
   - Risque de casser l’early exit (il faut connaître la marge avant de décider quels symboles tester).  
   - À réserver si l’anneau échoue.

3. **Double passe (6×6 puis 10×10)**  
   - Première passe chiffres/uniformes, seconde passe dédiée aux mines si doute.  
   - Double extraction pour ~30 % des cases → latence accrue.  
   - Compatible mais peu efficace : ne résout pas la confusion intrinsèque.

4. **Histogramme d’anneau / features avancées**  
   - Calcul de statistiques couleur par quadrant + seuils pondérés.  
   - Complexité et calibration supplémentaires, maintenance élevée.  
   - Option ultime si besoin, mais non prioritaire (perd l’avantage simplicité/early exit).

### 6. Docs / suivi

- `doc/SPECS/s02_CENTER SAMPLING.md` déjà à jour.
- `s21_templates/READ_ME.md` = guide rapide.
   - Ajouter une note dans CHANGELOG quand le classifieur sera branché.

## 4. Prochaines étapes immédiates

1. **Développer le loader + matcher central** (python pur, dépendances actuelles suffisantes).
2. **Brancher le service dans le pipeline vision** (remplacement progressif, mode shadow recommandé).
3. **Écrire un test minimal** qui charge le manifest, classifie un échantillon par symbole, vérifie la distance < seuil.

Une fois ces points terminés, la partie “templates” sera entièrement exploitée par s2_vision et la purge legacy pourra être considérée comme clôturée.
