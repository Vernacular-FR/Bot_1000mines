# Journal architectural — V0-1 (avant la refonte V2)

Ce journal couvre la période du **28 novembre 2025** (début du projet) au **9 décembre 2025**.
Je n’ai pas encore une architecture “en couches” : je construis le bot en même temps que je découvre les contraintes du site… et le fait que tout est un **canvas**.

---

## 28 novembre 2025 — La première contrainte : il n’y a pas de DOM

Je démarre avec l’idée naïve qu’un démineur web va me donner des éléments HTML, des classes, des attributs.
Sauf que non : la grille est dessinée dans un canvas. Donc, dès le premier jour, mon architecture se résume à une question très terre-à-terre :

Comment je construis un **repère stable** (un point d’**anchor**) pour pouvoir ensuite tout exprimer en coordonnées cohérentes ?

À ce moment-là, tout est encore “en vrac” : capture, vision, décisions, clics.
Et c’est normal : tant que je ne sais pas cliquer au bon endroit, le reste n’a aucune valeur.

---

## 30 novembre 2025 — Les premières frontières entre responsabilités

À force de corriger un bug et d’en créer deux ailleurs, je commence à séparer “ce qui voit”, “ce qui décide”, et “ce qui agit”.
Pas encore une vraie architecture officielle, mais une intuition se forme :

- la capture et l’interface doivent être fiables même si le solver est mauvais,
- la vision doit pouvoir évoluer (pixel sampling, templates, CNN…) sans casser le reste,
- et le solver doit recevoir un état propre, pas une bouillie de données.

Je réalise surtout que la performance n’est pas un détail : avec Selenium, un simple screenshot peut prendre **au moins 1,5 s**, et parfois plusieurs secondes.
Donc chaque étape “en plus” se paye cash.

---

## 2 décembre 2025 — Quand Selenium devient un handicap

La plus grosse leçon de cette phase, c’est que Selenium peut piloter un navigateur… mais pas forcément un jeu canvas de façon propre.
Les interactions déclenchent des comportements bizarres : au lieu de déplacer la vue, je finis par “déplacer du CSS”, et je me retrouve avec des décalages entre ce que je vois et ce que je clique.

À partir de là, je commence à basculer les actions vers des événements JavaScript plus directs.
C’est moins “magique”, mais beaucoup plus contrôlable.

---

## 9 décembre 2025 — Le constat : il faut une refonte

Je sors de cette première période avec une conclusion simple : je peux empiler des patches, mais je vais finir avec une machine illisible.
Et surtout, je vois enfin *où est la vraie difficulté* :

Le bot n’a pas besoin de “plus de trucs”. Il a besoin d’un pipeline clair, où chaque couche a un rôle net.

Le 10 décembre, je décide donc de repartir sur une refonte V2 : architecture en couches, capture canvas directe, vision déterministe, solver optimisé.