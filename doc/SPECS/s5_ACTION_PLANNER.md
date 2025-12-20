---
description: Spécification technique de la couche s5_actionplanner (planification et exécution d'actions)
---

# S05 ACTIONPLANNER – Spécification technique

## 1. Mission (ce que fait s5)

s5_actionplanner transforme une liste d’actions solver (`SolverAction`) en un plan d’exécution et **l'exécute en temps-réel** via le driver Selenium.

Dans la version actuelle, s5 est devenu l'agent actif du bot :
- il **ordonne** et **convertit** des actions.
- il **calcule les coordonnées relatives** à l'anchor.
- il **exécute** les clics via JavaScript.
- il **surveille les vies** et gère les délais de stabilisation (2s) après une explosion.
- il ne fait **aucun déplacement viewport** (pour l'instant).

Justification : Centraliser l'exécution dans le planner permet une réactivité maximale (clic immédiat après déduction) et simplifie la boucle de jeu qui n'a plus à gérer les états d'explosion.

## 2. Contrat (entrées / sorties)

### 2.1 Entrée : `SolverAction`

Type défini dans `src/lib/s4_solver/types.py` :
- `coord: (col, row)`
- `action: ActionType` (`FLAG`, `SAFE`, `GUESS`)
- `confidence: float`
- `reasoning: str`

### 2.2 Sortie : `PlannedAction`

Type défini dans `src/lib/s5_planner/types.py` :
- `coord: (col, row)`
- `action: ActionType`
- `screen_point: ScreenPoint` (Coordonnées relatives à l'anchor)
- `priority: int`
- `confidence: float`
- `reasoning: str`

### 2.3 API

- `plan(input: PlannerInput, driver: WebDriver, extractor: GameInfoExtractor) -> List[PlannedAction]`

## 3. Règles d'exécution

### 3.1 Ordre d’exécution (Priorités)

1. `FLAG` (Priorité 1)
2. `SAFE` (Priorité 2)
3. `GUESS` (Priorité 3)

### 3.2 Coordonnées Robustes (Anchor-Relative)

Les coordonnées sont calculées **relativement à l'élément `#anchor`** :
- `rel_x = canvas_x + cell_center_offset`
- `rel_y = canvas_y + cell_center_offset`

Le script JavaScript d'exécution (`actions.py`) utilise `getBoundingClientRect()` sur l'anchor au moment du clic pour retrouver la position absolue. Cela garantit la précision même si le viewport bouge pendant la rafale de clics.

### 3.3 Exécution Temps-Réel et Vie

Si un `driver` et un `extractor` sont fournis :
1. Chaque action est exécutée immédiatement après sa planification.
2. Le nombre de vies est vérifié via `extractor.get_game_info().lives`.
3. Si une vie est perdue (explosion), le bot marque une pause de **2 secondes** pour laisser les animations se stabiliser avant de continuer ou de rendre la main.

## 4. Invariants

- s5 ne modifie pas la sémantique des actions : il ne fait que réordonner / convertir / exécuter.
- s5 ne crée jamais de coordonnées nouvelles (il utilise le `converter` pour transformer la grille en relatif).
- s5 ne lit pas la grille : la vérité jeu (topologie, focus, etc.) vit dans s3_storage.

## 5. Intégration Technique

Le planner utilise directement les fonctions de `src.lib.s0_browser.actions` :
- `click_left(driver, rel_x, rel_y)`
- `click_right(driver, rel_x, rel_y)`

Il n'y a plus de module `s6_executor` séparé.