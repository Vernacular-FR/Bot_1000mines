from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set, Tuple

from src.lib.s3_storage.facade import Coord
from src.lib.s4_solver.s42_csp_solver.s422_segmentation import Segmentation


@dataclass
class ComponentRangeConfig:
    max_component_size: int = 50
    stability_threshold: int = 1


class ComponentRangeFilter:
    def __init__(self, config: ComponentRangeConfig | None = None):
        self.config = config or ComponentRangeConfig()
        self._component_cycles: Dict[frozenset[Coord], int] = {}

    def determine_eligible_components(
        self,
        segmentation: Segmentation,
        progress_cells: Iterable[Coord],
    ) -> Set[int]:
        progress_set = set(progress_cells)
        seen_keys: Set[frozenset[Coord]] = set()
        eligible_ids: Set[int] = set()

        for component in segmentation.components:
            component_cells = frozenset(cell for zone in component.zones for cell in zone.cells)
            if not component_cells:
                continue
            seen_keys.add(component_cells)

            if progress_set.intersection(component_cells):
                self._component_cycles[component_cells] = 0
                continue

            cycles = self._component_cycles.get(component_cells, 0) + 1
            self._component_cycles[component_cells] = cycles

            if cycles < self.config.stability_threshold:
                continue
            if len(component_cells) > self.config.max_component_size:
                continue

            eligible_ids.add(component.id)

        for key in list(self._component_cycles.keys()):
            if key not in seen_keys:
                del self._component_cycles[key]

        return eligible_ids
