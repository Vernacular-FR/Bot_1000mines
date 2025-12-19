"""
Exemple d'intégration de l'overlay UI dans le game loop.

Ce fichier montre comment utiliser l'OverlayInjector pour afficher
les informations du solver en temps réel sur le canvas.
"""

from typing import Set, Dict
from src.lib.s0_interface.s07_overlay import (
    OverlayInjector,
    OverlayType,
    OverlayData,
    CellOverlayData,
    ActionOverlayData,
)
from src.lib.s3_storage.types import GridCell, Coord
from src.lib.s4_solver.types import SolverAction


# ============================================================================
# Exemple 1 : Initialisation dans SessionSetupService
# ============================================================================

def example_session_setup(driver):
    """
    Initialisation de l'overlay lors de la création de session.
    
    À intégrer dans SessionSetupService.initialize_game()
    """
    from src.lib.s0_interface.s07_overlay import create_overlay_injector
    
    # Créer l'injector (désactivé par défaut)
    overlay_injector = create_overlay_injector(
        enabled=True,
        default_overlay=OverlayType.OFF
    )
    
    # Injecter dans la page
    if overlay_injector.inject(driver):
        print("[SESSION] Overlay UI initialisé")
    else:
        print("[SESSION] Échec de l'initialisation de l'overlay")
    
    return overlay_injector


# ============================================================================
# Exemple 2 : Mise à jour après le solver (Frontier Overlay)
# ============================================================================

def example_update_frontier_overlay(
    driver,
    overlay_injector: OverlayInjector,
    frontier_cells: Dict[Coord, GridCell]
):
    """
    Met à jour l'overlay Frontier après l'exécution du solver.
    
    À intégrer dans GameLoopService après StatusAnalyzer.
    """
    # Convertir les cellules en données d'overlay
    cell_data = []
    for coord, cell in frontier_cells.items():
        cell_data.append(CellOverlayData(
            col=coord[0],
            row=coord[1],
            focus_level=str(cell.focus_level_frontier) if cell.focus_level_frontier else None
        ))
    
    # Créer le paquet de données
    overlay_data = OverlayData(
        overlay_type=OverlayType.FRONTIER,
        cells=cell_data
    )
    
    # Mettre à jour l'overlay
    overlay_injector.update_data(driver, overlay_data)


# ============================================================================
# Exemple 3 : Mise à jour après le solver (Actions Overlay)
# ============================================================================

def example_update_actions_overlay(
    driver,
    overlay_injector: OverlayInjector,
    solver_actions: list  # List[SolverAction]
):
    """
    Met à jour l'overlay Actions après l'exécution du solver.
    
    À intégrer dans GameLoopService après solve().
    """
    # Convertir les actions en données d'overlay
    action_data = []
    for action in solver_actions:
        action_data.append(ActionOverlayData(
            col=action.cell[0],
            row=action.cell[1],
            type=str(action.action),  # CLICK, FLAG, GUESS
            confidence=action.confidence
        ))
    
    # Créer le paquet de données
    overlay_data = OverlayData(
        overlay_type=OverlayType.ACTIONS,
        actions=action_data
    )
    
    # Mettre à jour l'overlay
    overlay_injector.update_data(driver, overlay_data)


# ============================================================================
# Exemple 4 : Mise à jour complète (Status Overlay)
# ============================================================================

def example_update_status_overlay(
    driver,
    overlay_injector: OverlayInjector,
    all_cells: Dict[Coord, GridCell]
):
    """
    Met à jour l'overlay Status avec tous les statuts des cellules.
    
    À intégrer dans GameLoopService après storage update.
    """
    # Convertir toutes les cellules visibles
    cell_data = []
    for coord, cell in all_cells.items():
        # Ne pas afficher les cellules UNREVEALED sauf si pertinent
        if cell.solver_status in ['JUST_VISUALIZED', 'NONE']:
            continue
            
        cell_data.append(CellOverlayData(
            col=coord[0],
            row=coord[1],
            status=str(cell.solver_status)
        ))
    
    # Créer le paquet de données
    overlay_data = OverlayData(
        overlay_type=OverlayType.STATUS,
        cells=cell_data
    )
    
    # Mettre à jour l'overlay
    overlay_injector.update_data(driver, overlay_data)


# ============================================================================
# Exemple 5 : Intégration complète dans GameLoopService
# ============================================================================

