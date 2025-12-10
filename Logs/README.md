# Système de Logging Centralisé

Ce dossier contient le système de logging centralisé pour le bot 1000mines.com.

## Structure

```
Logs/
├── __init__.py          # Package Python - export des fonctions principales
├── logger.py            # Module principal de logging
└── *.json               # Fichiers de logs générés automatiquement
```

## Fonctionnalités

### Types de logs

1. **Logs d'extraction** (`game_state_*.json`)
   - Informations de débogage lors de l'extraction de l'état du jeu
   - Canvas info, variables globales, structure DOM
   - Succès/échec de l'extraction

2. **Logs d'actions du bot** (`bot_action_*.json`)
   - Actions effectuées par le bot (clics, déplacements)
   - Coordonnées, méthodes utilisées, résultats
   - Erreurs rencontrées

### Format des fichiers

Les logs sont sauvegardés en format JSON avec la structure suivante :

```json
{
  "timestamp": "20251129_212200",
  "extraction_type": "game_state",
  "url": "https://www.1000mines.com/",
  "success": true,
  "debug_info": {...},
  "game_state": {...}
}
```

## Utilisation

### Import dans les modules

```python
# Import du système de logging
from Logs.logger import save_extraction_log, save_bot_log
```

### Logs d'extraction

```python
# Sauvegarder les résultats d'une extraction
save_extraction_log(debug_info, game_state, "game_state", url)
```

### Logs d'actions du bot

```python
# Logger une action réussie
save_bot_log("click_cell", {
    "grid_x": x, 
    "grid_y": y, 
    "right_click": False
}, True)

# Logger une erreur
save_bot_log("click_cell", {
    "grid_x": x, 
    "grid_y": y,
    "error": str(e)
}, False)
```

## Avantages

1. **Centralisation** : Tous les logs sont dans un seul dossier
2. **Organisation** : Fichiers avec timestamps et types clairs
3. **Réutilisabilité** : Le logger peut être utilisé par tous les modules
4. **Maintenance** : Un seul endroit pour modifier la logique de logging
5. **Analyse** : Format JSON structuré pour faciliter l'analyse

## Nettoyage automatique

Les anciens logs sont supprimés automatiquement lors de la réorganisation du projet. Seuls les logs pertinents sont conservés.

## Exemples d'utilisation

### Dans `game_state_extractor.py`
```python
# Succès de l'extraction
save_extraction_log(debug_info, result, "game_state", self.url)

# Échec de l'extraction
save_extraction_log(debug_result, None, "game_state", self.url)
```

### Dans `game_controller.py`
```python
# Action de clic réussie
save_bot_log("click_cell", {
    "grid_x": grid_x,
    "grid_y": grid_y,
    "right_click": right_click,
    "screen_x": screen_x,
    "screen_y": screen_y,
    "method": "javascript"
}, True)

# Erreur de clic
save_bot_log("click_cell", {
    "grid_x": grid_x,
    "grid_y": grid_y,
    "error": str(e)
}, False)
```

### Dans `bot_1000mines.py`
```python
# Début de l'extraction
save_bot_log("extract_game_state_start", {
    "difficulty": difficulty,
    "method": "javascript"
}, True)

# Succès de l'extraction
save_bot_log("extract_game_state_success", {
    "difficulty": difficulty,
    "grid_width": width,
    "grid_height": height,
    "mines": mines
}, True)
```
