# Restructuration du Dossier Temp pour Organisation par Partie

## Objectif
Organiser tous les éléments d'une partie dans des dossiers séparés avec un identifiant unique basé sur la date et l'heure.

## Structure Actuelle (Problèmes)
```
temp/
├── screenshots/
│   ├── game_loop/
│   │   ├── game_loop_20251203_002550_iter_1.png
│   │   └── game_loop_20251203_002550_iter_2.png
│   └── zone_screenshots/
│       └── zone_*.png
├── analysis/
│   └── reports/
│       └── batch_analysis_report_*.json
├── grid_state_db/
│   └── game_loop_*.json
└── solver/
    └── overlays/
        └── zone_*_solver_overlay.png
```

**Problèmes :**
- Tous les mélangés dans les mêmes dossiers
- Difficile de retrouver les éléments d'une partie spécifique
- Les noms de fichiers sont longs et complexes
- Pas de séparation claire entre les parties
- Base de données persistante globale (temp/grid_state_db.json) mélange les parties

## Structure Proposée (Solution)

### Identifiant de Partie
Format : `YYYYMMDD_HHMMSS` (ex: `20251203_002550`)

### Nouvelle Structure
```
temp/
└── games/
    └── 20251203_002550/           # ID unique de la partie
        ├── metadata.json          # Infos de la partie (durée, score, etc.)
        ├── game_state.json        # BASE DE DONNÉES CENTRALISÉE DE LA PARTIE
        ├── s0_full_pages/         # Screenshots de pages complètes
        │   ├── iter_01.png        # Page complète itération 1
        │   ├── iter_02.png        # Page complète itération 2
        │   └── ...
        ├── s0_interface/          # Screenshots d'interface (viewport)
        │   ├── iter_01.png        # Interface itération 1
        │   ├── iter_02.png        # Interface itération 2
        │   └── ...
        ├── s1_zone/               # Screenshots de zone capturée
        │   ├── 20251203_002550_zone_-12_-6_13_7.png    # Zone avec coordonnées
        │   ├── 20251203_002551_zone_-12_-6_13_7.png    # Itération suivante
        │   └── ...
        ├── s2_analysis/           # Analyses et grilles
        │   ├── 20251203_002550_analysis_-12_-6_13_7.json   # Grid DB avec coordonnées
        │   ├── 20251203_002550_overlay_-12_-6_13_7.png # Overlay analyse
        │   ├── 20251203_002551_analysis_-12_-6_13_7.json   # Itération suivante
        │   └── final.png          # Analyse finale
        ├── s3_solver/             # Résolutions du solver
        │   ├── 20251203_002550_solver_-12_-6_13_7.png  # Overlay solver avec coordonnées
        │   ├── 20251203_002551_solver_-12_-6_13_7.png  # Itération suivante
        │   └── final.png          # Solver final
        └── s4_actions/            # Actions exécutées
            ├── 20251203_002550_actions_-12_-6_13_7.json # Actions avec coordonnées
            ├── 20251203_002551_actions_-12_-6_13_7.json # Itération suivante
            └── summary.json       # Résumé de toutes les actions
```

## Base de Données Centralisée

### Positionnement
**`temp/games/{game_id}/game_state.json`** - Base de données unique pour la partie

### Contenu
```json
{
  "metadata": {
    "game_id": "20251203_002550",
    "created_at": "2025-12-03T00:25:50Z",
    "last_updated": "2025-12-03T00:28:15Z",
    "iterations": 5,
    "total_actions": 42
  },
  "current_state": {
    "game_status": "PLAYING",
    "score": 0,
    "flags_placed": 3,
    "cells_revealed": 39
  },
  "cells": [
    {
      "x": -38,
      "y": -28,
      "type": "unrevealed",
      "confidence": 1.0,
      "state": "TO_PROCESS",
      "last_updated": "2025-12-03T13:50:09.016831+00:00",
      "metadata": {}
    }
  ],
  "iteration_history": [
    {
      "iteration": 1,
      "timestamp": "2025-12-03T00:26:10Z",
      "actions_taken": 8,
      "files": {
        "viewport": "s0_full_pages/iter_01.png",
        "zone": "s1_zone/20251203_002550_zone_-38_-28_50_16.png",
        "analysis": "s2_analysis/20251203_002550_analysis_-38_-28_50_16.json",
        "solver": "s3_solver/20251203_002550_solver_-38_-28_50_16.png",
        "actions": "s4_actions/20251203_002550_actions_-38_-28_50_16.json"
      }
    }
  ]
}
```

