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

## 16 décembre 2025 — Re-capture cadrée (TO_VISUALIZE)

Je clarifie l’interface avec le reste du pipeline : la vision ne “devine” pas quand recapturer.
Quand le solver annonce des cellules `SAFE`, il les marque `TO_VISUALIZE` pour forcer une relecture, et la boucle recapture une zone pertinente avant de relancer une analyse.
La vision reste volontairement déterministe : elle observe une image, elle produit une classification, et elle laisse la topologie/les décisions au solver.

## 17 décembre 2025 — Le bug fantôme du `known_set`

Problème fondamental : j’avais introduit un mécanisme simple (et indispensable) : **dire à la vision “ne re-scanne pas les cellules déjà connues”**.
En théorie, c’est juste un `known_set` (ensemble de coordonnées) passé au template matcher pour ignorer ces cases.

En pratique, ça ne marchait pas — ou pire, ça “marchait” mais de travers — parce qu’il y avait **deux pièges simultanés** :

- **Le `known_set` était toujours vide**
  La vision récupérait son `known_set` via une nouvelle instance de `StorageController()` à chaque analyse. Donc même si le storage du jeu (celui utilisé par le solver) s’enrichissait, la vision consultait un autre storage, vierge.

- **Confusion de repères (coords)**
  La capture est recadrée (image dont le coin haut-gauche est `(0,0)` en pixels), mais le `known_set` est en coordonnées absolues de grille.
  Sans conversion explicite, on filtre “au mauvais endroit”, ce qui peut donner l’impression que la vision perd des cases, que le solver n’a plus d’actions, ou que l’overlay est décalé.

Pourquoi c’était si difficile à déceler :

- **Symptômes trompeurs** : “le solver ne trouve plus d’actions” pouvait venir du filtre, du fait que la partie n’avait pas démarré (aucun clic initial), ou d’un simple problème d’overlay.
- **Le bug était silencieux** : un `known_set` vide ne déclenche aucune exception et ressemble à un comportement normal (“la vision analyse tout”).
- **Deux bugs qui se masquent** : le partage du storage (vide) et le repère de coordonnées (décalé) donnaient des résultats contradictoires selon les runs.

Ce qu’on a corrigé :

- **Storage partagé** : `VisionAnalysisService` reçoit l’instance de storage du game loop (donc le `known_set` est réel).
- **Conversion de coordonnées** : séparation nette entre coordonnées pixels (dans l’image recadrée) et coordonnées grille absolues (pour comparer au `known_set`).
- **Statut “observé” cohérent** : vision marque toute case observée (y compris flags/exploded) en `JUST_VISUALIZED`, et le storage n’ajoute au `known_set` que ces cases-là.