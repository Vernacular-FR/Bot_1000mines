# Journal interface — V0-1 (pilotage Selenium)

Ce journal couvre la période du **28 novembre 2025** au **9 décembre 2025**.
L’objectif n’est pas encore d’avoir une API propre, mais juste de rendre l’interface pilotable sur un jeu canvas, sans décalage entre ce que je vois et ce que je clique.

---

## 28 novembre 2025 — Le problème n’est pas “cliquer”, c’est “viser”

Sur un site classique, un clic est un clic.
Sur un canvas, un clic n’existe que si je sais traduire “une cellule (x,y)” en “un pixel écran” de manière stable.

Je pars donc avec Selenium et ses enchaînements d’actions. Très vite, je découvre que le moindre flou dans le repère (anchor, offset, viewport) me donne un bot qui *agit*… mais pas *au bon endroit*.

---

## 2 décembre 2025 — Les interactions Selenium deviennent toxiques

Au-delà de la lenteur, il y a un problème plus insidieux : certaines interactions Selenium donnent des effets de bord.
Dans mon cas, ça se traduit par un comportement immonde : `ActionChains.move_by_offset()` a l’air de marcher, parce que l’écran “translate”… mais la logique JavaScript reste au point initial. Résultat : j’ai un monde où le visuel bouge, mais pas le repère logique, donc mes clics finissent systématiquement à côté.

À ce stade, je commence à migrer une partie du pilotage vers des événements JavaScript (move/click) : c’est plus direct, et surtout plus prédictible.

---

## 9 décembre 2025 — Conclusion de V0-1

L’interface est encore imparfaite, mais je comprends la règle d’or :

Si l’interface n’est pas déterministe, la vision et le solver ne peuvent jamais être fiables.

La refonte V2 (dès le 10 décembre) va formaliser cette idée en contrat simple : un repère (anchor), une conversion, des actions contrôlées.