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
- **Python 3.11** (pas )
  - Téléchargement direct : https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  - Cocher "Add Python to PATH" pendant l'installation
- **Google Chrome** (dernière version)
- **Git**

### Installation 
```powershell
# 1. Cloner le dépôt
git clone https://github.com/Vernacular-FR/Bot_1000mines
cd bot-1000mines

# Créer l'environnement
py -3.11 -m venv .venv
.\.venv\Scripts\activate

# Vérifier la version dans le venv
python --version
# Doit afficher: Python 3.11.9

# Installer les dépendances (CPU ou GPU)
pip install -r requirements.txt

# Lancer le bot
python main.py
```

#### Résolution de Problèmes Courants

**Erreur: "pip n'est pas reconnu"**
```powershell
# Utiliser python -m pip au lieu de pip
python -m pip install -r doc/requirements_minimal.txt
```

**Erreur: "l'exécution de scripts est désactivée"**
```powershell
# Ouvrir PowerShell en Administrateur et exécuter:
Set-ExecutionPolicy RemoteSigned
# Puis réessayer l'activation: .\.venv\Scripts\activate
```

**Vérifier l'installation**
```powershell
# Vérifier Python
python --version  # Doit afficher 3.11.x ou 3.12.x

# Vérifier les packages installés
pip list
```

---

## 📦 Dépendances

### Packages Essentiels (Toujours requis)
- **selenium** - Automation du navigateur Chrome
- **webdriver-manager** - Gestion automatique du ChromeDriver
- **numpy** - Traitement d'images et calculs matriciels
- **Pillow** - Manipulation d'images (capture, overlays)

### Packages Optionnels
- **torch** - Accélération GPU (25× plus rapide pour le downscaling)
  - Nécessite: GPU NVIDIA + CUDA
  - Fallback CPU automatique si absent

---

## 🎮 Comment utiliser ?

### Scénarios rapides
```bash
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

### Architecture Modulaire V2

```
bot-1000mines/
├── main.py                # Point d'entrée unique
├── src/
│   ├── services/          # Orchestrateurs métier
│   │   ├── s0_session_service.py  # Gestion session navigateur
│   │   └── s9_game_loop.py        # Boucle de jeu principale
│   └── lib/               # Bibliothèques spécialisées (pipeline)
│       ├── s0_browser/    # Pilote navigateur (Selenium, WebDriver)
│       ├── s0_coordinates/# Conversion grille↔écran, viewport
│       ├── s0_interface/  # Overlay UI (canvas HTML5, injection JS)
│       ├── s1_capture/    # Capture canvas (toDataURL, composition)
│       ├── s2_vision/     # Template matching, GPU downscaling
│       ├── s3_storage/    # Grille sparse + sets (frontier, active...)
│       ├── s4_solver/     # State analyzer, CSP, propagation
│       └── s5_planner/    # Ordonnancement et exécution actions
├── tests/                 # Tests unitaires organisés
├── doc/
│   └── SPECS/             # Documentation technique de référence
├── temp/                  # Artefacts de parties (auto-généré)
└── README.md              # Ce guide
```

### Pipeline de Traitement

```
┌─────────────┐
│ s0_browser  │ ← Selenium + ChromeDriver
├─────────────┤
│ s1_capture  │ ← Canvas → Image brute (512×512 tiles)
├─────────────┤
│ s2_vision   │ ← Template matching → Grille reconnue
├─────────────┤
│ s3_storage  │ ← Grid sparse + Sets (frontier/active/known)
├─────────────┤
│ s4_solver   │ ← State analyzer + CSP → Actions (SAFE/FLAG)
├─────────────┤
│ s5_planner  │ ← Ordonnancement + Exécution temps-réel
└─────────────┘
```

**Flux:** `capture → vision → storage → solver → planner → recapture`

### Modules Clés

- **s0_browser** - Automation navigateur, gestion ChromeDriver
- **s1_capture** - Capture multi-canvas, composition alignée
- **s2_vision** - CenterTemplateMatcher, GPU/CPU downscaling
- **s3_storage** - GridStore + SetManager (invariants, cohérence)
- **s4_solver** - StateAnalyzer, FocusActualizer, CSP borné
- **s5_planner** - Agent actif d'exécution, gestion vies/délais

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

## Licence

MIT License
