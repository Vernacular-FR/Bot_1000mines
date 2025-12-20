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
- Suppression de 7 éléments (overlays debug, tests dispersés, code mort).
- Nettoyage des imports et méthodes obsolètes.

### Phase 2 – Refactoring Architectural
- Unification du `StatusClassifier`.
- Division de `GameLoopService` en `SingleIterationService` et `GameLoopService`.

## 19 décembre 2025 — Stabilisation du pipeline minimal

- **Init session propre** : sélection du mode Infinite + difficulté fiabilisée.
- **Repères corrects** : vision sur composite aligné avec GridBounds absolus.
- **Invariants storage** : formalisation de la validation des sets.

## 20 décembre 2025 — Stabilisation V3 (Exécution temps-réel & Clics robustes)

Cette étape marque la fin de la "passivité" du planner. Le bot devient beaucoup plus réactif et résistant aux manipulations de l'utilisateur.

### 1. Le Planner devient l'Exécuteur
Le module `s6_executor` a été supprimé. C'est maintenant le **Planner (s5)** qui prend la main sur la souris :
- **Réactivité** : Dès qu'une case est déduite comme sûre, elle est cliquée.
- **Intelligence émotionnelle** : Le planner surveille le compteur de vies. S'il fait sauter une mine, il s'arrête 2 secondes pour laisser les animations se finir.

### 2. Clics "Aimantés" (Anchor-Relative)
Le bot ne clique plus à côté si on bouge la fenêtre.
- **Le secret** : On utilise des coordonnées relatives à la grille.
- **JavaScript à la rescousse** : Au moment précis du clic, un script JS recalcule la position réelle de la grille via `getBoundingClientRect()`.

### 3. Simplification de la Boucle
La boucle de jeu (`s9_game_loop.py`) est maintenant ultra-légère. Elle orchestre les briques sans gérer les délais d'explosion.

## État actuel (fin 2025)
Le refactoring architectural a transformé le projet en une base solide, prête pour les optimisations de performance (V3-PERFORMANCES) et les nouvelles fonctionnalités (V4-FEATURES).