# Journal solver — V0-1 (des réflexes vers l’analytique)

Ce journal couvre la période du **28 novembre 2025** au **9 décembre 2025**.
À ce moment-là, je ne cherche pas encore “le solveur ultime”. Je cherche surtout un enchaînement qui fait progresser une grille sans partir dans une usine à gaz.

---

## 28 novembre 2025 — Les règles locales comme point de départ

Je commence avec des réflexes simples :
une valeur effective qui tombe à zéro libère des clics sûrs, et une valeur effective qui égale le nombre de voisines fermées permet de poser des drapeaux.

Ce n’est pas élégant, mais c’est immédiat.
Et surtout, ça m’apprend une première loi du démineur automatisé : si je peux réduire le problème vite, je gagne plus que si j’essaie d’être “intelligent” trop tôt.

---

## 1–3 décembre 2025 — Réduction frontière : la première vraie brique

Sans le nommer au début, je construis une phase de réduction qui tourne en boucle sur la frontière.
Elle ne fait rien de “savant”, mais elle a une propriété précieuse : elle est déterministe, et elle stabilise l’état.

Je remarque que ce mécanisme vaut mieux que de hardcoder des motifs.
Les motifs deviennent presque un effet de bord de la propagation, plutôt qu’une logique à maintenir à la main.

---

## 3–9 décembre 2025 — Le CSP : promesse théorique, piège pratique

Je cherche un solveur analytique existant et je tombe sur le CSP.
Sur des petits cas, le backtracking donne l’impression d’être exactement ce qu’il faut : on énumère, on prouve, on déduit.

Mais très vite, je rencontre le problème qui va structurer toute la suite : les **zones tronquées**.

Le plus frustrant, c’est que ça ne bloque pas uniquement des cas “difficiles”. J’ai déjà des frontières tronquées qui se résolvent à 0%, alors qu’elles contiennent des situations triviales que mon réducteur de frontière sait traiter… mais pas dans ces conditions.

Quand une composante est “fermée sur elle-même”, le CSP est propre.
Quand elle est tronquée (manque de contexte, segmentation imparfaite, frontière pas stabilisée), le CSP devient fragile : soit il ne trouve rien, soit il “travaille” sur une réalité qui bouge.

Je comprends alors l’essentiel :

Le CSP n’est pas un moteur autonome. Il ne devient bon que s’il arrive après une réduction solide.

---

## 9 décembre 2025 — La conclusion avant V2

Je termine V0-1 avec une direction claire.
En V2, je vais formaliser une chaîne de propagation plus riche (règles locales puis contraintes entre voisines), et garder le CSP comme un second niveau.

Mais surtout, je vais arrêter de “zoner puis réduire”.
Si je veux éviter les zones tronquées, je dois **réduire avant de segmenter** : la réduction doit précéder le zonage, pas l’inverse.