# Système d'Overlay UI Temps Réel

Surcouche visuelle injectée dans le navigateur pour afficher les informations du solver en temps réel.

## Architecture

```
s07_overlay/
├── overlay_ui.js       # Module JavaScript principal (BotUI)
├── ui_controller.py    # Contrôleur Python pour injection/communication
├── ui_data_converter.py # Convertisseurs de données solver → overlay
├── types.py            # Types de données overlay
└── __init__.py         # Exports publics
```

## Fonctionnalités

### Overlay Canvas (ancré sur #anchor)
- **Synchronisation fluide** : Position mise à jour à 60 FPS via `requestAnimationFrame`
- **Canvas 2D** : Rendu performant pour les cellules et actions
- **Coordonnées relatives** : Toutes les positions sont relatives à l'anchor du jeu

### Types d'Overlays
| Overlay | Touche | Description |
|---------|--------|-------------|
| Off | `1` | Désactive l'affichage |
| Status | `2` | Affiche ACTIVE (bleu), FRONTIER (orange), MINE (rouge) |
| Actions | `3` | Affiche SAFE (cercle vert), FLAG (croix rouge), GUESS (?) |
| Probas | `4` | Affiche probabilités (gradient vert → rouge) |

### Menu de Contrôle (fixe)
- Position : coin supérieur droit
- Collapsible : clic sur le header ou touche `M`
- Sections : Contrôle Bot, Overlays, Assistance

### Raccourcis Clavier
| Touche | Action |
|--------|--------|
| `F5` | Start/Stop Bot |
| `F6` | Stop Bot |
| `1-4` | Changer d'overlay |
| `M` | Toggle menu |
| `H` | Hint (futur) |

## Utilisation Python

```python
from src.lib.s0_interface.s07_overlay import get_ui_controller, UIOverlayType

# Obtenir le contrôleur (singleton)
ui = get_ui_controller()

# Injecter dans le navigateur
ui.inject(driver)

# Changer d'overlay
ui.set_overlay(driver, UIOverlayType.STATUS)

# Mettre à jour les données
from src.lib.s0_interface.s07_overlay import StatusCellData
cells = [StatusCellData(col=0, row=0, status='ACTIVE')]
ui.update_status(driver, cells)

# Afficher un toast
ui.show_toast(driver, "Action effectuée", "success")
```

## Intégration Game Loop

L'UI est automatiquement :
1. **Injectée** à la création de session (`s0_session_service.py`)
2. **Mise à jour** après chaque solve (`s9_game_loop.py`)

## Couleurs

```javascript
COLORS = {
  ACTIVE: 'rgba(0, 120, 255, 0.35)',     // Bleu
  FRONTIER: 'rgba(255, 165, 0, 0.35)',   // Orange
  MINE: 'rgba(255, 0, 0, 0.5)',          // Rouge
  TO_VISUALIZE: 'rgba(0, 255, 150, 0.4)', // Vert clair
  SAFE: 'rgba(0, 255, 0, 0.9)',          // Vert vif
  FLAG: 'rgba(255, 50, 50, 0.9)',        // Rouge vif
  GUESS: 'rgba(255, 255, 0, 0.9)',       // Jaune
}
```

## API JavaScript (window.BotUI)

```javascript
BotUI.init()                    // Initialise l'UI
BotUI.destroy()                 // Détruit l'UI
BotUI.setOverlay(type)          // 'off', 'status', 'actions', 'probabilities'
BotUI.updateData(type, data)    // Met à jour les données d'un overlay
BotUI.render()                  // Force un re-render
BotUI.showToast(msg, type)      // Affiche une notification
BotUI.getState()                // Retourne l'état actuel
BotUI.isRunning()               // True si bot marqué comme running
```

## Évolutions Futures

- [ ] **Hint visuel** : Suggestion de coup au clic sur `H`
- [ ] **Auto-solve** : Mode automatique pas à pas
- [ ] **Statistiques** : Compteurs temps réel (mines restantes, probabilité globale)
- [ ] **Export** : Capture d'écran avec overlay
