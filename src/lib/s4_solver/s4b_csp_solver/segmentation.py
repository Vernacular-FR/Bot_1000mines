"""Segmentation de la frontière en zones et composantes."""

from __future__ import annotations

from typing import Dict, List, Protocol, Set, Tuple

from src.lib.s3_storage.types import Coord


class FrontierViewProtocol(Protocol):
    """Interface minimale pour la segmentation."""

    def get_frontier_cells(self) -> Set[Coord]:
        ...

    def get_constraints_for_cell(self, x: int, y: int) -> List[Coord]:
        ...


class Zone:
    """Groupe de cellules partageant les mêmes contraintes."""

    def __init__(self, identifier: int, cells: List[Coord], constraints: List[Coord]):
        self.id = identifier
        self.cells = cells
        self.constraints = constraints

    def __repr__(self) -> str:
        return f"Zone(id={self.id}, size={len(self.cells)}, constraints={len(self.constraints)})"


class Component:
    """Ensemble de zones formant un sous-problème indépendant."""

    def __init__(self, identifier: int, zones: List[Zone], constraints: Set[Coord]):
        self.id = identifier
        self.zones = zones
        self.constraints = list(constraints)


class Segmentation:
    """Découpe la frontière en zones et composantes connexes."""

    def __init__(self, frontier_view: FrontierViewProtocol):
        self._frontier_view = frontier_view
        self.zones: List[Zone] = []
        self.cell_to_zone: Dict[Coord, Zone] = {}
        self.components: List[Component] = []
        self.zone_to_component: Dict[int, int] = {}
        self.zone_ids_by_component: Dict[int, Set[int]] = {}
        self._run()

    def _run(self) -> None:
        self._create_zones()
        self._create_components()

    def _create_zones(self) -> None:
        """Crée les zones à partir des signatures de contraintes."""
        signatures: Dict[Tuple[Coord, ...], List[Coord]] = {}

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
        """Regroupe les zones en composantes connexes via union-find."""
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

        constraint_to_zones: Dict[Coord, List[Zone]] = {}
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
            all_constraints: Set[Coord] = set()
            for zone in zone_list:
                all_constraints.update(zone.constraints)
            self.components.append(Component(comp_id, zone_list, all_constraints))
            self.zone_ids_by_component[comp_id] = {z.id for z in zone_list}
            for zone in zone_list:
                self.zone_to_component[zone.id] = comp_id
            comp_id += 1

    def zone_for_cell(self, coord: Coord) -> Zone | None:
        return self.cell_to_zone.get(coord)
