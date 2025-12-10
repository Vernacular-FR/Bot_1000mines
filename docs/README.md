# Documentation - Bot Minesweeper

## Architecture Complète

La documentation complète du projet est maintenant centralisée dans **[docs/specs/architecture_fichiers.md](specs/architecture_fichiers.md)**.

Ce document unifié inclut :
- **Architecture des fichiers** : Organisation complète des répertoires et chemins
- **Modules principaux** : Description détaillée de tous les composants
- **Flux de données** : Scénarios 1 et 2 avec flux détaillés
- **Base de données** : Structure de `grid_state_db.json`
- **Configuration** : Chemins centralisés dans `lib/config.PATHS`
- **Règles de nomination** : Conventions pour tous les types de fichiers

## Structure de la Documentation

> **Mises à jour récentes (Déc. 2025)** :
> - Consolidation des overlays (`lib/s1_interaction/combined_overlay.py`) documentée dans [specs/architecture_logicielle.md](specs/architecture_logicielle.md).
> - Navigation : `NavigationService` applique désormais une compensation de mouvement et prépare l'anchor lors du setup (voir [specs/workflows.md](specs/workflows.md)).
> - Les scénarios ont été simplifiés :
>   1. **Scénario 1** (initialisation + overlay) – lancer via `python main.py` > option 1, ou `bot.scenario_initialisation()`.
>   2. **Scénario 2** (analyse locale offline) – `bot.scenario_analyse_locale()`.
>   3. **Scénario 3** (passe unique) – `bot.scenario_jeu_automatique()` ou `python scenario3.py`.
>   4. **Scénario 4** (boucle complète) – `bot.scenario_boucle_jeu_complete()` ou `python scenario4.py`.
>   Tous utilisent `run_initialization_phase()` pour gérer la difficulté et l'overlay combiné.

### Spécifications Techniques
- **[specs/architecture_fichiers.md](specs/architecture_fichiers.md)** - Architecture complète (fichiers, modules, flux)
- **[specs/logique_metier.md](specs/logique_metier.md)** - Concepts, règles métier, acteurs, invariants
- **[specs/architecture_logicielle.md](specs/architecture_logicielle.md)** - Modules, services, interactions internes
- **[specs/composants_techniques.md](specs/composants_techniques.md)** - Librairies, utilitaires, frameworks
- **[specs/workflows.md](specs/workflows.md)** - Flux d'exécution et scénarios
- **Datasets CNN** : voir `lib/s2_recognition/s22_Neural_engine/cnn/data/README.md` pour les commandes (`prepare_cnn_dataset.py`, `augment_borders.py` avec `--central-keep 10`, exclusions `unrevealed/exploded`, etc.)

### Réflexions et Stratégies
- **[thinking/strategie_resolution_minesweeper.md](thinking/strategie_resolution_minesweeper.md)** - Stratégie complète du solver Minesweeper
- **[thinking/archive/](thinking/archive/)** - Archives des stratégies implémentées

### Suivi du Projet
- **[meta/changelog.md](meta/changelog.md)** - Évolutions versionnées officielles
- **[meta/roadmap.md](meta/roadmap.md)** - Journal de développement + roadmap future

---

## Comment Utiliser

### Pour le développement quotidien :
1. **[architecture_fichiers.md](specs/architecture_fichiers.md)** - Vue complète de l'architecture
2. **[logique_metier.md](specs/logique_metier.md)** - Comprendre les concepts et règles métier
3. **[architecture_logicielle.md](specs/architecture_logicielle.md)** - Implémenter les modules et services (inclut `run_initialization_phase`)
4. **[composants_techniques.md](specs/composants_techniques.md)** - Comprendre la pile technique
5. **[workflows.md](specs/workflows.md)** - Voir les flux d'exécution détaillés (scénarios 1-4 et lanceurs `scenario3.py` / `scenario4.py`)
6. **Datasets CNN** - `lib/s2_recognition/s22_Neural_engine/cnn/data/README.md` décrit la génération/augmentation (copies `--copies 10`, zone centrale préservée 10×10, scripts `prepare_cnn_dataset.py` & `augment_borders.py`).

### Pour la planification et stratégie :
- **[strategie_resolution_minesweeper.md](thinking/strategie_resolution_minesweeper.md)** - Développement du solver

### Pour l'historique :
- **[changelog.md](meta/changelog.md)** - Consulter les évolutions par version

---

## Architecture du Projet

```
docs/
├── README.md
├── specs/
│   ├── architecture_fichiers.md    # Architecture complète (UNIFIÉ)
│   ├── logique_metier.md
│   ├── architecture_logicielle.md
│   ├── composants_techniques.md
│   └── workflows.md
├── thinking/
│   ├── strategie_resolution_minesweeper.md  # Stratégies de développement
│   └── archive/                     # Archives de réflexions
└── meta/
    ├── changelog.md
    └── roadmap.md
```

---

## Liens Utiles

- **Code source** : `../services/`, `../lib/`, `../bot_1000mines.py`
- **Interface utilisateur** : `../main.py`
- **Tests** : `../tests/`
- **Configuration** : `../lib/config.py`