## Configuration de Production

### Modes de Fonctionnement

#### Mode Développement (par défaut)
```python
PRODUCTION_CONFIG = {
    "save_viewport": True,           # s0_full_pages/
    "save_interface": True,          # s0_interface/
    "save_zone_screenshots": True,   # s1_zone/
    "save_analysis_files": True,     # s2_analysis/
    "save_solver_overlays": True,     # s3_solver/
    "save_action_reports": True,     # s4_actions/
    "save_final_state": True         # game_state.json
}
```

#### Mode Production (optimisé)
```python
PRODUCTION_CONFIG = {
    "save_viewport": False,          # Économie d'espace
    "save_interface": False,         # Économie d'espace
    "save_zone_screenshots": False,  # Économie d'espace
    "save_analysis_files": False,    # Économie d'espace
    "save_solver_overlays": False,    # Économie d'espace
    "save_action_reports": False,     # Économie d'espace
    "save_final_state": True         # Uniquement la base de données
}
```

#### Mode Monitoring (intermédiaire)
```python
PRODUCTION_CONFIG = {
    "save_viewport": False,
    "save_interface": True,           # Pour debug interface
    "save_zone_screenshots": False,
    "save_analysis_files": False,
    "save_solver_overlays": False,
    "save_action_reports": True,      # Pour audit des actions
    "save_final_state": True
}
```

### Implémentation Technique

### 1. Gestionnaire de Configuration
```python
class ProductionConfig:
    def __init__(self, mode="development"):
        self.mode = mode
        self.config = self._get_config(mode)
    
    def _get_config(self, mode):
        configs = {
            "development": {
                "save_viewport": True,
                "save_interface": True,
                "save_zone_screenshots": True,
                "save_analysis_files": True,
                "save_solver_overlays": True,
                "save_action_reports": True,
                "save_final_state": True
            },
            "production": {
                "save_viewport": False,
                "save_interface": False,
                "save_zone_screenshots": False,
                "save_analysis_files": False,
                "save_solver_overlays": False,
                "save_action_reports": False,
                "save_final_state": True
            },
            "monitoring": {
                "save_viewport": False,
                "save_interface": True,
                "save_zone_screenshots": False,
                "save_analysis_files": False,
                "save_solver_overlays": False,
                "save_action_reports": True,
                "save_final_state": True
            }
        }
        return configs.get(mode, configs["development"])
    
    def should_save(self, file_type):
        return self.config.get(f"save_{file_type}", False)
```

### 2. Modification des Services

#### GameLoopService
```python
def execute_single_pass(self, iteration_num: int = 1) -> Dict[str, Any]:
    config = ProductionConfig(self.production_mode)
    
    # 0. Capture du viewport (si activé)
    if config.should_save("viewport"):
        viewport_result = self._capture_viewport(iteration_num)
        pass_result['files_saved'].append(viewport_result['screenshot_path'])
    
    # 1. Capture de la zone (si activé)
    if config.should_save("zone_screenshots"):
        capture_result = self.capture_service.capture_game_zone_inside_interface(
            self.session_service, iteration_num=iteration_num
        )
    
    # 2. Analyse (toujours effectuée, sauvegarde optionnelle)
    analysis_result = self.analysis_service.analyze_from_path(...)
    if config.should_save("analysis_files"):
        pass_result['files_saved'].append(analysis_result['db_path'])
    
    # 3. Solver (toujours effectué, sauvegarde optionnelle)
    solve_result = self.solver_service.solve_from_db_path(...)
    if config.should_save("solver_overlays"):
        pass_result['files_saved'].append(solver_save_path)
    
    # 4. Actions (toujours exécutées, sauvegarde optionnelle)
    if config.should_save("action_reports"):
        pass_result['files_saved'].append(actions_save_path)
    
    # 5. Mise à jour base de données centrale (toujours)
    self._update_central_db(iteration_num, pass_result)
    
    return pass_result
```

