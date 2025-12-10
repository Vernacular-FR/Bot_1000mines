# Workflows - Bot Minesweeper

> **Portée** : Flux d'exécution arborescents et scénarios uniquement

---

## Scénario 1 - Navigation et Capture

### Flux Principal
```
Interface (main.py)
├── Affichage menu utilisateur
├── Collecte choix utilisateur → "1"
└── bot_1000mines.scenario_navigation_et_capture()
    ├── Définition paramètres (difficulté, taille)
    ├── NavigationService.start_session()
    │   ├── Initialisation navigateur
    │   ├── Navigation vers 1000mines.com
    │   └── Retour instance WebDriver
    ├── GameSetupService.setup_game_auto()
    │   ├── Validation paramètres difficulté
    │   ├── Sélection mode de jeu
    │   ├── Attente chargement grille
    │   └── Calcul coordonnées zone
    ├── ZoneCaptureService.capture_centered_zone()
    │   ├── Calcul zone centrée
    │   ├── Capture screenshot zone
    │   ├── Génération overlay grille
    │   └── Sauvegarde fichiers
    └── NavigationService.end_session()
        ├── Fermeture navigateur
        └── Nettoyage ressources
```

---

## Scénario 2 - Analyse Locale

### Flux Principal
```
Interface (main.py)
├── Affichage menu utilisateur
├── Collecte choix utilisateur → "2"
└── bot_1000mines.scenario_analyse_locale()
    ├── Recherche fichiers screenshots
    ├── Pour chaque screenshot trouvé:
    │   ├── OptimizedAnalysisService.analyze_screenshot()
    │   │   ├── Chargement image
    │   │   ├── Reconnaissance template matching
    │   │   ├── Construction grille
    │   │   ├── Mise à jour base de données
    │   │   └── Génération overlay analyse
    │   ├── Sauvegarde rapport JSON
    │   └── Génération overlay reconnaissance
    ├── Consolidation résultats batch
    └── Sauvegarde base de données globale
```

---

## Scénario 3 - Test Patterns

### Flux Principal
```
Interface (main.py)
├── Affichage menu utilisateur
├── Collecte choix utilisateur → "3"
└── bot_1000mines.scenario_test_patterns()
    ├── Initialisation séquence tests
    ├── Pour chaque pattern de test:
    │   ├── TestPatternsService.execute_pattern()
    │   │   ├── Configuration pattern
    │   │   ├── Exécution actions
    │   │   ├── Validation résultats
    │   │   └── Collecte métriques
    │   └── Logging résultats pattern
    ├── Consolidation métriques globales
    └── Génération rapport tests
```

---

## Scénario 4 - Capture Interface Optimisée

### Flux Principal
```
Interface (main.py)
├── Affichage menu utilisateur
├── Collecte choix utilisateur → "4"
└── bot_1000mines.scenario_capture_zone_interface()
    ├── NavigationService.start_session()
    │   ├── Initialisation navigateur
    │   ├── Navigation vers jeu
    │   └── Configuration session
    ├── InterfaceDetector.detect_interface_positions()
    │   ├── Analyse éléments interface
    │   ├── Extraction positions UI
    │   ├── Masquage zones interface
    │   └── Sauvegarde configuration
    ├── ZoneCaptureService.capture_game_zone_inside_interface()
    │   ├── Application masquage interface
    │   ├── Capture zone optimisée
    │   ├── Génération overlays
    │   └── Validation qualité
    └── NavigationService.end_session()
        └── Nettoyage ressources
```

---

## Scénario 5 - Jeu Complet Automatisé

### Flux Principal
```
Interface (main.py)
├── Affichage menu utilisateur
├── Collecte choix utilisateur → "5"
└── bot_1000mines.run_complete_game()
    ├── GameLoopService.initialisation
    │   ├── Configuration session jeu
    │   ├── Initialisation services
    │   └── Préparation environnement
    ├── Boucle principale (itération 1 à N):
    │   ├── GameLoopService.execute_single_pass()
    │   │   ├── Capture zone jeu
    │   │   ├── Analyse grille
    │   │   ├── Résolution logique
    │   │   ├── Exécution actions
    │   │   └── Vérification état fin
    │   ├── Logging itération
    │   └── Pause inter-itérations
    ├── Détection fin de partie
    └── GameLoopService.finalisation
        ├── Consolidation statistiques
        ├── Génération rapports
        └── Nettoyage environnement
```

---

## Gestion d'Erreurs

### Flux d'Erreur Standard
```
Opération normale
├── Tentative exécution
├── Exception détectée
│   ├── Capture contexte erreur
│   ├── Logging détaillé
│   └── Nettoyage partiel
├── Retour résultat d'erreur
└── Continuation workflow (si applicable)
```

### Gestion États Terminaux
```
Détection état terminal (WON/LOST/TIMEOUT/ERROR)
├── Arrêt boucle principale
├── Collecte statistiques finales
├── Génération rapport final
└── Nettoyage ressources
```

---

## Patterns de Flux

### Pattern Séquencement
```
Étape N
├── Validation pré-conditions
├── Exécution opération principale
├── Validation post-conditions
├── Logging succès
└── Passage étape N+1
```

### Pattern Retry
```
Opération risquée
├── Tentative 1
├── Échec détecté
│   ├── Pause courte
│   ├── Nettoyage état
│   └── Tentative 2
├── Succès ou abandon
└── Continuation normale
```

### Pattern Validation
```
Données entrantes
├── Contrôle format
├── Contrôle cohérence
├── Contrôle intégrité
├── Acceptation ou rejet
└── Logging décision
```
