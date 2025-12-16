# Bot Démineur 1000mines

🚀 **Bot automatisé pour jouer au démineur sur 1000mines.com**

---

## 🎯 Qu'est-ce que c'est ?

Un bot intelligent qui :
- **Observe l'écran** comme un humain via Selenium + vision
- **Analyse la grille** pour construire un `grid_db.json` par partie
- **Joue automatiquement** avec un contrôleur fiable

Les services orchestrent l'ensemble, la logique bas niveau vit dans `src/lib/`.

---

## 🚀 Installation Rapide

### Prérequis
- Python 3.8+
- Google Chrome
- Git

### Installation en 30 secondes
```powershell
# Cloner
git clone <URL_REPO>
cd bot-1000mines

# Créer l'environnement
py -3.11 -m venv .venv311
.\.venv311\Scripts\activate

# Installer les dépendances (CPU ou GPU)
pip install -r requirements.txt

# Lancer
python main.py
```

---

## 🎮 Comment utiliser ?

### Scénarios rapides
```bash
# Scénario 3 : une passe capture → analyse → solve → actions
python scenario3.py

# Scénario 4 : boucle complète
python scenario4.py

# Interface menu historique
python main.py
```

Pipeline d'exécution :
1. `Minesweeper1000Bot` appelle `SessionSetupService` → navigateur, bot, `GameSessionManager`
2. `ZoneCaptureService` capture la zone interne (`screenshot_manager` + overlays)
3. `OptimizedAnalysisService` + `GameSolverService` remplissent `grid_db.json`
4. `ActionExecutorService` délègue à `MineSweeperBot.execute_game_action`
5. `GamePersistence` (lib/s2_analysis) gère `temp/games/{game_id}` (actions, metadata, grid_db)

---

## 📁 Structure du Projet

```
bot-1000mines/
├── src/
│   ├── app/              # Points d’entrée (CLI / scripts)
│   ├── services/         # Orchestrateurs (session, capture, boucle…)
│   └── lib/
│       ├── s0_viewport/  # DOM + coordonnées (réutilise lib/s0_navigation)
│       ├── s1_capture/   # canvas.toDataURL / CDP
│       ├── s2_vision/    # PixelSampler + debug overlays
│       ├── s3_storage/   # Archive + frontière compacte
│       ├── s4_solver/    # Motifs + solveur local (debug inclus)
│       ├── s5_actionplanner/# Heatmap + trajets multi-étapes
│       └── s6_action/    # Exécution multi-clics
├── tests/                # Tests unitaires
├── doc/                  # Synthèses (pipeline, README)
├── doc/SPECS/            # Référence technique (architecture, roadmap…)
├── temp/                 # Artefacts de parties (généré automatiquement)
├── main.py               # Stub lançant src.main.run()
└── README.md             # Ce guide
```

---

## ⚙️ Configuration (Optionnel)

Variables d'environnement utiles :
```bash
# Chrome
CHROME_BIN=/usr/bin/google-chrome
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
```

---

## 📊 Résultats & persistance

Chaque partie vit dans `temp/games/{game_id}/` :
- `s0_full_pages/` : captures viewport et overlays interface
- `s1_zone/` : captures de zone pour l'analyse
- `s2_analysis/` : JSON d'analyse + `grid_db.json`
- `s4_actions/` : logs d'actions via `GamePersistence.save_actions`
- `metadata.json` : résumé de la partie (état final, durée, itérations, actions)

Supprimez un dossier pour faire de la place : aucun autre état persistant.

### Lancer le pipeline minimal

Sans overlay (par défaut) :
```bash
python src/main.py --difficulty impossible
```

Avec overlays (vision + solver) :
```bash
python src/main.py --difficulty impossible --overlay --verbose
```

---

## 🤝 Contribuer

Pour approfondir :
- `SPECS/ARCHITECTURE.md` : blueprint complet
- `SPECS/DEVELOPMENT_JOURNAL.md` : journal de bord
- `SRC_REFACTOR_PLAN.md` : état de la migration vers `src/`
- `docs/specs/` (INDEX, architecture) : responsabilités détaillées

---

## 📄 Licence

MIT License - Fait avec ❤️

---

**Simple, efficace, intelligent** 🎯
