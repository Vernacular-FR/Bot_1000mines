"""
Configuration centrale pour le bot Démineur.

Ce fichier contient tous les paramètres configurables du jeu,
y compris les dimensions graphiques et les temps d'attente.
"""

# Paramètres graphiques
CELL_SIZE = 24         # Taille d'une case en pixels
CELL_BORDER = 1        # Épaisseur des bordures entre les cases en pixels
# Offset de référence de la grille dans le CanvasSpace (position réelle des bordures)
GRID_REFERENCE_POINT = (-1, -1)

# Paramètres du viewport
VIEWPORT_CONFIG = {
    'position': (0, 54),    # Position du coin supérieur gauche du viewport (x, y) en pixels
    'description': 'Coordonnées du viewport dans le ScreenSpace'
}

# Temps d'attente (en secondes)
WAIT_TIMES = {
    'page_load': 10,           # Temps d'attente maximum pour le chargement d'une page
    'element': 10,             # Temps d'attente pour trouver un élément
    'animation': 0.05,         # Temps d'attente pour les animations
    'between_actions': 0.02,   # Temps d'attente entre deux actions (clics, etc.)
    'after_click': 0.01,       # Temps d'attente après un clic
    'game_start': 2,           # Temps d'attente après le démarrage du jeu
}

# Paramètres du navigateur
BROWSER_CONFIG = {
    'headless': False,         # Mode sans affichage
    'maximize': True,          # Ouvre le navigateur en mode plein écran
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Paramètres du jeu
GAME_CONFIG = {
    'url': 'https://www.1000mines.com/',  # URL du jeu
    'max_retries': 3,                        # Nombre de tentatives en cas d'échec
    'debug': True,                            # Mode débogage (affiche plus d'informations)
    'grid_reference_point': GRID_REFERENCE_POINT  # Configuration du point de référence de la grille
}

# Configuration des difficultés
DIFFICULTY_CONFIG = {
    'beginner': {
        'name': 'Beginner',
        'selenium_id': 'new-game-beginner'
    },
    'master': {
        'name': 'Master',
        'selenium_id': 'new-game-master'
    },
    'ultimate': {
        'name': 'Ultimate',
        'selenium_id': 'new-game-ultimate'
    },
    'impossible': {
        'name': 'Impossible',
        'selenium_id': 'new-game-impossible'
    },
    'deathmatch': {
        'name': 'Deathmatch',
        'selenium_id': 'new-game-deathmatch'
    }
}

# Configuration par défaut
DEFAULT_DIFFICULTY = 'impossible'

# Paramètres du solver CSP
CSP_CONFIG = {'max_zones_per_component':30} # Limite de zones par composante pour éviter explosion backtracking

# Chemins des fichiers (un niveau = un chemin)
# NOTE: Ces chemins sont les valeurs par défaut.
# Le GameLoopService génère dynamiquement des chemins par partie dans temp/games/{game_id}/
PATHS = {
    'logs': 'logs',
}

def get_game_paths(game_id: str) -> dict:
    """
    Retourne les chemins configurés pour une partie spécifique.
    Structure: temp/games/{game_id}/{category}/...
    """
    base = f"temp/games/{game_id}"
    return {
        # Screenshots et captures
        'full_pages': f"{base}/s0_full_pages",           # Viewport complet
        'interface': f"{base}/s0_interface",             # Interface overlays
        'zone': f"{base}/s1_zone",                       # Zones de jeu capturées
        'grid': f"{base}/s1_grid",                       # Données de grille
        
        # Analyse et reconnaissance
        'analysis': f"{base}/s2_analysis",               # Rapports et overlays d'analyse
        
        # Solver et résolution
        'solver': f"{base}/s4_solver",                   # Overlays du solver
        
        # Actions et exécution
        'actions': f"{base}/s4_actions",                 # Données d'actions
        
        # Métadonnées et base de données
        'metadata': f"{base}/metadata.json",           # Métadonnées de la partie
        'grid_db': f"{base}/grid_state_db.json"        # Base de données de la grille
    }