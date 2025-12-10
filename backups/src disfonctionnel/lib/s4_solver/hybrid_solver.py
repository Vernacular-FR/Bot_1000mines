from typing import List, Dict, Tuple
from src.lib.s4_solver.core.grid_analyzer import GridAnalyzer
from src.lib.s4_solver.core.segmentation import Segmentation
from src.lib.s4_solver.csp.solver import CSPSolver
from src.lib.s4_solver.tensor_frontier import SolverContext

from src.lib.s3_tensor.grid_state import GamePersistence, GridDB

class HybridSolver:
    """
    Orchestrateur principal:
    1. Segmentation (Vision -> Maths)
    2. CSP (Maths -> Solutions)
    3. Probabilités (Solutions -> Décisions)
    """
    def __init__(self, analyzer: GridAnalyzer, tensor_context: Optional[SolverContext] = None):
        self.analyzer = analyzer
        self.segmentation = Segmentation(analyzer, tensor_context=tensor_context)
        self.csp = CSPSolver(analyzer)
        
        self.zone_probabilities: Dict[int, float] = {} # ZoneID -> Prob(Mine) par CELLULE
        self.solutions_by_component: Dict[int, List] = {}
        
    def solve(self):
        """Exécute le pipeline complet de résolution"""
        self.zone_probabilities = {}
        self.solutions_by_component = {}
        
        for component in self.segmentation.components:
            # 1. Résoudre CSP
            solutions = self.csp.solve_component(component)
            self.solutions_by_component[component.id] = solutions
            
            if not solutions:
                # Incohérence détectée ou bug
                print(f"WARN: No solution for component {component.id}")
                continue
                
            # 2. Calculer Probabilités
            total_weight = 0.0
            zone_weighted_mines: Dict[int, float] = {z.id: 0.0 for z in component.zones}
            
            for sol in solutions:
                weight = sol.get_prob_weight(component.zones)
                total_weight += weight
                
                for zid, mines in sol.zone_assignment.items():
                    zone_weighted_mines[zid] += mines * weight
            
            # 3. Normaliser
            if total_weight > 0:
                for z in component.zones:
                    # Espérance du nombre de mines dans la zone
                    expected_mines = zone_weighted_mines[z.id] / total_weight
                    
                    # Probabilité qu'une cellule spécifique de la zone soit une mine
                    # P(Cell) = E[Mines] / Size
                    prob = expected_mines / len(z.cells)
                    self.zone_probabilities[z.id] = prob
            else:
                print(f"WARN: Total weight 0 for component {component.id}")

    def get_safe_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules identifiées comme sûres (0%)"""
        safe = []
        for z in self.segmentation.zones:
            if z.id in self.zone_probabilities:
                prob = self.zone_probabilities[z.id]
                if prob < 0.000001: # Epsilon pour float
                    safe.extend(z.cells)
        return safe

    def get_flag_cells(self) -> List[Tuple[int, int]]:
        """Retourne les cellules identifiées comme mines (100%)"""
        flags = []
        for z in self.segmentation.zones:
            if z.id in self.zone_probabilities:
                prob = self.zone_probabilities[z.id]
                if prob > 0.999999:
                    flags.extend(z.cells)
        return flags

    def get_best_guess(self) -> Tuple[int, int, float]:
        """
        Retourne la meilleure case à deviner (plus basse probabilité).
        TODO: Implémenter Information Gain pour départager.
        """
        best_prob = 1.1
        best_cell = None
        
        for z in self.segmentation.zones:
            if z.id in self.zone_probabilities:
                prob = self.zone_probabilities[z.id]
                # On cherche prob min mais > 0 (car =0 c'est safe, pas guess)
                if 0.000001 < prob < best_prob:
                    best_prob = prob
                    # On prend la première cellule de la zone (toutes équivalentes)
                    if z.cells:
                        best_cell = z.cells[0]
        
        return (best_cell[0], best_cell[1], best_prob) if best_cell else None

    def save_to_db(self, db: GridDB):
        """Sauvegarde les actions et les probabilités dans la GridDB"""
        
        # 1. Actions Safe (Reveal)
        for x, y in self.get_safe_cells():
            db.add_action({
                "type": "reveal",
                "coordinates": (x, y),
                "confidence": 1.0,
                "reasoning": "CSP Solver (0% mine)"
            })
        
        # 2. Actions Flag
        for x, y in self.get_flag_cells():
             db.add_action({
                "type": "flag",
                "coordinates": (x, y),
                "confidence": 1.0,
                "reasoning": "CSP Solver (100% mine)"
            })
            
        # 3. Metadata Probabilités
        for z in self.segmentation.zones:
            if z.id in self.zone_probabilities:
                prob = self.zone_probabilities[z.id]
                for x, y in z.cells:
                    # On charge la cellule complète pour ne pas écraser d'autres champs
                    cell = db.get_cell(x, y)
                    if cell:
                        if "metadata" not in cell: cell["metadata"] = {}
                        cell["metadata"]["mine_probability"] = prob
                        db.add_cell(x, y, cell)
                        
        # 4. Si aucune action sûre, proposer un Guess
        safe = self.get_safe_cells()
        flags = self.get_flag_cells()
        if not safe and not flags:
            guess = self.get_best_guess()
            if guess:
                x, y, prob = guess
                db.add_action({
                    "type": "guess",
                    "coordinates": (x, y),
                    "confidence": 1.0 - prob, # Confidence is safety
                    "reasoning": f"Best Guess ({prob*100:.1f}% mine)"
                })
