# Journal capture — V2 (pixels rapides, image fiable)

Ce journal couvre la **V2 à partir du 10 décembre 2025**.
L’objectif est clair : arrêter de payer le coût du screenshot Selenium et récupérer l’information au plus près de la source, c’est-à-dire le canvas.

---

## 10 décembre 2025 — Le pivot : capturer le canvas, pas l’écran

La capture devient une brique technique à part entière.
Je ne veux plus “une image jolie”, je veux une image exploitable : alignée sur la grille, stable, et reproductible.

Je mets donc en place la capture canvas et un mécanisme de composition, parce qu’en pratique le jeu n’est pas toujours dans une seule surface simple.
Le cœur de la V2, c’est ça : reconstruire une vue cohérente, même si elle est composée de plusieurs tiles.

Au passage, je me heurte à un détail qui m’avait bloqué mentalement en V0-1 : les canvases ne sont pas “interactifs” à la main, et leur taille (par exemple **512×512**) n’est pas un multiple propre de la grille. En V2, je dois donc rajouter un système de conversion en plus, pour passer d’un repère canvas à un repère cellule sans tricher.

---

## 12 décembre 2025 — Alignement pixel‑parfait, ou rien

Je découvre que la capture n’est pas un simple “dump” : l’alignement fait la différence entre une vision fiable et une vision qui déraille.
Le CanvasCompositor devient donc une pièce centrale : il recolle, aligne, et recalcul les bornes de grille.

Ce jour-là, je passe d’une capture qui “marche souvent” à une capture qui devient une base de travail sérieuse.

---

## 15 décembre 2025 — Capture live, rangée par partie

Je rends la capture plus simple à exploiter : chaque run crée une arborescence de partie (un `game_id`) et la capture y dépose ses fichiers.
Concrètement : les tuiles sont dans `s1_raw_canvases/`, puis l’image recomposée dans `s1_canvas/`.

C’est une amélioration discrète mais très utile : je peux comparer deux parties, retrouver une capture précise, et corréler immédiatement ce que la vision et le solver vont produire ensuite.

---

## 16 décembre 2025 — export_root unique et re-capture pilotée

Je verrouille le principe : la capture reçoit une seule racine de partie (`export_root`) et dépose ses artefacts uniquement dans `s1_raw_canvases/` et `s1_canvas/`.
Quand le solver marque des cellules `TO_VISUALIZE`, la capture devient le point de passage obligé pour régénérer une image de grille cohérente avant la relecture vision.