### 3. Base de Données Centrale
```python
class CentralGameDB:
    def __init__(self, game_id, game_base_path):
        self.game_id = game_id
        self.db_path = f"{game_base_path}/game_state.json"
        self.data = self._load_or_create()
    
    def update_iteration(self, iteration_num, pass_result):
        """Met à jour la base avec les résultats d'une itération"""
        self.data['metadata']['last_updated'] = datetime.now().isoformat()
        self.data['metadata']['iterations'] = max(
            self.data['metadata'].get('iterations', 0), 
            iteration_num
        )
        
        # Ajouter à l'historique
        iteration_entry = {
            "iteration": iteration_num,
            "timestamp": datetime.now().isoformat(),
            "actions_taken": pass_result.get('actions_executed', 0),
            "files": self._map_files(pass_result.get('files_saved', []))
        }
        self.data['iteration_history'].append(iteration_entry)
        
        self.save()
```

## Actions à Effectuer

### 1. **Suppression de l'ancienne base globale**
- [ ] Supprimer `temp/grid_state_db.json`
- [ ] Supprimer le dossier `temp/grid_state_db/`
- [ ] Modifier `lib/config.py` pour ne plus référencer ces chemins

### 2. **Implémentation de la base centrale**
- [ ] Créer `CentralGameDB` class
- [ ] Intégrer dans `GameLoopService`
- [ ] Modifier tous les services pour utiliser la base centrale

### 3. **Ajout du système de configuration**
- [ ] Créer `ProductionConfig` class
- [ ] Ajouter paramètre `production_mode` aux services
- [ ] Modifier les points de sauvegarde conditionnels

### 4. **Mise à jour des chemins**
- [ ] Modifier `lib/config.py` pour pointer vers `temp/games/{game_id}/`
- [ ] Mettre à jour tous les services
- [ ] Tester tous les modes de fonctionnement

### 5. **Nettoyage et optimisation**
- [ ] Supprimer les fichiers temporaires inutiles
- [ ] Optimiser les accès disques
- [ ] Ajouter compression optionnelle pour la production

## Avantages

### 1. **Performance**
- Base unique par partie = accès plus rapide
- Moins de fichiers en production = économie d'espace
- Configuration flexible = adaptation au besoin

### 2. **Clarté**
- Une seule source de vérité par partie
- Historique complet dans un seul fichier
- Modes clairs (dev/prod/monitoring)

### 3. **Maintenance**
- Nettoyage facile (supprimer un dossier de partie)
- Export simple d'une partie complète
- Debug ciblé selon le mode

### 4. **Scalabilité**
- Support de milliers de parties sans pollution
- Archive facile des anciennes parties
- Monitoring léger en production

## Avantages

### 1. **Clarté**
- Chaque partie a son dossier propre
- Facile de naviguer dans l'historique
- Structure hiérarchique logique

### 2. **Traçabilité**
- On peut suivre l'évolution itération par itération
- Corrélation directe entre screenshot, analyse et actions
- Métadonnées centralisées

### 3. **Maintenance**
- Nettoyage facile (supprimer un dossier de partie)
- Export simple d'une partie complète
- Comparaison entre parties

### 4. **Performance**
- Moins de fichiers par dossier = accès plus rapide
- Structure prédictible pour les requêtes

## Implémentation Technique

### 1. Générateur d'ID de Partie
```python
import time

def generate_game_id():
    """Génère un ID unique basé sur la date/heure actuelle"""
    return time.strftime("%Y%m%d_%H%M%S")
```

### 2. Création de Structure
```python
import os
import json

def create_game_structure(game_id):
    """Crée la structure complète pour une partie"""
    base_path = f"temp/games/{game_id}"
    
    # Créer tous les dossiers avec indices
    folders = [
        "s0_full_pages",
        "s0_interface", 
        "s1_zone",
        "s1_grid",
        "s2_analysis",
        "s3_solver",
        "s4_actions"
    ]
    
    for folder in folders:
        os.makedirs(f"{base_path}/{folder}", exist_ok=True)
    
    # Créer le fichier de métadonnées
    metadata = {
        "game_id": game_id,
        "start_time": time.time(),
        "start_datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "difficulty": None,  # Sera rempli plus tard
        "iterations": 0,
        "total_actions": 0,
        "final_state": "playing",
        "duration": 0
    }
    
    with open(f"{base_path}/metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
```

### 3. Intégration dans GameLoopService

