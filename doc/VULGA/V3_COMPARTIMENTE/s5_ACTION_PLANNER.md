# S05 ACTION PLANNER — Vulgarisation V3

## Le Planner : Le Bras Armé du Bot

Dans cette version V3 "compartimentée", le Planner n'est plus un simple "secrétaire" qui fait des listes d'actions. Il est devenu l'agent actif qui exécute les décisions du solver.

### 1. Ordonnancement Intelligent
Il trie toujours les actions pour garantir un flux logique :
- **Drapeaux d'abord** : On sécurise les mines connues.
- **Ouvertures (Safes)** : On ouvre les cases sûres.
- **Paris (Guesses)** : En dernier recours.

### 2. Exécution Directe et Temps-Réel
Le Planner possède maintenant le contrôle du navigateur. Dès qu'une action est planifiée, elle est exécutée. Cela rend le bot beaucoup plus réactif.

### 3. Surveillance et "Intelligence Émotionnelle"
Le Planner surveille le compteur de vies en permanence :
- S'il clique sur une mine par erreur (explosion), il le détecte immédiatement.
- Il marque alors une pause de **2 secondes** pour laisser les animations de fumée se dissiper et la grille se stabiliser.
- Cela évite au bot de s'affoler et de cliquer n'importe où pendant une explosion.

### 4. Précision Chirurgicale (Clics Aimantés)
Grâce au nouveau système de coordonnées relatives :
- Le bot ne clique plus à des positions fixes sur l'écran.
- Il vise des positions **relatives à la grille**.
- Un script JavaScript recalcule la position exacte au millième de seconde près juste avant le clic.
- **Résultat** : Vous pouvez bouger la fenêtre dans tous les sens, le bot ne ratera jamais sa cible.

---

## Conclusion
La couche s5 est maintenant le centre névralgique de l'interaction. Elle garantit que les décisions du solver sont appliquées avec une fiabilité maximale, peu importe les conditions de navigation.
