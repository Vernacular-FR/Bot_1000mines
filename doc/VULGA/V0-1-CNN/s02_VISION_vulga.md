# Journal Vision - CNN (Nov-Dec 2025)

**25 novembre 2025**  
*Basculer sur le CNN*  
Implémentation du réseau décrit dans architecture_neurone.md :  
- Dataset généré via template matching  
- 95% de précision mais 300ms/case  
"Trop lent pour des grilles de 1000 cases"

## 1. Le Piège des Pixels (Nov 2025)
```mermaid
graph TD
    A[Capture Selenium] --> B{Pixel Sampling}
    B -->|Éclats mines| C[Faux positifs]
    B -->|Décors| D[Confusions]
```

*"J'ai passé 3 semaines à tweaker les seuils... pour rien !"*
- Exemple typique :
  - Case réelle : 5
  - Reconnue comme : "3" (à cause d'un éclat)
  - Puis comme : "Décor" (faux positif)

## 2. L'Illusion CNN (Fin Nov 2025)
```mermaid
graph LR
    E[Dataset bruité] --> F[CNN]
    F --> G[95% accuracy]
    G --> H[300ms/inference]
    H --> I[Blocage pratique]
```

*"Le modèle avait tout compris... mais trop lentement !"*

## L'Épopée de la Reconnaissance Visuelle

### Le Cas Concret du Chiffre "5"
```mermaid
graph TD
    A[Image Réelle] --> B[CNN: 92% Confiance]
    A --> C[Template: 85%]
    B --> D{Problème}
    D --> E[Trop Lent]
    C --> F[Erreurs sur Décors]
```

*"Cette case '5' était notre pire ennemi - reconnaissable mais trop lentement"*

### Percée Technique
```mermaid
graph LR
    G[Canvas API] --> H[Extraction 10x10]
    H --> I[Match Central]
    I --> J[Early Exit si <90%]
```

*"En se concentrant sur le centre, on ignore les éclats perturbateurs"*