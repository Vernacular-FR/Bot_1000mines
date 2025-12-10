# Logique Métier - Bot Minesweeper

> **Portée** : Concepts métier, règles et invariants uniquement

---

## Concepts Métier

### Bot d'Automation
- Agent logiciel automatisant les interactions avec le jeu Minesweeper
- Exécute des workflows prédéfinis de manière séquentielle
- Responsable : navigation, configuration, capture d'écran, analyse, résolution

### Workflows
- Séquences d'opérations orchestrées avec validation à chaque étape
- Types principaux : navigation, initialisation, capture, analyse, résolution
- Exécution unidirectionnelle avec gestion des erreurs et états

### Session de Jeu
- Instance unique de jeu par exécution du bot
- Cycle : démarrage → configuration → jeu → arrêt propre
- Gestion des métadonnées : identifiant, timestamp, difficulté, statistiques

### Zone de Capture
- Zone rectangulaire sur la grille de jeu
- Exclusion des éléments d'interface utilisateur (status, contrôles)
- Base pour l'analyse automatisée de la grille

### Analyse de Grille
- Reconnaissance automatique des symboles de la grille
- Construction d'une représentation logique du jeu
- Base de données des cellules avec états et symboles

### Résolution de Puzzle
- Application d'algorithmes logiques pour résoudre le Minesweeper
- Génération d'actions sûres (clics) et drapeaux
- Validation des déductions mathématiques

### Actions de Jeu
- Exécution d'actions sur la grille : clics et drapeaux
- Coordination avec le système de coordonnées du jeu
- Validation des actions avant exécution

---

## Règles Métier

### Gestion des Sessions
- Une session = une partie complète du jeu
- Identification unique par timestamp et identifiant
- Persistence des métadonnées de session

### Validation des Configurations
- Vérification des paramètres avant utilisation
- Valeurs par défaut définies pour les paramètres manquants
- Centralisation de toute la configuration

### Capture et Analyse
- Capture centrée sur la zone de jeu uniquement
- Analyse complète de toutes les cellules visibles
- Validation de la qualité des données avant traitement

### Résolution Logique
- Application exclusive d'algorithmes mathématiques
- Priorité aux actions sûres (déductions certaines)
- Évitement des risques non calculés

### Exécution des Actions
- Validation de la faisabilité des actions
- Conversion coordonnées logiques → coordonnées écran
- Gestion des timeouts et erreurs d'exécution

---

## Invariants Métier

### Unicité de Session
- Une seule session active par exécution du bot
- Isolation complète entre différentes exécutions

### Intégrité des Données
- Toute cellule analysée doit avoir un état cohérent
- Les actions générées doivent être valides pour la grille

### Sécurité des Actions
- Jamais d'actions aléatoires ou spéculatives
- Seules les déductions mathématiques certaines sont autorisées

### Traçabilité
- Tout état du jeu doit être sauvegardé et récupérable
- Historique complet des actions et décisions

---

## États du Jeu

### États Possibles
- **PLAYING** : Partie en cours, actions possibles
- **WON** : Victoire détectée, partie terminée
- **LOST** : Défaite détectée, partie terminée
- **TIMEOUT** : Délai dépassé, arrêt de sécurité
- **ERROR** : Erreur technique, arrêt anormal
- **NO_ACTIONS** : Plus d'actions possibles, blocage logique

### Transitions d'États
- PLAYING → WON (victoire détectée)
- PLAYING → LOST (mine déclenchée)
- PLAYING → TIMEOUT (délai dépassé)
- PLAYING → ERROR (exception technique)
- PLAYING → NO_ACTIONS (aucune action sûre trouvée)
- États terminaux : WON, LOST, TIMEOUT, ERROR, NO_ACTIONS

---

## Acteurs Métier

### Utilisateur
- Lance les scénarios d'automation
- Définit les paramètres de configuration
- Consulte les résultats et statistiques

### Bot d'Automation
- Exécute les workflows selon les scénarios
- Gère les sessions et états du jeu
- Produit les rapports et métriques

### Système de Jeu
- Fournit l'interface web Minesweeper
- Répond aux actions du bot
- Fournit les états visuels de la grille

### Solveur Mathématique
- Analyse la logique du jeu
- Génère les actions sûres
- Détecte les états terminaux
