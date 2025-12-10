# Plan d’optimisation – Vision incrémentale & CNN hybride

## 1. Constat actuel
- **Pipeline en production** : capture → template matching OpenCV + logique (Pass00/Pass01/Pass02) → GridDB → solver.
- **Avantages** : déterministe, pas de dataset à maintenir, compatible avec la logique de flood-fill et les overlays existants.
- **Limites** :
  - Sensible aux variations visuelles (décorations animées, bruit de compression).
  - Coût CPU proportionnel au nombre de cellules inspectées (même si réduit par les passes).
  - Difficulté à distinguer certains motifs « exotiques » (décorations, chiffres délavés) sans heuristiques supplémentaires.

## 2. Lecture critique du plan CNN (Optimised analysis.md)
| Axe | Plan CNN | Analyse |
|-----|----------|---------|
| **Structure projet** | Créer un dépôt `mines_cnn/` complet avec dataset, scripts, bench, ONNX | Très exhaustif mais déconnecté du repo actuel → risque de double maintenance. |
| **Extraction dataset** | Scripts pour découper toutes les cases, normaliser, stocker par classe | Nécessite une chaîne fiable de labellisation (ground truth). Actuellement les labels « sûrs » ne couvrent pas toutes les classes, surtout les décorations. |
| **Modèle** | CNN léger (type LeNet) en PyTorch | Faisable, mais nécessite GPU/CPU optimisé + intégration Python (Torch) dans notre pipeline orienté PIL/Numpy. |
| **Intégration** | Remplacer le matching par des batchs `predict()` | Impose de gérer les seuils d’incertitude, fallback template, monitoring. |
| **Maintenance** | Export ONNX, quantization, tests unitaires | Exige une infra ML (datasets versionnés, régénération des modèles). |

**Conclusion** : excellente vision long terme mais lourde à déployer immédiatement. Il faut préparer :
1. Des données labellisées fiables.
2. Un chemin d’intégration progressif (mode shadow, puis hybride).
3. Des métriques pour comparer CNN vs template.

## 3. Stratégie proposée
Nous conservons la logique incrémentale actuelle et ouvrons un chantier *vision hybride* structuré en phases. Objectifs :
1. **Court terme** : Stabiliser et instrumenter le pipeline existant (déjà bien avancé).
2. **Moyen terme** : Construire un dataset auto-labellisé + pipeline d’entraînement (préparer l’arrivée du CNN).
3. **Long terme** : Intégrer un CNN léger en mode shadow, puis en production lorsque ses métriques dépassent le template matching.

## 4. Roadmap détaillée

### Phase A – Stabilisation (en cours / court terme)
1. Finaliser le filtrage actif (ne passer au matching que les candidates non stables).
2. Générer `analysis_diff.json` et synchroniser GameSolverService.
3. Consolider les métriques (`scan_ratio`, `cells_skipped`, pass metrics) et écrire un journal d’expérimentation.

### Phase B – Extraction indépendante & Labellisation (pré requis CNN)
1. **Extracteur autonome (OK)**
   - Script CLI `tools/extract_cells.py` exploitant les screenshots existants (`temp/games/**/zone_*.png`) sans dépendre du pipeline temps réel.
   - Pour chaque screenshot : découper toutes les cellules via les bounds, lire `grid_state_db.json` si présent pour suggérer un label courant, sauvegarder l’image dans `data/cell_bank/<label_suggéré or decor>/shot_<id>_x<gx>_y<gy>.png`.
   - Arborescence fixe : `unrevealed/`, `empty/`, `flag/`, `exploded/`, `decor/`, `number_1..8/`.  Les cellules non sûres vont dans `decor/` (ou `unverified/`) et pourront être reclassées à la main.
2. **Labellisation manuelle rapide (en cours)**
   - L’utilisateur déplace/renomme les fichiers pour valider les classes (glisser-déposer dans les dossiers cibles).
   - Script `python scripts/cell_bank_stats.py --root src/lib/s2_recognition/Neural_engine/cell_bank` pour compter les exemples par classe, détecter les patches invalides et produire un rapport optionnel (`--output stats.json`).
3. **Nettoyage & contrôle**
   - Supprimer automatiquement les patches dupliqués / flous.
   - Reporter les classes sous-représentées pour guider la collecte.
4. **Augmentation ciblée (plus tard)**
   - Une fois les dossiers remplis, appliquer des augmentations (luminosité, bruit, blur léger) avant l’entraînement.

### Phase C – Prototype CNN (shadow mode)
1. Implémenter un micro-modèle (PyTorch ou ONNX) entraîné sur le dataset interne.
2. Intégrer un service `CNNRecognizer` appelé en parallèle du template matching (mode shadow) pour collecter les prédictions sans influencer le jeu.
3. Comparer les résultats : confusion matrix, score par classe, temps d’inférence.
4. Déterminer un seuil de confiance et un fallback automatique (ex : CNN >= 0.85 → accepter, sinon template).

### Phase D – Intégration hybride
1. Ajouter une passe « vision_hybride » dans OptimizedAnalysisService :
   - Si CNN est confiant ⇒ utiliser le résultat.
   - Sinon ⇒ fallback template matching actuel.
2. Monitorer les deux pipelines (temps, précision, divergences).
3. Étendre la couverture (chiffres, empty, décorations) progressivement.

### Phase E – Optimisation & maintenance
1. Export ONNX + quantization pour réduire la latence.
2. Automatiser l’entraînement (script + config + artefacts versionnés).
3. Documenter les seuils, les modèles et la procédure de regression testing.

## 5. KPI & critères de bascule
- **CNN Accuracy ≥ 99 %** sur jeu de test interne (par classe).
- **Temps d’inférence batch** ≤ template matching pour un patch complet.
- **Taux de fallback** (CNN → template) ≤ 5 % après stabilisation.
- **Zéro régression** sur les scénarios 3 et 4 (victoire/défaite inchangées).

## 6. Actions immédiates
1. Terminer la Phase A (filtrage actif + diff + journal de metrics).
2. Spécifier l’API « export dataset » (Phase B) et l’intégrer dans `ZoneCaptureService` + `OptimizedAnalysisService`.
3. Définir le format des métadonnées pour le dataset (JSON + PNG par cellule).

## 7. Prochain point de synchronisation
- Préparer un rapport Semaine X avec :
  - Statut Phase A (OK / bloquant).
  - Volume de données collectées pour Phase B.
  - Décision sur la stack ML (PyTorch vs TensorFlow vs ONNX direct).
