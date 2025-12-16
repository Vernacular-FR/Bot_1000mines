---
description: Spécification technique de la couche s3_storage (stockage à trois sets)
---

# S03 STORAGE – Spécification technique (didactique)

s3_storage est une **base de données passive**.

- Elle **mémorise** ce que l’on sait sur la grille.
- Elle **n’infère pas**.
- Elle **n’orchestré pas**.

Le but est d’avoir un endroit unique où l’information s’accumule et se stabilise, avec une règle claire : **qui est autorisé à écrire quoi**.

---

## 0. Les 3 sources de connaissance (et leur autorité)

Le bot n’apprend pas “en une fois”. Il apprend via 3 sources complémentaires :
- Vision  -> "ce que je vois maintenant"
- Actions -> "ce que j'ai déclenché" (donc ce qui DOIT être re-visualisé)
- Solver  -> "ce que j'en déduis / ce que je choisis de traiter"

### 0.1 Vision (s2) – vérité brute

Vision écrit :
- la **classification brute** (ex: `UNREVEALED`, `NUMBER_3`, `EMPTY`, `FLAG`, ...)
- l’état logique normalisé (ex: `OPEN_NUMBER`, `EMPTY`, `UNREVEALED`, ...)
- marque les cellules nouvellement observées comme **à traiter** par le solver (ex: `JUST_REVEALED` ou équivalent)

Vision a le droit de :
- **ajouter** au set `revealed`

Vision n’a pas le droit de :
- calculer la frontière
- décider qu’une cellule est ACTIVE/FRONTIER/SOLVED (ça relève du solver)

### 0.2 Actions / ActionPlanner (s5/s6) – vérité procédurale

Les actions ne “voient” rien, mais elles savent une chose :

> "j’ai cliqué (x,y) donc le jeu a peut-être révélé des cellules que je n’ai pas encore re-lues"

ActionPlanner a besoin d’un mécanisme persistant :
- **TO_VISUALIZE** : coordonnée potentiellement révélée, à re-cadrer / re-capturer

Ce n’est pas une classification du jeu, c’est un **besoin de vision**.

### 0.3 Solver (s4) – connaissance dérivée + mémoire de pertinence

 Le solver :
 - calcule la **topologie** (ACTIVE/FRONTIER/...) à partir de ce que Vision a écrit
 - maintient un niveau de **pertinence** (FocusLevel) pour éviter de retraiter inutilement
 - décide quand une zone frontière est "TO_PROCESS" vs "BLOCKED" (CSP) d’une itération à l’autre

---

## 1. Modèle de données (ce qui est stocké)

### 1.1 GridCell = observation + metadata

La cellule contient deux familles d’infos :

Schéma unifié (données + index + contexte de partie) :

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                           s3_storage                                │
 │                                                                     │
 │  SessionContext (s30_session_context.py)                            │
 │   ├─ game_id, iteration                                             │
 │   ├─ export_root, overlay_enabled                                   │
 │   └─ capture_saved_path, capture_bounds, capture_stride             │
 │                                                                     │
 │  StorageController                                                  │
 │   ├─ cells: dict[(x,y) -> GridCell]                                 │
 │   │        ┌────────────────────────────────────────────────────┐   │
 │   │        │ GridCell (observation + metadata)                  │   │
 │   │        │  observation (Vision)                              │   │
 │   │        │   ├─ raw_state                                     │   │
 │   │        │   ├─ logical_state                                 │   │
 │   │        │   └─ number_value                                  │   │
 │   │        │  metadata (Solver/Planner)                         │   │
 │   │        │   ├─ topological_state                             │   │
 │   │        │   ├─ focus_level                                   │   │
 │   │        │   │  ├─ ActiveRelevance (si ACTIVE)                │   │
 │   │        │   │  └─ FrontierRelevance (si FRONTIER)            │   │
 │   │        │   └─ zone_id (si FRONTIER)                         │   │
 │   │        └────────────────────────────────────────────────────┘   │
 │   │                                                                 │
 │   ├─ ZoneDB (mémoire CSP persistée)                                 │
 │   │    zone_db      : dict[ZoneId -> ZoneRecord] (dérivé/index)     │
 │   │                                                                 │
 │   └─ SetManager (index)                                             │
 │        revealed_set   : "déjà vu"                                   │
 │        active_set     : "OPEN_NUMBER avec voisins UNREVEALED"       │
 │        frontier_set   : "UNREVEALED adjacent à une ACTIVE"          │
 └─────────────────────────────────────────────────────────────────────┘