#### Modification du constructeur
```python
def __init__(self, session_service: SessionSetupService, ...):
    # ... code existant ...
    
    # Générer l'ID de partie
    self.game_id = generate_game_id()
    self.game_base_path = f"temp/games/{self.game_id}"
    
    # Créer la structure
    create_game_structure(self.game_id)
```

#### Sauvegarde des éléments par itération
```python
def execute_next_iteration(self, iteration_idx: int):
    # 1. Capture de page complète (s0_full_pages)
    # ... capture page complète ...
    full_page_path = f"{self.game_base_path}/s0_full_pages/iter_{iteration_idx:02d}.png"
    # Sauvegarder screenshot complet
    
    # 2. Capture d'interface (s0_interface) 
    # ... capture viewport/interface ...
    interface_path = f"{self.game_base_path}/s0_interface/iter_{iteration_idx:02d}.png"
    # Sauvegarder screenshot interface
    
    # 3. Capture de zone (s1_zone)
    capture_result = self.capture_service.capture_game_zone_inside_interface(self.session_service)
    zone_path = f"{self.game_base_path}/s1_zone/iter_{iteration_idx:02d}.png"
    shutil.copy2(capture_result['zone_path'], zone_path)
    
    # 4. Analyse et sauvegarde grid (s1_grid)
    analysis_result = self.analysis_service.analyze_from_path(zone_path, zone_bounds=zone_bounds)
    grid_path = f"{self.game_base_path}/s1_grid/iter_{iteration_idx:02d}.json"
    shutil.copy2(analysis_result['db_path'], grid_path)
    
    # 5. Sauvegarde analyse (s2_analysis)
    if analysis_result.get('overlay_path'):
        analysis_overlay_path = f"{self.game_base_path}/s2_analysis/iter_{iteration_idx:02d}.png"
        shutil.copy2(analysis_result['overlay_path'], analysis_overlay_path)
    
    # 6. Résolution solver (s3_solver)
    solve_result = self.solver_service.solve_from_db_path(analysis_result['db_path'], zone_path)
    if solve_result.get('overlay_path'):
        solver_overlay_path = f"{self.game_base_path}/s3_solver/iter_{iteration_idx:02d}.png"
        shutil.copy2(solve_result['overlay_path'], solver_overlay_path)
    
    # 7. Actions (s4_actions)
    solve_result['analysis_result'] = analysis_result
    game_actions = self.solver_service.convert_actions_to_game_actions(solve_result)
    
    actions_data = {
        "iteration": iteration_idx,
        "timestamp": time.time(),
        "actions": [action.to_dict() for action in game_actions],
        "execution_result": execution_result
    }
    
    with open(f"{self.game_base_path}/s4_actions/iter_{iteration_idx:02d}.json", "w") as f:
        json.dump(actions_data, f, indent=2)
    
    # 8. Exécution
    execution_result = self.action_executor.execute_batch(game_actions)
    self.stats['total_actions'] += execution_result['executed_count']
```

#### Finalisation de la partie
```python
def play_game(self) -> GameResult:
    # ... boucle de jeu ...
    
    # Mettre à jour les métadonnées finales
    metadata_path = f"{self.game_base_path}/metadata.json"
    with open(metadata_path, "r") as f:
        metadata = json.load(f)
    
    metadata.update({
        "end_time": time.time(),
        "end_datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration": total_time,
        "iterations": iteration,
        "total_actions": self.stats['total_actions'],
        "final_state": result.final_state.value,
        "success": result.success
    })
    
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return result
```

## Migration

### Étape 1 : Créer la nouvelle structure
- Implémenter les fonctions de création de structure
- Modifier GameLoopService pour utiliser la nouvelle structure

### Étape 2 : Migration progressive
- Garder l'ancienne structure en parallèle
- Utiliser un flag pour choisir la structure
- Tester avec quelques parties

### Étape 3 : Nettoyage
- Supprimer l'ancienne structure une fois validée
- Mettre à jour tous les scénarios

## Conclusion

Cette restructuration apportera :
- **Clarté** : Organisation par partie
- **Traçabilité** : Historique complet itération par itération  
- **Maintenance** : Nettoyage et export simplifiés
- **Performance** : Meilleure organisation des fichiers

C'est une évolution naturelle pour un bot qui gère des parties complètes avec beaucoup de données à conserver.
