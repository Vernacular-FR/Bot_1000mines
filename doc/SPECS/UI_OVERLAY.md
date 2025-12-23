# Overlay UI - Spécifications Techniques

## Architecture

L'overlay UI est une surcouche visuelle injectée dans le navigateur pour afficher les informations du bot en temps réel sur la grille de jeu.

### Structure Modulaire

```
src/lib/s0_interface/s07_overlay/
├── overlay_ui.js          # Cœur de l'overlay (rendu canvas)
├── ui_controller.py       # Interface Python/JavaScript
└── INTEGRATION_EXAMPLE.py # Exemple d'intégration
```

## Système de Canvas Dynamique

### Principe de Fonctionnement

L'overlay utilise un canvas HTML5 qui s'adapte dynamiquement à la zone de jeu :

1. **Anchor Element** : Élément de référence pour la grille (`<div id="anchor"></div>`)
2. **Controller Element** : Conteneur de la zone de jeu (`<div id="control"></div>`)
3. **Canvas Overlay** : Canvas positionné par-dessus le controller

### Calcul des Dimensions

```javascript
// Taille du canvas = taille du controller
state.canvas.width = controllerRect.width;  // ~2561px
state.canvas.height = controllerRect.height; // ~1261px

// Positionnement absolu sur le controller
state.canvas.style.left = controllerRect.left + 'px';
state.canvas.style.top = controllerRect.top + 'px';
```

### Système de Coordonnées

#### STRIDE et CELL_SIZE

- **GRID** : 24×24 cellules
- **CELL_SIZE** : 24px (fixe)
- **CELL_BORDER** : 1px
- **STRIDE** : 25px = CELL_SIZE + CELL_BORDER

```javascript
// Calcul dynamique du stride basé sur l'anchor
const realStride = anchorRect.width / 24; // 600px / 24 = 25px
CONFIG.REAL_STRIDE = realStride;
CONFIG.REAL_CELL_SIZE = 24;
```

#### Offset de Rendu

Les coordonnées de rendu incluent l'offset entre l'anchor et le controller :

```javascript
const x = cell.col * stride + ANCHOR_OFFSET_X;
const y = cell.row * stride + ANCHOR_OFFSET_Y;
```

## Modes d'Affichage

### 1. Status Overlay
- Couleur des cellules selon leur état
- Bordures noires de 1px (droite et bas uniquement)
- Utilise `fillRect` pour éviter les débordements

### 2. Actions Overlay
- Cercles verts pour les actions SAFE
- Croix rouges pour les actions FLAG
- Points d'interrogation pour les GUESS

### 3. Probabilities Overlay
- Gradient rouge (100% mine) → vert (0% mine)
- Pourcentage affiché si 1% < prob < 99%

## Performance

### Optimisations

1. **Viewport Culling** : Seules les cellules visibles sont rendues
2. **RequestAnimationFrame** : Boucle de rendu à 60fps
3. **Cache des Dimensions** : Mise à jour uniquement si changement

### Logs de Debug

```javascript
console.log(`[BotUI] Canvas: ${width}x${height}`);
console.log(`[BotUI] Controller trouvé: ${controller.tagName}#${controller.id}`);
console.log(`[BotUI] Anchor offset: (${x}, ${y})`);
```

## Intégration Python

### Injection

```python
# Injection du code JavaScript
session.ui_controller.inject(driver, overlay_js_code)

# Mise à jour des données
session.ui_controller.set_overlay(driver, {
    'status': {'cells': [...]},
    'actions': {'actions': [...]},
    'probabilities': {'cells': [...]}
})
```

### Événements

- `botui:start` : Démarrage du bot
- `botui:pause` : Mise en pause
- `botui:restart` : Redémarrage de la partie

## CSS et Styles

### Menu Flottant

```css
#bot-ui-menu {
  position: fixed;
  top: 50%;
  left: 15px;
  transform: translateY(-50%);
  z-index: 9999;
}
```

### Canvas Overlay

```css
#bot-ui-canvas {
  position: absolute;
  pointer-events: none;
  z-index: 9998;
}
```

## Dépannage

### Problèmes Courants

1. **Canvas non aligné** : Vérifier que `#control` existe
2. **Taille incorrecte** : Forcer la mise à jour avec `|| !state.lastControllerRect`
3. **Offset cumulatif** : Utiliser `fillRect` pour les bordures, pas `strokeRect`

### Commandes de Debug

```javascript
// Dans la console navigateur
document.getElementById('control').getBoundingClientRect()
window.__bot_ui_state  // État interne de l'overlay
```

## Évolutions Futures

- Support du zoom navigateur
- Mode plein écran
- Thèmes personnalisables
- Export des statistiques
