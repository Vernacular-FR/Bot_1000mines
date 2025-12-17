---
description: Alerte – cases hors champ (frontière incomplète)
---

## Problème
Quand une grande zone s’ouvre hors du viewport, les UNREVEALED hors capture ne sont pas connues de storage. Le reclustering ne peut pas marquer la frontière (UNREVEALED adjacentes aux ACTIVE) au-delà de ce qui est dans la capture.

## Impact
- `active_set`/`frontier_set` incomplets si les voisines UNREVEALED ne sont pas capturées.
- Solver peut manquer des déductions ou tourner sans actions.

## Rappel/solution
- Vision doit injecter les UNREVEALED visibles (sauf déjà connues via known_set).
- Si une zone s’ouvre en dehors du champ, recadrer/capturer de nouveau pour inclure ces UNREVEALED dans storage.
- Le state analyzer lit storage (anciennes + nouvelles) mais ne devine pas les cases hors capture.

## Suivi
- À adresser dans l’évolution navigation/recadrage : planifier un recentrage automatique sur `TO_VISUALIZE` ou sur bords actifs pour compléter la frontière.
