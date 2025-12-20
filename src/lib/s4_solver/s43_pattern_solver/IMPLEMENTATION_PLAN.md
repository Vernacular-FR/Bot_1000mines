# Plan d'implémentation du Pattern Solver (s43)

Ce document liste les étapes à suivre pour finaliser le pattern solver et l'instrumentation de tests, en prenant exemple sur les scripts existants `01_run_propagation_solver.py`, `02_run_csp_solver_only.py` et `03_compare_solver_pipelines.py`.

## 1. Préparation du module s43
1. **Structurer le dossier** `s43_pattern_solver/` :
   - `pattern_solver.py` : moteur principal (détection de motifs, priorisation des actions).
   - `pattern_registry.py` : définition des motifs (structures de données, paramètres d'activation).
   - `actions_overlay.py` (facultatif) : rendu des actions spécifiques aux motifs.
   - `README.md` (ce fichier) : documentation de référence.
2. **Définir les interfaces** :
   - Entrées communes : `SolverFrontierView`, `GridCell` (comme CSP/propagator).
   - Sorties : `List[SolverAction]` + méta-infos (motif déclenché, confiance).
3. **Prévoir la configuration** : activation/désactivation par type de motif, profondeur de recherche éventuelle, logging détaillé des motifs détectés.

## 2. Tests unitaires dédiés (pattern only)
1. Créer `tests_unitaire/04_run_pattern_solver_only.py` sur le modèle de `02_run_csp_solver_only.py` :
   - Chargement des captures (`00_raw_grids`).
   - Conversion vision → storage (`matches_to_upsert`).
   - Exécution du pattern solver seul.
   - Génération d'overlays spécifiques (transparence par motif, couleur unique par famille de pattern).
   - Rapport console listant pour chaque capture : motifs déclenchés, nombre de safe/flags, temps d'exécution.
2. Ajouter un dossier `s43_pattern_solver_overlay/` pour stocker les rendus.
3. Prévoir un export JSON optionnel pour analyser les motifs retenus (analogue à `s429_solver_comparison`).

## 3. Tests orchestrés (pattern + propagator + CSP)
1. Étendre `03_compare_solver_pipelines.py` :
   - Ajouter un troisième pipeline « pattern solver » exécuté après vision et avant propagator pour mesurer ses apports.
   - Collecter les métriques : temps, safe/flags uniques, motifs utilisés.
   - Mettre à jour le rapport Markdown avec de nouvelles colonnes (diff Pattern vs Propagator/CSP, temps, ratio, motifs clés).
2. Permettre l'activation/désactivation de chaque pipeline par arguments CLI (ex. `--no-pattern`, `--only-pattern`).

## 4. Intégration future (hybrid solver)
1. Connecter `PatternSolver` dans `HybridSolver` (nouvelle version `s49_hybrid_solver`) comme phase préliminaire avant propagator.
2. Utiliser la configuration (flag `enable_patterns`) depuis `controller.py` pour activer/désactiver la phase.
3. Ajouter des compteurs dans `SolverStats` pour suivre les actions issues du pattern solver.

## 5. Validation / QA
1. Sélectionner un échantillon de grilles couvrant des motifs faciles (1-2-1, coin 1-1, chaînes 1-2-1-2).
2. Vérifier que les actions pattern sont :
   - Correctes seules (script 04),
   - Non redondantes lorsque propagator tourne,
   - Complémentaires vis-à-vis du CSP (rapports 03).
3. Documenter les résultats et limites dans `doc/SPECS/s04_SOLVER.md`.

> **Note** : cette feuille de route n'impose pas l'ordre exact mais décrit les livrables nécessaires pour industrialiser le pattern solver et ses tests.
