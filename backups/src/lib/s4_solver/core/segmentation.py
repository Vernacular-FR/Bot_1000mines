from typing import List, Dict, Set, Tuple
from lib.s3_solver.core.grid_analyzer import GridAnalyzer

"""
Segmentation de la frontière en zones et composantes connexes.

Ce module optimise la résolution du problème CSP en découpant la frontière
en sous-problèmes indépendants. Les cases inconnues partageant les mêmes
contraintes sont regroupées en zones, puis les zones connectées forment
des composantes qui peuvent être résolues séparément.
"""

class Zone:
    """
    Un groupe de cases inconnues qui partagent exactement les mêmes contraintes.
    Du point de vue du solveur, toutes les cases d'une zone sont équivalentes.
    """
    def __init__(self, id: int, cells: List[Tuple[int, int]], constraints: List[Tuple[int, int]]):
        self.id = id
        self.cells = cells
        self.constraints = constraints # Liste des coordonnées des chiffres qui impactent cette zone
    
    def __repr__(self):
        return f"Zone(id={self.id}, size={len(self.cells)}, constraints={len(self.constraints)})"

class Component:
    """
    Un ensemble de Zones et de Contraintes qui forment un système isolé.
    Peut être résolu indépendamment des autres composants.
    """
    def __init__(self, id: int, zones: List[Zone], constraints: Set[Tuple[int, int]]):
        self.id = id
        self.zones = zones
        self.constraints = list(constraints)

class Segmentation:
    """
    Responsable de découper la frontière en Zones et Composants.
    """
    def __init__(self, analyzer: GridAnalyzer):
        self.analyzer = analyzer
        self.zones: List[Zone] = []
        self.cell_to_zone: Dict[Tuple[int, int], Zone] = {}
        self.components: List[Component] = []
        
        self._run()

    def _run(self):
        self._create_zones()
        self._create_components()

    def _create_zones(self):
        # Group by signature (set of constraints)
        signatures: Dict[Tuple[Tuple[int, int], ...], List[Tuple[int, int]]] = {} 
        
        frontier_cells = self.analyzer.get_frontier_cells()
        for cell in frontier_cells:
            # Get constraints for this cell
            constraints = self.analyzer.get_constraints_for_cell(cell[0], cell[1])
            # Sort to make a unique signature
            sig = tuple(sorted(constraints))
            
            if sig not in signatures:
                signatures[sig] = []
            signatures[sig].append(cell)
            
        # Create Zones
        zone_id = 0
        for sig, cells in signatures.items():
            # sig est un tuple de contraintes (coord chiffres)
            zone = Zone(zone_id, cells, list(sig))
            self.zones.append(zone)
            for cell in cells:
                self.cell_to_zone[cell] = zone
            zone_id += 1

    def _create_components(self):
        # Utilisation de Union-Find pour grouper les zones connectées
        parent = {z.id: z.id for z in self.zones}
        
        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]
        
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j
        
        # Pour chaque contrainte (chiffre), trouver quelles zones elle touche
        # Et unir ces zones
        # On inverse la map: Contrainte -> Liste de Zones
        constraint_to_zones: Dict[Tuple[int, int], List[Zone]] = {}
        
        for zone in self.zones:
            for c in zone.constraints:
                if c not in constraint_to_zones:
                    constraint_to_zones[c] = []
                constraint_to_zones[c].append(zone)
        
        # Unir les zones qui partagent une contrainte
        for c, zones_sharing_c in constraint_to_zones.items():
            if len(zones_sharing_c) > 1:
                base_zone = zones_sharing_c[0]
                for other_zone in zones_sharing_c[1:]:
                    union(base_zone.id, other_zone.id)
        
        # Regrouper les zones par parent racine
        components_map: Dict[int, List[Zone]] = {}
        for zone in self.zones:
            root = find(zone.id)
            if root not in components_map:
                components_map[root] = []
            components_map[root].append(zone)
        
        # Créer les objets Component
        comp_id = 0
        for root_id, zone_list in components_map.items():
            # Collecter toutes les contraintes uniques de ce composant
            all_constraints = set()
            for z in zone_list:
                for c in z.constraints:
                    all_constraints.add(c)
            
            comp = Component(comp_id, zone_list, all_constraints)
            self.components.append(comp)
            comp_id += 1
