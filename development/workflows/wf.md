# Workflow de Structuration Documentation

## Objectif

Réviser, normaliser et compléter le dossier `docs/` pour qu'il soit :
- **Cohérent et exploitable par une IA**
- **Structuré selon les couches métier, applicative et technique**  
- **Synthétique et modulable pour la maintenance future**
- **Flexible et adaptatif** : préserver les fichiers existants pertinents tout en visant la structure cible

---

## Structure Cible (Flexible)

```
docs/
├── specs/                    # Documentation technique principale
│   ├── architecture_fichiers.md     # Architecture complète (fichiers, modules, flux)
│   ├── architecture_logicielle.md   # Couches, patterns, interfaces
│   ├── logique_metier.md            # Concepts, règles, invariants, acteurs
│   ├── stack_techniques.md          # Librairies, frameworks, utilitaires
│   └── workflows.md                 # Flux d'exécution et scénarios
├── thinking/                 # Réflexions et stratégies de développement
│   ├── strategie_resolution_minesweeper.md  # Stratégie du solver Minesweeper
│   └── archive/                     # Archives de réflexions et stratégies
├── meta/                     # Méta-informations et gestion
│   ├── changelog.md                 # Historique des modifications
│   └── roadmap.md                   # Journal de développement + roadmap
├── guides/                   # Guides spécialisés (si existants)
│   └── [guides_utilitaires.md]      # Guides d'usage, configuration, etc.
├── examples/                 # Exemples de code (si pertinents)
│   └── [exemples_pratiques.md]      # Cas d'usage concrets
└── README.md                # Guide utilisateur simple
```

**Principe d'adaptation :**
- Conserver les fichiers existants qui apportent une valeur réelle
- Créer les dossiers `guides/`, `examples/`, `meta/archive/` si besoin
- Viser la structure cible sans forcément supprimer tout ce qui dévie

---

## Workflow d'Exécution

### Phase 1: Analyse (5 min)
```
1. Lister tous les fichiers docs/ actuels
2. Identifier les problèmes de couche:
   - Contenus redondants ou mal placés
   - Concepts métier vs modules vs techniques
   - Flux incohérents ou dupliqués
3. Créer todo_list avec 8 tâches prioritaires
```

### Phase 2: Normalisation (15 min)
```
1. architecture_fichiers.md
   - Architecture complète: fichiers, modules, flux
   - Référence principale du projet
   
2. architecture_logicielle.md  
   - Uniquement: couches, patterns, interfaces
   - Format: arborescences YAML-like, flux explicites
   
3. logique_metier.md
   - Uniquement: concepts, règles, invariants, acteurs
   - Format: 3-5 lignes par concept, pas de code
   
4. composants_techniques.md
   - Uniquement: librairies, frameworks, utilitaires  
   - Format: carte technique avec dépendances
   
5. workflows.md
   - Uniquement: flux d'exécution arborescents
   - Format: main → services → lib avec gestion erreurs
```

### Phase 3: Nettoyage et Adaptation (5 min)
```
1. Analyser les fichiers existants :
   - Identifier les fichiers pertinents à conserver
   - Repérer les fichiers obsolètes ou redondants
   - Évaluer l'utilité de chaque fichier par rapport à la structure cible

2. Adapter plutôt que supprimer systématiquement :
   - Renommer/réorganiser les fichiers existants pertinents
   - Fusionner le contenu de fichiers redondants
   - Conserver les fichiers spécialisés qui apportent de la valeur
   - Déplacer le contenu mal placé vers la bonne couche

3. Gérer les cas particuliers :
   - Guides volumineux → README.md ou docs/guides/
   - Configuration → lib/config.py ou docs/meta/config.md
   - Code examples → docs/examples/ ou supprimer si obsolètes
   - Fichiers historiques → docs/meta/archive/
```

### Phase 4: Finalisation (5 min)
```
1. Mettre à jour changelog.md (section Unreleased)
2. Vérifier cohérence terminologique
3. Contrôle qualité: zéro doublons, une couche par concept
4. Valider structure arborescente claire
```

---

## Règles d'Or

### **Une couche = un fichier**
- `architecture_fichiers.md` : Fichiers et architecture globale
- `architecture_logicielle.md` : Applicatif uniquement  
- `logique_metier.md` : Métier uniquement
- `composants_techniques.md` : Technique uniquement
- `workflows.md` : Flux uniquement

### **Format IA-Optimal**
- **Arborescences > Paragraphes**
- **Listes > Texte descriptif**
- **Code minimal > Exemples volumineux**
- **Terminologie cohérente > Synonymes**

### **Workflow Unidirectionnel**
```
Analyse → Normalisation → Nettoyage → Finalisation
```

---

## Contrôles Qualité

### **Avant de valider**
- [ ] Chaque concept dans UNE seule couche
- [ ] Zéro doublons entre fichiers
- [ ] Arborescences claires et lisibles
- [ ] Terminologie harmonisée
- [ ] Pas de code dans les specs métier

### **Après modification**
- [ ] Mettre à jour changelog.md
- [ ] Vérifier cohérence des flux
- [ ] Supprimer fichiers obsolètes
- [ ] Valider structure cible atteinte

---

## Anti-Patterns à Éviter

**Mélanger les couches** : Métier dans architecture, technique dans workflows  
**Paragraphes volumineux** : Préférer listes et arborescences  
**Code dans les specs** : Uniquement concepts et flux  
**Doublons** : Un concept = un emplacement unique  
**Terminologie variable** : Harmoniser le vocabulaire  
**Suppression systématique** : Préférer l'adaptation et la réorganisation  
**Ignorer les fichiers existants** : Évaluer leur utilité avant de les déplacer/supprimer  

---

## Métriques de Succès

- **Lisibilité IA** : Arborescences claires, sections courtes
- **Maintenance** : 1 fichier par couche, zéro doublons  
- **Cohérence** : Terminologie uniforme, flux explicites
- **Synthèse** : Contenu concis, pas de verbiage inutile
- **Adaptabilité** : Structure flexible qui préserve l'existant pertinent
- **Continuité** : Pas de rupture brutale avec la documentation existante