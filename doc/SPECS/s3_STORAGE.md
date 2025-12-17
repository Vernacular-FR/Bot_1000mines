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
- **ne touche pas** au set `known_set` : l’inclusion se fera automatiquement via `apply_upsert` en passant `topological_state=JUST_VISUALIZED`.

Vision n’a pas le droit de :
- calculer la frontière
- décider qu’une cellule est ACTIVE/FRONTIER/SOLVED (ça relève du solver)

### 0.2 Actions / ActionPlanner (s5/s6) – vérité procédurale

Les actions ne “voient” rien, mais elles savent une chose :

> "j’ai cliqué (x,y) donc le jeu a peut-être révélé des cellules que je n’ai pas encore re-lues"

ActionPlanner a besoin d’un mécanisme persistant :
- **TO_VISUALIZE** : coordonnée potentiellement révélée, à re-cadrer / re-capturer

Ce n’est pas une classification du jeu, c’est un **besoin de vision**.

Important : dans la stratégie actuelle, le **solver** est celui qui écrit `TO_VISUALIZE` quand il décide qu’une cellule est **SAFE** (donc cliquable) et qu’elle doit impérativement être re-lue à l’itération suivante.

### 0.3 Solver (s4) – connaissance dérivée + mémoire de pertinence

 Le solver :
 - calcule la **topologie** (ACTIVE/FRONTIER/...) à partir de ce que Vision a écrit
 - maintient un niveau de **pertinence** (FocusLevel) pour éviter de retraiter inutilement
 - décide quand une zone frontière repasse à `TO_PROCESS` (ré-entrée CSP) d’une itération à l’autre

---

## 1. Modèle de données (ce qui est stocké) – invariants à appliquer dans apply_upsert (pare-feu)

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
 │   │        │   ├─ focus_level (cohérence stricte)               │   │
 │   │        │   │  ├─ ActiveRelevance (uniquement si ACTIVE)     │   │
 │   │        │   │  └─ FrontierRelevance (uniquement si FRONTIER) │   │
 │   │        │   └─ zone_id (si FRONTIER)                         │   │
 │   │        └────────────────────────────────────────────────────┘   │
 │   │                                                                 │
 │   ├─ ZoneDB (mémoire CSP persistée)                                 │
 │   │    zone_db      : dict[ZoneId -> ZoneRecord] (dérivé/index)     │
 │   │                                                                 │
 │   └─ SetManager (index)                                             │
 │        known_set : "déjà vu"                         │
 │        active_set     : "ACTIVE avec voisins UNREVEALED"            │
 │        frontier_set   : "UNREVEALED adjacent à une ACTIVE"          │
 │        to_visualize   : "SAFE cliquées à re-capturer"               │
 └─────────────────────────────────────────────────────────────────────┘
