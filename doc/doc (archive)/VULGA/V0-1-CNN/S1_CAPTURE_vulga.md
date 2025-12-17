# Journal capture — V0-1 (screenshots Selenium)
Ce journal couvre la période du **28 novembre 2025** au **9 décembre 2025**.
Dans cette première version, je n’ai pas encore la capture “directe” du canvas : je fais ce que tout le monde fait au début… je prends des screenshots.

---

## 28 novembre 2025 — Le premier mur : la lenteur

Dès que j’essaie d’imaginer une boucle complète (capture → analyse → action → recapture), je comprends que la capture est le vrai goulot d’étranglement.
Avec Selenium, une capture d’écran est lourde : au minimum **~1,5 s**, parfois plusieurs secondes.

Ça change tout.
À partir de là, je commence à raisonner “pipeline” :

- si je fais deux passes de vision, je double la peine,
- si je fais une analyse trop ambitieuse, j’explose le temps de tour,
- et si je veux itérer vite, je dois minimiser les allers-retours.

---

## 30 novembre 2025 — L’anchor, la seule chose réellement stable

Un screenshot n’a de valeur que si je sais exactement comment le relier à la grille.
Or, la grille est paradoxale : elle est évidente pour l’œil humain, mais le programme n’a aucun “bord de tableau” dans le DOM.

Je finis donc par traiter un point comme une vérité : l’**anchor**.
Tout découle de lui : alignement, offsets, conversion cellule→pixel. Et quand l’anchor bouge (même légèrement), j’ai l’impression que tout le bot s’effondre.

---

## 9 décembre 2025 — La conclusion avant la refonte

Je sors de V0-1 avec une conviction simple : les screenshots Selenium sont suffisants pour prototyper, mais trop lents pour un bot “sérieux”.

La V2 (dès le **10 décembre**) va pivoter vers une capture canvas beaucoup plus directe : extraire les pixels sans passer par un screenshot complet, et donc rendre la boucle enfin réactive.
