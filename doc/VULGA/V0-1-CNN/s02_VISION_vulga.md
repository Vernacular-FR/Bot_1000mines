# Journal vision — V0-1 (pixel sampling, templates, puis CNN)

Ce journal couvre la période du **28 novembre 2025** au **9 décembre 2025**.
Pendant cette phase, la vision n’est pas encore une “brique stable” : c’est un terrain d’essais où j’alterne entre intuition et réalité du canvas.

---

## 28 novembre 2025 — Voir un jeu canvas, sans le DOM

Je commence avec Selenium et une idée simple : “je capture l’écran, puis j’analyse”.
Mais très vite, je me rends compte que la vision est déjà contrainte par la capture : si chaque screenshot prend au minimum **~1,5 s** (et parfois plus), alors *toute* stratégie qui nécessite plusieurs passes devient trop coûteuse.

J’essaie quand même, parce qu’au début on veut juste “faire marcher quelque chose”.

---

## 1er décembre 2025 — Pixel sampling : séduisant… puis frustrant

Ma première piste est le pixel sampling : repérer quelques pixels “caractéristiques” pour deviner le symbole.
Sur le papier, c’est rapide et trivial.
Dans la vraie vie, c’est une machine à faux positifs.

Deux choses me sabotent en permanence :

Les **éclats de mines**, qui perturbent l’image au moment où j’ai le plus besoin de stabilité, et les **décors aléatoires**, qui introduisent des textures et des variations non liées au symbole.

Je passe du temps à ajuster des seuils, à “compenser”, à filtrer… et je comprends que je suis en train d’écrire un modèle implicite, mais sans la robustesse d’un vrai modèle.

---

## 3–5 décembre 2025 — Template matching : mieux, mais pas fiable

Je bascule sur un template matching (même proposé au départ par ChatGPT).
C’est plus structuré, et ça donne un sentiment de progrès.
Mais je tombe sur un piège très concret : certaines versions du matching ont tendance à passer l’image en **noir et blanc**, et là je perds de l’information qui était justement discriminante. À force, je calibre des seuils “au feeling”, puis je les recale, puis je les recale encore… et je comprends que je suis en train de faire de la calibration à la main sur un système qui n’a pas la marge.

Le symptôme le plus cruel, c’est le chiffre **6** (turquoise)… et aussi les **8** (blancs) quand ils se retrouvent sur un fond gris.
Selon les couleurs et le contraste du fond, ces symboles peuvent se retrouver “trop uniformes” une fois binarisés, et donc mal classés.
Et quand des bombes/explosions viennent polluer la zone, c’est encore pire.

Et je découvre un autre défaut : mon template matching n’a pas vraiment la structure pour gérer correctement les **bombes** (motif variable, mais très distinctif). Il sait reconnaître des chiffres “propres”, mais il se casse les dents sur ce qui sort du cadre.

---

## 5–9 décembre 2025 — Le pari CNN (et sa limite)

À ce stade, je me dis : “les motifs sont déterminés, avec peu de variations… un CNN devrait plier ça.”
Je l’intègre donc dans le pipeline.

La génération du dataset est pragmatique : j’écris un programme qui découpe des screenshots en cases, puis je trie une grosse partie à la main.
Le point intéressant, c’est que le template matching précédent reconnaissait déjà une majorité de cellules : il a servi de **pré-tri**, et l’explorateur de fichiers rend très visibles les images “pas au bon endroit”.

En pratique, le CNN marche “bien” — je parle d’environ **95%** sur les cellules révélées, mais c’est franchement **au doigt mouillé** : je n’ai pas instrumenté une vraie métrique propre à ce moment-là.
Et surtout, ce n’est pas gratuit : même en découpant la vision en passes successives, ça reste lourd.

Le point ironique, c’est qu’il est très bon là où mon template matching galérait : les **bombes**. C’est exactement le genre de motif variable mais très distinctif où un CNN excelle.

Techniquement, le pipeline CNN de l’époque standardise les patches en **niveaux de gris** (24×24), ce qui explique aussi pourquoi les histoires de contraste et de couleur restent un angle mort quand les cas limites s’accumulent.

Le pire, c’est que les erreurs résiduelles retombent encore sur les mêmes coupables : les **6**, et particulièrement les **6 pollués**.

Je termine V0-1 avec une conclusion qui prépare V2 :

Ce n’est pas normal d’avoir besoin d’un CNN lourd pour reconnaître des symboles quasi déterministes.
La bonne direction, c’est un template matching plus subtil, centré, et surtout en conservant l’information de **couleur** au lieu de la détruire.

Mais je garde quand même une idée en tête pour la suite : réessayer un CNN, non pas sur une case seule, mais sur des patches plus larges (9 ou 25 cases) pour reconnaître directement des motifs de solution. Ce sera sûrement plus lourd, donc je le repousse après l’implémentation du pattern engine.