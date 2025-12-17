from __future__ import annotations

from typing import Dict, List, Protocol, Set, Tuple


class FrontierViewProtocol(Protocol):
    """
    Interface minimale dont la segmentation a besoin.
    Permet d'adapter facilement StorageController/GridStore sans répliquer GridAnalyzer.
    """

    def get_frontier_cells(self) -> Set[Tuple[int, int]]:
        ...

    def get_constraints_for_cell(self, x: int, y: int) -> List[Tuple[int, int]]:
        ...


class Zone:
    """
    Groupe de cases inconnues partageant exactement les mêmes contraintes.
    Toutes les cellules d'une zone sont équivalentes pour le solver.
    """

    def __init__(self, identifier: int, cells: List[Tuple[int, int]], constraints: List[Tuple[int, int]]):
        self.id = identifier
        self.cells = cells
        self.constraints = constraints

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"Zone(id={self.id}, size={len(self.cells)}, constraints={len(self.constraints)})"


class Component:
    """
    Ensemble de zones + contraintes formant un sous-problème indépendant.
    """

    def __init__(self, identifier: int, zones: List[Zone], constraints: Set[Tuple[int, int]]):
        self.id = identifier
        self.zones = zones
        self.constraints = list(constraints)


class Segmentation:
    """
    Découpe la frontière en zones et composantes connexes.
    """

    def __init__(self, frontier_view: FrontierViewProtocol):
        self._frontier_view = frontier_view
        self.zones: List[Zone] = []
        self.cell_to_zone: Dict[Tuple[int, int], Zone] = {}
        self.components: List[Component] = []
        # Index auxiliaires : zone -> composante, composante -> ids de zones
        self.zone_to_component: Dict[int, int] = {}
        self.zone_ids_by_component: Dict[int, Set[int]] = {}
        self._run()

    def _run(self) -> None:
        self._create_zones()
        self._create_components()

    def _create_zones(self) -> None:
        signatures: Dict[Tuple[Tuple[int, int], ...], List[Tuple[int, int]]] = {}

        for cell in self._frontier_view.get_frontier_cells():
            constraints = self._frontier_view.get_constraints_for_cell(cell[0], cell[1])
            sig = tuple(sorted(constraints))
            signatures.setdefault(sig, []).append(cell)

        zone_id = 0
        for sig, cells in signatures.items():
            zone = Zone(zone_id, cells, list(sig))
            self.zones.append(zone)
            for cell in cells:
                self.cell_to_zone[cell] = zone
            zone_id += 1

    def _create_components(self) -> None:
        parent = {zone.id: zone.id for zone in self.zones}

        def find(idx: int) -> int:
            if parent[idx] == idx:
                return idx
            parent[idx] = find(parent[idx])
            return parent[idx]

        def union(i: int, j: int) -> None:
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        constraint_to_zones: Dict[Tuple[int, int], List[Zone]] = {}
        for zone in self.zones:
            for constraint in zone.constraints:
                constraint_to_zones.setdefault(constraint, []).append(zone)

        for zones in constraint_to_zones.values():
            if len(zones) > 1:
                base_zone = zones[0]
                for other in zones[1:]:
                    union(base_zone.id, other.id)

        components_map: Dict[int, List[Zone]] = {}
        for zone in self.zones:
            root = find(zone.id)
            components_map.setdefault(root, []).append(zone)

        comp_id = 0
        for zone_list in components_map.values():
            all_constraints: Set[Tuple[int, int]] = set()
            for zone in zone_list:
                all_constraints.update(zone.constraints)
            self.components.append(Component(comp_id, zone_list, all_constraints))
            self.zone_ids_by_component[comp_id] = {z.id for z in zone_list}
            for zone in zone_list:
                self.zone_to_component[zone.id] = comp_id
            comp_id += 1

    def zone_for_cell(self, coord: Tuple[int, int]) -> Zone | None:
        return self.cell_to_zone.get(coord)