```

Note : l’implémentation actuelle expose déjà un `solver_status` et `action_status` dans `GridCell`.
Cette spec formalise ce qu’on veut exprimer (TopologicalState / FocusLevel) : la représentation concrète peut passer par `solver_status/action_status` ou par des champs dédiés.

### 1.1.1 Invariant de cohérence (enforcé par storage)
- `solver_status == ACTIVE`  ⇒ `focus_level_active ∈ {TO_REDUCE, REDUCED}` et `focus_level_frontier is None`
- `solver_status == FRONTIER` ⇒ `focus_level_frontier ∈ {TO_PROCESS, PROCESSED}` et `focus_level_active is None`
- Tous les autres états (`SOLVED`, `TO_VISUALIZE`, `JUST_VISUALIZED`, `NONE`, `OUT_OF_SCOPE`) ⇒ `focus_level_active is None` et `focus_level_frontier is None`
- **TO_VISUALIZE** peut être exclu de `active_set` (optionnel) pour éviter des faux positifs. Dans tous les cas, il reste hors `known_set` et sera reclassé par vision dès recapture.
- Toute violation lève une exception lors du `apply_upsert`.

### 1.1.2 Invariant logique/valeur
- `logical_state == OPEN_NUMBER` ⇒ `number_value` obligatoire (1..8)
- `logical_state != OPEN_NUMBER` ⇒ `number_value` doit être `None`
Violation ⇒ exception lors du `apply_upsert`.

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

`TO_VISUALIZE` / `JUST_VISUALIZED` sont des états de transition topologiques :
- `TO_VISUALIZE` : la case a été cliquée (SAFE par le solver/planner) et doit être re-capturée. L’état logique/réel reste `UNREVEALED` tant que la vision n’a pas relu.
- `JUST_VISUALIZED` : la vision vient de fournir l’observation (logical_state + raw_state) ; la topologie doit encore être recalculée par le state analyzer (ACTIVE / SOLVED / FRONTIER).

### 2.2 Transitions (topologie uniquement)

- `TO_VISUALIZE → JUST_VISUALIZED` (vision recapture avec new logical_state/raw_state)
- `JUST_VISUALIZED → ACTIVE | SOLVED` (states_analyzer reclasse selon voisinage)
- `ACTIVE → SOLVED` (plus de voisins `UNREVEALED`)
- `NONE → FRONTIER` (un voisin devient **ACTIVE**)
- `FRONTIER → JUST_VISUALIZED` (devient révélée par vision)

### 2.3 Mapping états réels / logiques / topo (règles d’écriture)
- **Vision** écrit `raw_state` + `logical_state` et pose `topological_state = JUST_VISUALIZED` pour toutes les nouvelles observations (FLAGS compris), en ignorant le revealed/known_set déjà acquis.
- **Solver (actions SAFE)** : ne touche pas au `logical_state`, marque `topological_state = TO_VISUALIZE` (et ajoute la coordonnée dans `to_visualize`). Pas de focus_level actif ici.
- **Solver (actions FLAG)** : `logical_state = CONFIRMED_MINE`, `topological_state = SOLVED`.
- **State analyzer** (reclassement) : convertit `JUST_VISUALIZED` en `ACTIVE`/`SOLVED`/`FRONTIER` via `s40_states_analyzer/states_recluster.py`, puis déclenche la première repromotion des focus levels.

### 2.4 Triggers de promotion (voisinage)
- Déclencheur : une case change de topologie vers **ACTIVE**, **SOLVED** ou **TO_VISUALIZE**.
- Deux points de repromotion dans le pipeline :
  1. **Post-vision** : après le reclustering des états (`s40_states_analyzer/states_recluster.py`)
  2. **Post-solver** : après les actions solver (safe/flag) dans `s49_optimized_solver.py`
- Effets :
  - voisines **ACTIVE** : `focus_level_active REDUCED → TO_REDUCE`
  - voisines **FRONTIER** (zone entière) : `focus_level_frontier PROCESSED → TO_PROCESS`

### 2.5 Sets exposés
- `revealed_set` (a.k.a. known_set) : utilisé par Vision pour éviter de rescanner les cases déjà connues.
- `active_set` : `ACTIVE` **∪ `TO_VISUALIZE`** (les cases à re-capturer sont considérées comme actives côté solver).
- `frontier_set` : UNREVEALED adjacentes aux ACTIVE (selon la topologie recalculée).

---

## 3. FocusLevel (mémoire inter-itérations) – pourquoi la case nous intéresse encore

Ici on encode la pertinence **réversible**. C’est ce qui évite de cliquer / re-CSP les mêmes zones indéfiniment.

### 3.1 ActiveRelevance

ActiveRelevance ∈ {
TO_REDUCE,
REDUCED,
}

Intuition :
- `TO_REDUCE` : la cellule ACTIVE est éligible à la réduction de frontière déterministe (passes “simples”, pré-CSP).
- `REDUCED` : la cellule a été exploitée via la réduction, mais aucune action supplémentaire n’est apparue dans l’état courant (elle peut redevenir pertinente si le voisinage change).

Transitions typiques :
- `TO_REDUCE → REDUCED` (aucune nouvelle action après réduction, et aucun changement de voisinage observé)
- `REDUCED → TO_REDUCE` (si un voisin change d'état)

Source d’écriture (déterministe) :
- le solver remet une cellule `ACTIVE` à `TO_REDUCE` dès qu’il détecte un changement topologique ou un changement dans son voisinage local.

### 3.2 FrontierRelevance

FrontierRelevance ∈ {
TO_PROCESS,
PROCESSED,
}

Portée : statut stocké **sur la cellule FRONTIER** (GridCell) comme source de vérité, mais il est **homogène par zone**. Toutes les cellules qui partagent le même `zone_id` doivent avoir le même FrontierRelevance ; le regroupement par `zone_id` sert à propager le changement à tout le groupe.

Intuition :
- `TO_PROCESS` : la zone frontière a changé, CSP doit (re)passer.
- `PROCESSED` : la zone a déjà été traitée par le CSP. Si elle reste `PROCESSED`, on considère implicitement qu’elle est “bloquée” tant qu’aucune information nouvelle n’arrive.

Transitions typiques :
- `TO_PROCESS → PROCESSED` (CSP exécuté sur la zone)
- `PROCESSED → TO_PROCESS` (si la zone change)

Source d’écriture (déterministe) :
- le solver remet une zone `FRONTIER` à `TO_PROCESS` dès qu’il détecte que la signature de la zone change (contraintes) ou que le voisinage/les contraintes sont impactés.

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
- Une zone traitée par CSP est marquée `PROCESSED` (homogène sur ses cellules). Tant qu’elle reste `PROCESSED`, on considère implicitement qu’elle n’apporte rien de déterministe (sans guess) dans l’état courant.
- Une zone vide est supprimée de `zone_db`.

Note : `TO_PROCESS` signifie seulement « la zone doit repasser au CSP *si/ quand* le solver décide de lancer le CSP ». Le déclenchement effectif du CSP (seuils, heuristiques, ordre des phases) est une logique **s4_solver**, pas **s3_storage**.

Note : les **components** CSP (assemblages de zones) ne sont pas persistés ; ils sont reconstruits au moment de la résolution.

---

## 4. Règles d’écriture (qui modifie quoi)

Règle centrale : **s3 stocke, s3 ne calcule pas**.

Vision    : écrit observation (raw/logical/value) + revealed_add
Solver    : écrit topological_state + focus_level + active_add/remove + frontier_add/remove
Solver    : peut aussi écrire TO_VISUALIZE (besoin de re-capture) lorsqu’il publie des actions SAFE (cases amenées à changer)
Planner   : consomme TO_VISUALIZE et s’en sert pour recadrer la vision

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
│              │ TO_VISUALIZE, FLAG              │                             │
├──────────────┼───────────────────────────┼─────────────────────────────┤
│ Planner (s5) │                           │ classification raw/logical  │
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
  - base de la réduction de frontière déterministe (passes “simples”, pré-CSP)
  - le solver filtre ensuite via `GridCell.focus_level` (`ActiveRelevance=TO_REDUCE/REDUCED`) sans rescanner toute la grille

---

## 6. Pièges à éviter

- Vision qui calcule la frontière (mauvaise séparation).
- Un état “fourre-tout” : topologie et focus_level doivent rester orthogonaux.
- Confondre mémoire inter-itérations (FocusLevel) et état interne d’un algo (to_process/processed d’un seul pass).

---

## 7. Résumé opérationnel

s2 Vision        : observe -> écrit cells + revealed
s4 Solver        : calcule topologie + focus_level -> écrit active/frontier
s5 ActionPlanner : exécute -> consomme TO_VISUALIZE -> recadre vision
s3 Storage       : conserve tout ça, sans logique