```

Note : l’implémentation actuelle expose déjà un `solver_status` et `action_status` dans `GridCell`.
Cette spec formalise ce qu’on veut exprimer (TopologicalState / FocusLevel) : la représentation concrète peut passer par `solver_status/action_status` ou par des champs dédiés.

### 1.2 SessionContext (contexte de partie)

En complément de la grille et des sets, le module `s30_session_context.py` expose un contexte global minimal pour :
- nommer/organiser les artefacts (par `game_id`, `iteration`)
- activer/désactiver l’export d’overlays
- donner aux modules l’information de capture courante (chemin + bounds + stride)

Champs principaux :

```
SessionContext
 ├─ game_id, iteration
 ├─ export_root, overlay_enabled
 └─ capture_saved_path, capture_bounds, capture_stride
```

API :
- `set_session_context(game_id, iteration, export_root, overlay_enabled)`
- `update_capture_metadata(saved_path, bounds, stride)`
- `get_session_context()`

---

## 2. TopologicalState (structurel) – ce qu’est la case

**Objectif** : exprimer la topologie locale sans mélange avec la pertinence.

TopologicalState ∈ {
TO_VISUALIZE,
JUST_VISUALIZED,
SOLVED,
ACTIVE,
FRONTIER,
NONE,
OUT_OF_SCOPE,
}

### 2.1 Invariants (logiques)

Écriture compacte :

- **ACTIVE** ⇔ `open_number` AND ∃ voisin `UNREVEALED`
- **FRONTIER** ⇔ `UNREVEALED` AND ∃ voisin **ACTIVE**
- **NONE** ⇔ `UNREVEALED` AND ∀ voisins ≠ **ACTIVE**
- **SOLVED** ⇔ `EMPTY` OR `CONFIRMED_MINE` OR (`open_number` AND ∀ voisins ≠ `UNREVEALED`)

`TO_VISUALIZE` / `JUST_VISUALIZED` sont des états de transition utiles :
- `TO_VISUALIZE` : le bot pense que des infos sont apparues, mais il ne les a pas encore re-lues.
- `JUST_VISUALIZED` : la vision vient de fournir l’observation, mais la classification topologique n’a pas encore été recalculée.

### 2.2 Transitions (topologie uniquement)

- `TO_VISUALIZE → JUST_VISUALIZED` (vision recapture)
- `JUST_VISUALIZED → ACTIVE | SOLVED` (states_analyzer)
- `ACTIVE → SOLVED` (plus de voisins `UNREVEALED`)
- `NONE → FRONTIER` (un voisin devient **ACTIVE**)
- `FRONTIER → JUST_VISUALIZED` (devient révélée par vision)

---

## 3. FocusLevel (mémoire inter-itérations) – pourquoi la case nous intéresse encore

Ici on encode la pertinence **réversible**. C’est ce qui évite de cliquer / re-CSP les mêmes zones indéfiniment.

### 3.1 ActiveRelevance

ActiveRelevance ∈ {
TO_TEST,
TESTED,
STERILE,
}

Intuition :
- `TO_TEST` : il faut la tester (clic-based) / l’exploiter dans l’itération.
- `STERILE` : on a testé, ça ne produit rien dans l’état courant (mais ça peut redevenir pertinent si voisinage change).

Transitions typiques :
- `TO_TEST → TESTED` (testée)
- `TO_TEST → STERILE` (testée sans effet)
- `STERILE → TO_TEST` (si un voisin change d'état)
- `TESTED → TO_TEST` (si un voisin change d'état)

### 3.2 FrontierRelevance

FrontierRelevance ∈ {
TO_PROCESS,
PROCESSED,
BLOCKED,
}

Portée : statut stocké **sur la cellule FRONTIER** (GridCell) comme source de vérité, mais il est **homogène par zone**. Toutes les cellules qui partagent le même `zone_id` doivent avoir le même FrontierRelevance ; le regroupement par `zone_id` sert à propager le changement à tout le groupe.

Intuition :
- `TO_PROCESS` : la zone frontière a changé, CSP doit (re)passer.
- `BLOCKED` : CSP est passé mais aucune déduction certaine n’est possible (sans guess) → on n’y revient que si la zone change.

Transitions typiques :
- `TO_PROCESS → PROCESSED` (CSP a trouvé des actions)
- `TO_PROCESS → BLOCKED` (CSP bloqué)
- `BLOCKED → TO_PROCESS` (si la zone change)

### 3.3 ZoneDB (mémoire CSP persistée / index dérivé)

Objectif : éviter de recalculer toute la segmentation CSP à chaque itération, en indexant les zones et leurs contraintes.  

Ici :
- **Source de vérité** : `GridCell.zone_id` (appartenance) et `GridCell.frontier_relevance` (statut CSP)
- **ZoneDB** : index dérivé pour regrouper par `zone_id` et propager un changement à l’ensemble des cellules de la zone

Une **zone** regroupe des cellules FRONTIER qui partagent la même signature de contraintes.

**ZoneId** : identifiant stable dérivé de la signature (ex : hash de `sorted(constraints)`), où :
- `constraints` = coordonnées des cellules `OPEN_NUMBER` adjacentes (les contraintes)

**ZoneRecord** (index dérivé minimal) :
- `zone_id: ZoneId`
- `constraints: set[Coord]`
- `cells: set[Coord]` (cellules FRONTIER de cette zone, cohérentes avec leurs `zone_id`)

Note : on n’a pas besoin de stocker `FrontierRelevance` dans ZoneDB si on le stocke déjà dans les cellules ; ZoneDB sert surtout à regrouper/projeter.

**Règles d’update (incrémental, centré Storage) :**
- À chaque `upsert()`, à partir du **delta** (cells dont l’observation/logique a changé), construire un ensemble `touched_constraints` (OPEN_NUMBER modifiés) et/ou un voisinage à rafraîchir.
- Pour les FRONTIER dans ce voisinage :
  - recalculer la signature `constraints(frontier_cell)`
  - recalculer `zone_id` et l’écrire dans la cellule (GridCell)
  - si `zone_id` change : l’**ancienne** zone et la **nouvelle** zone passent `TO_PROCESS` (propagation sur toutes leurs cellules)
- Reconstituer ou maintenir l’index `zone_db` par **group-by `zone_id`** (ou via un `cell_to_zone` dérivé si besoin de performance).
- Toute zone dont le contenu change (cells ajoutées/sorties) ou dont les contraintes changent (signature modifiée) entraîne la propagation du `FrontierRelevance = TO_PROCESS` sur **toutes les cellules** de cette zone.
- Une zone traitée par CSP sans action certaine reste `BLOCKED` (homogène sur ses cellules).
- Une zone vide est supprimée de `zone_db`.

Note : `TO_PROCESS` signifie seulement « la zone doit repasser au CSP *si/ quand* le solver décide de lancer le CSP ». Le déclenchement effectif du CSP (seuils, heuristiques, ordre des phases) est une logique **s4_solver**, pas **s3_storage**.

Note : les **components** CSP (assemblages de zones) ne sont pas persistés ; ils sont reconstruits au moment de la résolution.

---

## 4. Règles d’écriture (qui modifie quoi)

Règle centrale : **s3 stocke, s3 ne calcule pas**.

Vision    : écrit observation (raw/logical/value) + revealed_add
Solver    : écrit topological_state + focus_level + active_add/remove + frontier_add/remove
Planner   : écrit TO_VISUALIZE (besoin de re-capture), et s’en sert pour recadrer la vision

Table simplifiée :
┌──────────────┬───────────────────────────┬─────────────────────────────┐
│ Source       │ Peut écrire               │ Ne doit pas écrire          │
├──────────────┼───────────────────────────┼─────────────────────────────┤
│ Vision (s2)  │ cells(obs), revealed+,    │ frontier_set (calcul),      │
│              │                           │ focus_level/topologie       │
├──────────────┼───────────────────────────┼─────────────────────────────┤
│ Solver (s4)  │ active+/-, frontier+/-    │ revealed_set                │
│              │ topologie, focus_level,   │ (sauf via vision)           │
│              │ ZoneDB (zones+relevance)  │                             │
├──────────────┼───────────────────────────┼─────────────────────────────┤
│ Planner (s5) │ TO_VISUALIZE              │ classification raw/logical  │
└──────────────┴───────────────────────────┴─────────────────────────────┘

---

## 5. API & invariants (implémentation actuelle)

### 5.1 StorageUpsert

Le mécanisme d’écriture doit rester batché : un seul `upsert()` par “événement”.

```python
@dataclass
class StorageUpsert:
    cells: dict[Coord, GridCell]
    revealed_add: set[Coord]
    active_add: set[Coord]
    active_remove: set[Coord]
    frontier_add: set[Coord]
    frontier_remove: set[Coord]
    zone_upsert: dict[str, dict]
    zone_remove: set[str]
    cell_to_zone_upsert: dict[Coord, str]
    cell_to_zone_remove: set[Coord]
