# Workflow de Modularisation de Méthodes

## Objectif

Découper les méthodes d’un fichier (ou d’un lot de fichiers) pour obtenir des blocs modulaires, lisibles et maintenables, en limitant les classes qui ne servent que d’interface et en privilégiant des composants directement appelables depuis l’extérieur.

---

## Principes Directeurs

1. **Une méthode = une responsabilité** : chaque bloc doit avoir un objectif clair.
2. **Helpers privés ciblés** : n’en créer que si la logique est réutilisée dans ≥2 endroits ou si elle modélise un comportement, ou sous-comportement, autonome clairement distinct (les logs/contrôles doivent systématiquement être extraits et regroupés dans une section dédiée en fin de classe).
3. **Classes exposées** : viser des classes directement consommables par les services ; éviter les façades inutiles.
4. **Façade minimale** : conserver la compatibilité si nécessaire, mais migrer les appelants vers les nouvelles classes dès que possible.
5. **Respect des responsabilités** : déplacer du code vers un autre module uniquement si la responsabilité y est clairement mieux portée.
6. **Documentation synchronisée** : tenir à jour les notes techniques et l’index des modules dès qu’une responsabilité change.

---

## Workflow d’Exécution

### Phase 1 – Analyse rapide
```
1. Identifier le(s) fichier(s) cible(s).
2. Lister les méthodes > 30 lignes ou multi-responsabilités.
3. Décomposer chaque méthode en blocs logiques (lecture, calcul, I/O, logs, validation, conversion…).
4. Créer une todo_list : helpers à créer, méthodes à découper, déplacements à proposer.
```

### Phase 2 – Extraction modulaire
```
1. Extraire d’abord les blocs évidents (noms de fichiers, validations, conversions, calculs répétitifs).
2. Créer un helper uniquement si au moins deux call-sites l’utiliseront ou si la logique correspond à une capacité indépendante (double-clic, conversions complexes, conversions multi-étapes, etc.).
   - Obligatoire si duplication ; sinon, inline direct pour éviter les “mini-helpers”.
   - Souhaitable si la lecture est nettement améliorée et réutilisable.
   - Logs, contrôles, conversions >1 étape : extraire en helpers dédiés ET les stocker dans une section finale clairement commentée (`# Logging & diagnostics helpers`).
   - Pour les helpers purement transitionnels (ex: conversion unique, wrapper de trois lignes), inlinez si leur nom n’apporte pas de valeur.
   - Regrouper les helpers par “zones” commentées :
       * `# Game setup helpers` (sélection de mode, initialisation)
       * `# Navigation helpers` (drag, conversion coordonnées)
       * `# Logging & diagnostics helpers`
   - Position : en bas de fichier ou immédiatement après la classe concernée, avec un commentaire de séparation.
3. Réévaluer les classes existantes : fusionner/renommer si elles ne servent que d’interface afin de permettre aux consommateurs d’appeler directement les contrôleurs ou services concrets.
4. Pour une normalisation plus large, réordonner les sections (imports, classes, helpers) si nécessaire.
5. Valider tout déplacement inter-fichiers/classes avant application en confirmant que les nouvelles classes sont auto-suffisantes.
6. Tenir un journal « Avant / Après » pour expliciter les changements.
```

### Phase 3 – Vérifications
```
1. Prévisualiser les modifications (diff) et valider avant application définitive.
2. Vérifier que l’API publique reste inchangée (ou documenter toute rupture nécessaire) en identifiant clairement les points d’entrée désormais directs.
3. Mettre à jour l’index des modules si la responsabilité évolue.
4. Confirmer qu’aucun helper « one-liner » ou purement décoratif n’a été introduit, que les helpers de logs/contrôles/conversions multi-étapes sont bien regroupés dans leur section dédiée et que les services pointent vers les classes concrètes.
5. Vérifier la structure en sections commentées (ex: `# Helpers NavigationController`, `# Logging & diagnostics helpers`) pour refléter clairement les responsabilités.
5. S’assurer que les méthodes principales invoquent correctement les helpers extraits.
6. Préparer/planifier les tests à exécuter après validation.
```

### Phase 4 – Documentation
```
1. Notes techniques : journaliser
   - Modules impactés
   - Helpers / classes ajoutés
   - Responsabilités transférées
2. Index des modules : refléter les responsabilités actuelles.
3. Ajouter les prochaines étapes si d’autres modules doivent suivre.
```

---

## Contrôles Qualité
- [ ] Méthodes > 30 lignes analysées et découpées si nécessaire.
- [ ] Aucun code dupliqué entre modules.
- [ ] Helpers regroupés par rôle avec un commentaire clair; aucun helper décoratif, logs/diagnostics positionnés dans la section dédiée.
- [ ] Logs/messages d’erreur conservés ou centralisés.
- [ ] Documentation de référence mise à jour (index, notes techniques, autres guides pertinents).

---

## Anti-Patterns à éviter
- **Helper fourre-tout** : pas de « mini God-object ».
- **Façade décorative** : classe qui ne fait que relayer vers un autre composant sans logique propre.
- **Extraction sans usage multiple** (sauf lisibilité critique clairement justifiée).
- **Refactorings cachés** : toujours documenter les mouvements inter-modules.
- **Suppression d’API publique** : seulement avec plan validé et communication claire.

---

## Métriques de succès
- Taille moyenne des méthodes < 25 lignes (hors helpers).
- Zéro duplication d’algorithmes entre modules voisins.
- Chaque méthode peut être décrite en une phrase (« Cette méthode fait X en déléguant à Y »).
- Les helpers existants sont soit réutilisés dans plusieurs call-sites, soit identifiés comme fonctionnalités autonomes, et les helpers de logs/contrôles sont regroupés en fin de classe.
- Les classes exposées sont directement consommables par au moins un service sans passer par une façade supplémentaire.
- Le journal de maintenance décrit clairement les modifications et les plans futurs.

---

## Convention de nommage des helpers

- Préfixer systématiquement par `_` pour signaler la portée privée.
- Utiliser le format `_verbe_sujet` (ex: `_log_move_view`, `_resolve_anchor_position`).
- Pour les helpers de logging/diagnostic, conserver un préfixe `_log_` ou `_describe_` explicite et les placer sous un commentaire `# Logging & diagnostics helpers`.

---

## Checklist express
1. **Lire le fichier** → repérer les méthodes cibles.
2. **Lister les blocs logiques** → préparer la todo_list.
3. **Créer les helpers/classes** → appliquer les refactorings.
4. **Afficher les diff** → validation par la personne responsable.
5. **Mettre à jour les docs** → notes techniques et index concernés.

Ce workflow est rejouable sur n’importe quel module pour garantir une modularité progressive, quel que soit l’environnement ou l’outillage utilisé.
