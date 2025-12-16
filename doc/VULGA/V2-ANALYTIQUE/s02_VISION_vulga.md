# Journal vision — V2 (template matching centré, en couleur)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
Après la phase V0-1, mon objectif n’est plus d’“essayer des trucs” : je veux une vision déterministe, robuste, et surtout assez rapide pour que le bot puisse boucler.

---
## 10 décembre 2025 — Lire le canvas comme une source de pixels

Le déclic, c’est d’arrêter de capturer l’écran et de récupérer l’information directement depuis le canvas.
Ça change la nature du problème : moins de lenteur, moins d’aléas, et une maîtrise bien plus fine de ce que je considère comme “l’image de la grille”.

Je n’ai pas instrumenté des métriques millisecondes ultra propres à ce moment-là, mais la différence est immédiatement perceptible : la boucle devient enfin réactive.

## 12 décembre 2025 — CenterTemplateMatcher : petit, centré, et fidèle à la couleur

Je corrige une erreur qui revenait sans cesse : perdre de l’information en binarisant trop tôt.
En V2, je conserve la couleur et je me concentre sur une petite zone centrale.

Ce choix est volontairement minimaliste.
Il ignore naturellement beaucoup de bruit périphérique (éclats, artefacts), et surtout il évite de retomber dans une machine à gaz faite de pixels “confirmants/infirmants”.

## 14 décembre 2025 — La vision devient une brique stable

À partir de là, je ne passe plus mon temps à “réparer la reconnaissance”.
La vision devient une brique stable, et je peux enfin concentrer l’effort sur la résolution.

La conséquence la plus importante est presque philosophique : si le solver se trompe, ce n’est plus parce que la vision hallucine.

## 15 décembre 2025 — Vision “plug-and-play” dans le pipeline live

Je consolide l’intégration : la vision n’est plus un script à part, c’est un service qui prend une image recomposée et renvoie des matches exploitables par le storage/solver.
Et surtout, l’overlay de vision est rangé au bon endroit, dans le dossier de la partie.

En pratique, ça fait gagner du temps : quand une déduction est étrange, je remonte immédiatement à l’overlay vision correspondant, sans me demander quel fichier appartient à quel run.