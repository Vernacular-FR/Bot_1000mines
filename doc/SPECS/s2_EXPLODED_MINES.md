# Gestion des Mines Explosées

## Flux de Données

1. **Vision**
   - Détecte une case "exploded" (explosion visuelle)
   - Classifie en `CONFIRMED_MINE`
2. **Storage**
   - Convertit `exploded` -> `CONFIRMED_MINE`
   - Stocke l’état logique (non prise en compte comme UNREVEALED)
3. **Status Analyzer**
   - `CONFIRMED_MINE` -> `solver_status = MINE`
   - Écarte des frontiers et des zones actives
4. **CSP / Solver**
   - Travaille uniquement sur `UNREVEALED`
   - Les `CONFIRMED_MINE` sont ignorées et ne génèrent pas de FLAG

## Pourquoi des FLAG sur des mines explosées ?

- Si l’explosion se produit **après le calcul des actions**, les FLAG déjà planifiés s’exécutent quand même.
- Si l’explosion se produit **hors viewport**, la vision ne capture pas l’état `exploded` et la cellule reste `UNREVEALED` dans le storage.

## Contre-mesures

1. **Vision élargie** : capturer au moins une marge autour de la zone visible pour couvrir les explosions en périphérie.
2. **Invalidation d’actions** : après un événement d’explosion, purger ou revalider la file d’actions.
3. **Marquage côté Planner** : si une explosion est détectée (perte de vie), marquer les coordonnées concernées en `CONFIRMED_MINE` dans le storage pour la prochaine itération.

## Règles de Cohérence

- Toute cellule `CONFIRMED_MINE` doit être exclue des frontiers.
- Les `FLAG` ne doivent jamais être appliqués sur une cellule `CONFIRMED_MINE` si l’état est à jour.
- En cas de doute (viewport partiel), privilégier le marquage manuel côté Planner sur les coordonnées suspectes.

## Points à Surveiller

- **Viewport partiel** : explosions en dehors de la capture => état obsolète.
- **Asynchronisme** : actions calculées avant l’explosion => replanifier si possible.
- **Logs** : vérifier que les logs de vision indiquent bien la détection des `exploded` après un hit.