class GameLoopWithOverlayExample:
    """
    Exemple d'intégration dans GameLoopService.
    
    Montre où et comment appeler l'overlay injector.
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.overlay_injector = None
        self.overlay_enabled = True  # Configurable
    
    def setup(self):
        """Initialisation (appelé une fois au démarrage)."""
        if self.overlay_enabled:
            from src.lib.s0_interface.s07_overlay import create_overlay_injector
            
            self.overlay_injector = create_overlay_injector(
                enabled=True,
                default_overlay=OverlayType.FRONTIER  # Overlay par défaut
            )
            
            if not self.overlay_injector.inject(self.driver):
                print("[LOOP] Overlay désactivé (échec injection)")
                self.overlay_injector = None
    
    def run_iteration(self):
        """
        Exemple d'itération de game loop avec overlay.
        
        Pseudo-code simplifié pour illustrer l'intégration.
        """
        # 1. Capture + Vision
        capture_result = self.capture_service.capture()
        vision_result = self.vision_service.analyze(capture_result)
        
        # 2. Storage update
        self.storage.update_from_vision(vision_result)
        
        # 3. Status Analyzer (Pipeline 1)
        status_upsert = self.status_analyzer.analyze(
            self.storage.get_snapshot()
        )
        self.storage.apply_upsert(status_upsert)
        
        # → Mise à jour overlay Frontier (après classification)
        if self.overlay_injector:
            frontier_cells = {
                coord: cell 
                for coord, cell in self.storage.get_snapshot().items()
                if cell.solver_status == 'FRONTIER'
            }
            example_update_frontier_overlay(
                self.driver,
                self.overlay_injector,
                frontier_cells
            )
        
        # 4. Solver (CSP + Reducer)
        solver_output = self.solver.solve(
            self.storage.get_solver_input()
        )
        
        # → Mise à jour overlay Actions (après solver)
        if self.overlay_injector:
            example_update_actions_overlay(
                self.driver,
                self.overlay_injector,
                solver_output.actions
            )
        
        # 5. Action Mapper (Pipeline 2)
        action_upsert = self.action_mapper.map_actions(
            solver_output
        )
        self.storage.apply_upsert(action_upsert)
        
        # 6. Executor
        self.executor.execute(solver_output.actions)
        
        # → Option : Mise à jour overlay Status (vue complète)
        if self.overlay_injector and False:  # Activable si souhaité
            example_update_status_overlay(
                self.driver,
                self.overlay_injector,
                self.storage.get_snapshot()
            )
    
    def cleanup(self):
        """Nettoyage (appelé à la fin)."""
        if self.overlay_injector:
            self.overlay_injector.destroy(self.driver)


# ============================================================================
# Exemple 6 : Changement manuel d'overlay (via hotkey ou commande)
# ============================================================================

def example_switch_overlay(
    driver,
    overlay_injector: OverlayInjector,
    overlay_name: str
):
    """
    Change l'overlay actif (pour debug ou tests).
    
    Peut être appelé depuis un hotkey ou une commande CLI.
    """
    overlay_map = {
        'off': OverlayType.OFF,
        'frontier': OverlayType.FRONTIER,
        'actions': OverlayType.ACTIONS,
        'status': OverlayType.STATUS,
    }
    
    overlay_type = overlay_map.get(overlay_name.lower())
    if overlay_type:
        if overlay_injector.set_overlay(driver, overlay_type):
            print(f"[OVERLAY] Changé vers: {overlay_name}")
        else:
            print(f"[OVERLAY] Échec du changement")
    else:
        print(f"[OVERLAY] Type inconnu: {overlay_name}")
        print(f"[OVERLAY] Types disponibles: {list(overlay_map.keys())}")


# ============================================================================
# Exemple 7 : Utilisation avec arguments CLI
# ============================================================================

def example_cli_integration():
    """
    Montre comment intégrer l'overlay avec les arguments CLI.
    
    À ajouter dans main.py ou le parser d'arguments.
    """
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--overlay',
        type=str,
        choices=['off', 'frontier', 'actions', 'status'],
        default='off',
        help='Type d\'overlay à afficher'
    )
    parser.add_argument(
        '--no-overlay',
        action='store_true',
        help='Désactiver complètement l\'overlay'
    )
    
    args = parser.parse_args()
    
    # Utilisation
    if not args.no_overlay:
        from src.lib.s0_interface.s07_overlay import create_overlay_injector, OverlayType
        
        overlay_type_map = {
            'off': OverlayType.OFF,
            'frontier': OverlayType.FRONTIER,
            'actions': OverlayType.ACTIONS,
            'status': OverlayType.STATUS,
        }
        
        overlay_injector = create_overlay_injector(
            enabled=True,
            default_overlay=overlay_type_map[args.overlay]
        )
        
        return overlay_injector
    
    return None


# ============================================================================
# Résumé d'intégration
# ============================================================================

"""
INTÉGRATION RECOMMANDÉE (MVP) :

1. SessionSetupService.initialize_game()
   → Injecter l'overlay au démarrage
   → Stocker l'injector dans le contexte de session

2. GameLoopService.run_iteration()
   → Après StatusAnalyzer : mettre à jour overlay Frontier
   → Après Solver : mettre à jour overlay Actions (optionnel)

3. main.py
   → Ajouter argument --overlay {off,frontier,actions,status}
   → Créer l'injector selon l'argument

4. Pour debug
   → Utiliser example_switch_overlay() pour changer à la volée
   → Vérifier l'état avec overlay_injector.get_state()

POINTS D'ATTENTION :

- L'overlay est injecté une seule fois par session
- Les mises à jour sont incrémentales (pas de clear complet)
- Le menu UI permet de changer d'overlay manuellement
- La synchronisation des transformations est automatique (polling 60 FPS)
- Désactiver l'overlay si performance insuffisante (grandes grilles)

PROCHAINES ÉTAPES :

1. Tester l'injection dans une session de test
2. Vérifier que le menu apparaît et fonctionne
3. Intégrer dans GameLoopService avec données réelles
4. Ajuster les couleurs/styles si besoin
5. Optimiser si ralentissements constatés
"""