```

### 5.2 Invariants de sets (enforce dans SetManager)

Dans l’implémentation, on applique déjà :
- `active_set ⊆ revealed_set`
- `frontier_set ∩ revealed_set = ∅`
- `frontier_set ⊆ neighbors(active_set)`

Utilité & fonctionnement :
- `frontier_set` est un **index dérivé** (un cache) qui évite de rescanner toute la grille pour retrouver les cellules FRONTIER.
- Définition fonctionnelle : cellule **fermée** qui est voisine d’au moins une cellule **ACTIVE** (donc une cellule fermée qui porte des contraintes potentielles).
- Écriture : maintenu de façon incrémentale par le solver (s4) via `frontier_add/frontier_remove` dans `StorageUpsert`.
- Usage :
  - base de la vue solver (frontier view) pour la segmentation / ZoneDB
  - permet de limiter le travail CSP aux cellules pertinentes

Utilité & fonctionnement (active) :
- `active_set` est un **index dérivé** (un cache) pour accéder rapidement aux cases `ACTIVE`.
- Définition fonctionnelle : cellule `OPEN_NUMBER` qui a au moins un voisin `UNREVEALED`.
- Écriture : maintenu de façon incrémentale par le solver (s4) via `active_add/active_remove` dans `StorageUpsert`.
- Usage :
  - base de la boucle click-based (“dumb solver”)
  - le solver filtre ensuite via `GridCell.focus_level` (`ActiveRelevance=TO_TEST/TESTED/STERILE`) sans rescanner toute la grille

---

## 6. Pièges à éviter

- Vision qui calcule la frontière (mauvaise séparation).
- Un état “fourre-tout” : topologie et focus_level doivent rester orthogonaux.
- Confondre mémoire inter-itérations (FocusLevel) et état interne d’un algo (to_process/processed/blocked d’un seul pass).

---

## 7. Résumé opérationnel

s2 Vision        : observe -> écrit cells + revealed
s4 Solver        : calcule topologie + focus_level -> écrit active/frontier
s5 ActionPlanner : exécute -> marque TO_VISUALIZE -> recadre vision
s3 Storage       : conserve tout ça, sans logique