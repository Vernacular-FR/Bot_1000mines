# Architecture des Fichiers - Bot Minesweeper

> **Portée** : Structure physique des fichiers et modules uniquement

---

## Structure Globale

```
Bot 1000mines-com/
├── main.py                       # Point d'entrée
├── src/                          # Code applicatif
│   ├── lib/                      # Cœur technique modulaire
│   │   ├── s0_navigation/        # Navigation, browser & coordonnées
│   │   ├── s1_capture/           # Capture et overlays interface/grille
│   │   ├── s2_recognition/       # Template matching & mapping vision
│   │   ├── s3_tensor/            # TensorGrid, GamePersistence, types
│   │   └── s4_solver/            # Segmentation, CSP, overlays solver
│   ├── services/                 # Services métier orchestrateurs
│   │   ├── s0_test_patterns_service.py
│   │   ├── s1_session_setup_service.py
│   │   ├── s1_zone_capture_service.py
│   │   ├── s2_optimized_analysis_service.py
│   │   ├── s3_game_solver_service.py
│   │   ├── s4_action_executor_service.py
│   │   └── s5_game_loop_service.py
│   ├── apps/                     # Scénarios bot_1000mines, CLI
│   └── tests/                    # Tests fonctionnels sous src
├── docs/                         # Documentation
├── tests/                        # Tests unitaires
├── temp/                         
└── logs/                         # Logs centralisés
```

---

## Structure temp/ par Partie

```
temp/games/{game_id}/
├── s0_full_pages/               # Captures viewport complet
├── s0_interface/                # Métadonnées interface + overlays
├── s1_zone/                     # Zones de jeu capturées
├── s1_grid/                     # Données de grille
├── s2_analysis/                 # Rapports + overlays d'analyse
├── s3_solver/                   # Overlays du solver
├── s4_actions/                  # Données d'actions
├── grid_state_db.json          # Base de données grille
└── metadata.json               # Métadonnées partie
```

---

## Configuration Chemins

Chemins centralisés dans `lib/config.py` :

```python
def get_game_paths(game_id: str) -> dict:
    base = f"temp/games/{game_id}"
    return {
        'full_pages': f"{base}/s0_full_pages",
        'interface': f"{base}/s0_interface",
        'zone': f"{base}/s1_zone",
        'grid': f"{base}/s1_grid",
        'analysis': f"{base}/s2_analysis",
        'solver': f"{base}/s3_solver",
        'actions': f"{base}/s4_actions",
        'grid_db': f"{base}/grid_state_db.json",
        'metadata': f"{base}/metadata.json"
    }
```
