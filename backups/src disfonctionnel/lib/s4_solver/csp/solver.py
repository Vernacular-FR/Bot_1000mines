from typing import List, Dict, Tuple, Optional
from src.lib.s4_solver.core.segmentation import Component, Zone
from src.lib.s4_solver.core.grid_analyzer import GridAnalyzer

class Solution:
    def __init__(self, zone_assignment: Dict[int, int]):
        self.zone_assignment = zone_assignment # ZoneID -> NumMines
    
    def get_prob_weight(self, zones: List[Zone]) -> float:
        """
        Calcule le poids combinatoire de cette solution.
        C'est le produit des C(n, k) pour chaque zone.
        """
        weight = 1.0
        for zone in zones:
            if zone.id in self.zone_assignment:
                k = self.zone_assignment[zone.id] # Mines placées
                n = len(zone.cells) # Taille de la zone
                weight *= self._combinations(n, k)
        return weight

    def _combinations(self, n: int, k: int) -> int:
        """Calcule C(n, k)"""
        if k < 0 or k > n:
            return 0
        if k == 0 or k == n:
            return 1
        if k > n // 2:
            k = n - k
        
        res = 1
        for i in range(k):
            res = res * (n - i) // (i + 1)
        return res

class ConstraintModel:
    """Modèle interne optimisé pour le backtracking"""
    def __init__(self, limit: int, zone_ids: List[int]):
        self.limit = limit
        self.zone_ids = zone_ids
        self.current_sum = 0
        self.assigned_count = 0 # Combien de zones liées sont assignées

class CSPSolver:
    def __init__(self, analyzer: GridAnalyzer):
        self.analyzer = analyzer
        self.solutions: List[Solution] = []

    def solve_component(self, component: Component) -> List[Solution]:
        """
        Trouve toutes les configurations valides de mines pour ce composant.
        """
        self.solutions = []
        
        # 1. Préparer les contraintes
        # On mappe ZoneID -> Liste de ConstraintModel
        zone_to_constraints: Dict[int, List[ConstraintModel]] = {}
        all_constraints: List[ConstraintModel] = []
        
        # Pour chaque contrainte physique (chiffre) du composant
        for c_coord in component.constraints:
            val = self.analyzer.get_cell(*c_coord)
            
            # Compter les drapeaux déjà posés autour (hors zones inconnues)
            # Les zones contiennent SEULEMENT les cases inconnues (Frontier)
            # Donc on regarde les voisins 'flag' qui sont DANS la grille mais PAS dans une zone ?
            # Non, Grid.FLAG est utilisé.
            # Mais attention : la frontière est construite sur les Unknowns.
            # Si on a un flag, il n'est PAS dans la frontière, donc PAS dans une zone.
            # Donc on doit réduire la limite du chiffre par le nombre de flags voisins.
            
            neighbors = self._get_neighbors(*c_coord)
            flags = 0
            relevant_zones = []
            
            for nx, ny in neighbors:
                n_val = self.analyzer.get_cell(nx, ny)
                if n_val == self.analyzer.FLAG:
                    flags += 1
                elif n_val == self.analyzer.UNKNOWN:
                    # Trouver à quelle zone appartient ce voisin
                    # Optimisation: Component a déjà la liste des zones
                    # On peut chercher dans component.zones
                    for z in component.zones:
                        if (nx, ny) in z.cells:
                            relevant_zones.append(z.id)
                            break
            
            effective_limit = val - flags
            
            # Créer le modèle de contrainte
            # Attention : relevant_zones peut contenir des doublons si plusieurs cases d'une même zone touchent le chiffre ?
            # OUI.
            # Si une zone a 2 cases qui touchent le chiffre, elle compte pour 1 variable Z_i
            # MAIS la contrainte est Somme(Mines(Cell)) = Limite.
            # Or on résout pour Z_i = Mines(Zone).
            # Si la contrainte touche TOUTE la zone, alors Mines(Zone) contribue.
            # Si la contrainte touche UNE PARTIE de la zone... AIE.
            # C'est là que la segmentation est CRITIQUE.
            # DÉFINITION: Une Zone est un groupe de cases qui partagent EXACTEMENT les mêmes contraintes.
            # Donc, si une case de la zone touche le chiffre C, TOUTES les cases de la zone touchent le chiffre C.
            # PREUVE: Sinon elles n'auraient pas la même signature (ensemble de voisins chiffres).
            # DONC: On peut dire que Z_i contribue pleinement à la contrainte.
            
            # On dédoublonne les zones
            unique_zone_ids = sorted(list(set(relevant_zones)))
            
            print(f"DEBUG: Constraint {c_coord} (Val={val}, Flags={flags}) -> EffLimit={effective_limit}, Zones={unique_zone_ids}")

            cm = ConstraintModel(effective_limit, unique_zone_ids)
            all_constraints.append(cm)
            
            for zid in unique_zone_ids:
                if zid not in zone_to_constraints:
                    zone_to_constraints[zid] = []
                zone_to_constraints[zid].append(cm)

        # 2. Variables à assigner
        for z in component.zones:
             print(f"DEBUG: Zone {z.id} Size={len(z.cells)}")

        variables = [z.id for z in component.zones]
        # Domaine de chaque variable : 0 à len(zone.cells)
        domains = {z.id: list(range(len(z.cells) + 1)) for z in component.zones}
        
        # Optimisation: Trier les variables par 'Most Constrained' ?
        # Celles qui apparaissent dans le plus de contraintes
        variables.sort(key=lambda zid: len(zone_to_constraints.get(zid, [])), reverse=True)
        
        # 3. Lancer le backtracking
        self._backtrack({}, variables, domains, zone_to_constraints)
        
        return self.solutions

    def _backtrack(self, 
                   assignment: Dict[int, int], 
                   unassigned: List[int], 
                   domains: Dict[int, List[int]],
                   zone_to_constraints: Dict[int, List[ConstraintModel]]):
        
        # Base case: Success
        if not unassigned:
            self.solutions.append(Solution(assignment.copy()))
            return

        # Select var
        var = unassigned[0]
        rest = unassigned[1:]
        
        # Try values
        for val in domains[var]:
            # Check consistency
            valid = True
            
            # Mise à jour temporaire des contraintes impactées
            affected_constraints = zone_to_constraints.get(var, [])
            updated_constraints = []
            
            for c in affected_constraints:
                c.current_sum += val
                c.assigned_count += 1
                updated_constraints.append(c)
                
                # Check 1: Overfill
                if c.current_sum > c.limit:
                    valid = False
                
                # Check 2: Underfill impossible
                # Si on a assigné toutes les zones de cette contrainte
                # et que la somme n'est pas atteinte
                elif c.assigned_count == len(c.zone_ids) and c.current_sum != c.limit:
                    valid = False
                
                if not valid:
                    # print(f"DEBUG: Fail Var {var}={val} on C(Limit={c.limit}, Sum={c.current_sum}, Count={c.assigned_count}/{len(c.zone_ids)})")
                    break # Stop checking constraints for this value
            
            if valid:
                # Continue recursion
                assignment[var] = val
                self._backtrack(assignment, rest, domains, zone_to_constraints)
                del assignment[var]
                
            # Backtrack / Cleanup (Always revert changes made in this iteration)
            for c in updated_constraints:
                c.current_sum -= val
                c.assigned_count -= 1
    
    def _get_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Retourne les voisins d'une case"""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.analyzer.get_cell(nx, ny) is not None:
                    neighbors.append((nx, ny))
        return neighbors
