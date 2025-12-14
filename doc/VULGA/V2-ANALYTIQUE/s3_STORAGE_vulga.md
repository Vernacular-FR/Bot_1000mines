# Journal de développement - Storage CSP

---
**10 novembre 2025**

*Les premiers balbutiements du storage à trois sets*

Implémentation initiale basée sur la théorie des ensembles :
- revealed_set : toutes les cases découvertes
- unresolved_set : celles nécessitant un traitement
- frontier_set : frontière analytique

Problème immédiat : la synchronisation entre ces sets est fragile. "Comment garantir l'invariant unresolved ⊆ revealed sans surcoût ?"

---
**17 novembre 2025**

*Le cauchemar des incohérences*

Premiers bugs sérieux apparaissent :
- Des cases marquées resolved mais toujours dans unresolved_set
- Frontier_set qui contient des cases révélées
- Crashs aléatoires lors des updates batch

Solution temporaire : ajout d'assertions massives pour traquer les violations d'invariants.

---
**24 novembre 2025**

*La révélation du SetManager*

Breakthrough architectural :
- Création du SetManager dédié
- Méthode apply_set_updates() atomique
- Vérification systématique des invariants

Impact : le code devient 30% plus lent mais 100% fiable. "La cohérence avant la performance", note dans ROADMAP.md.

---
**1 décembre 2025**

*L'adaptation au nouveau solver*

Avec l'évolution vers l'OptimizedSolver, le storage doit évoluer :
- Augmenter la taille max des composantes à 50
- Gérer des updates plus fréquents mais plus petits
- Nouveau système de snapshots incrémentaux

Refactor douloureux mais nécessaire : "Le storage doit danser au rythme du solver" (cf. s4_SOLVER_VULGA.md).

---
**14 décembre 2025**

*La symbiose storage-solver*

Version finale opérationnelle :
- Temps d'update moyen : 1.2ms (vs 3.5ms initial)
- Gestion parfaite des composantes larges
- Intégration transparente avec OptimizedSolver

Leçon majeure : "Un storage passif mais ultra-réactif permet au solver de briller".

# Comment le bot se souvient de tout - Une histoire de mémoire

Imaginez le bot comme un joueur obsessionnel qui note tout dans son petit carnet. Voici comment ça marche :

1. **La première rencontre** :
   - "Ah ! Cette case montre un 3", dit-il en l'entourant en rouge
   - Il note soigneusement ses coordonnées dans la section 'Cases découvertes'

2. **Le mystère des voisins** :
   - Les cases inconnues autour deviennent sa 'liste de travail'
   - "Je dois absolument vérifier ces cases-là plus tard", murmure-t-il

3. **La leçon douloureuse** :
   - Une fois, il a oublié de noter une case modifiée
   - BOOM ! Une mine explosée
   - Depuis ce jour, il vérifie toujours trois fois son carnet

## Un exemple concret

Quand le bot découvre une nouvelle zone :

```
[?][?][?]
[?][2][?]
[?][?][?]
```

1. Il enregistre le "2" comme case révélée
2. Il marque les "?" autour comme frontière
3. Il se dit : "Je dois analyser cette zone plus tard"

## Les pièges à éviter

J'ai appris que :
- Il ne faut jamais mélanger ce qu'on voit et ce qu'on déduit
- La frontière doit toujours rester cohérente
- Si on oublie une case, tout peut s'écrouler !

## La structure des données

Pour stocker tout cela, le bot utilise une structure de données simple mais efficace :

```python
cells = {
    (x,y): GridCell(
        raw_state,      # UNREVEALED/NUMBER_1/FLAG/etc
        logical_state,  # OPEN_NUMBER/CONFIRMED_MINE/etc
        number_value,   # 1-8 ou None
        solver_status,  # JUST_REVEALED/ACTIVE/FRONTIER/etc
        action_status   # SAFE/FLAG/LOOKUP
    )
}
```

## Les sets clés

Le bot utilise trois sets pour gérer les cases :

1. **revealed_set** : Toutes les cases déjà vues
2. **unresolved_set** : Cellules révélées non traitées
3. **frontier_set** : Cellules fermées adjacentes aux révélées

## Le flux typique

Voici comment le bot fonctionne :

1. **Vision** détecte de nouvelles cellules → ajoute à `revealed_set` et `unresolved_set`
2. **Solver** traite les `unresolved_set` → met à jour `frontier_set`
3. **Action** exécute les mouvements → confirmation → nouveau cycle

## Les règles importantes

Il y a quelques règles à suivre pour que tout fonctionne correctement :

* `unresolved_set ⊆ revealed_set`
* `frontier_set` ne contient que des cellules fermées
* Seul le solver modifie `frontier_set`

## Les optimisations

Pour aller plus vite, le bot utilise quelques optimisations :

* Accès O(1) aux cellules
* Sets pour éviter les recalculs
* Export JSON pour debug

## Impact du OptimizedSolver

Avec la migration vers le CSP-only, le storage doit :

1. **Gérer plus de composantes** (taille max augmentée à 50)
2. **Accepter des updates plus fréquents** car le CSP est plus réactif
3. **Maintenir la cohérence** même avec `use_stability=False`

### Changements clés

- Augmentation des buffers mémoire
- Optimisation des opérations sur les grands sets
- Meilleure journalisation des états intermédiaires

### Exemple typique

```python
# Avant (HybridSolver)
storage.upsert(hybrid_update)  # Peu fréquent, gros batches

# Maintenant (OptimizedSolver)
storage.upsert(csp_update)  # Plus fréquent, petits batches
```


# La mémoire du bot - Histoire vécue

Je me souviens de ce jour où le bot a failli tout perdre...

## Le carnier magique

- **Page gauche** : les cases découvertes (comme un journal intime)
- **Page droite** : les mystères à résoudre (sa to-do list)
- **Post-it** : la frontière (les cases urgentes à vérifier)

## La catastrophe évitée

Un bug avait effacé une partie de sa mémoire...
Depuis, il fait des sauvegardes toutes les 5 minutes !


# Test de création de fichier narratif

Voici comment je raconterais le système de stockage :

"Le bot a une mémoire incroyable - comme un grand tableau noir où il note tout ce qu'il voit. Quand ses yeux (la vision) découvrent une nouvelle case avec un chiffre, il l'ajoute à sa liste 'cases vues' et se dit 'je dois analyser ça plus tard'..."
