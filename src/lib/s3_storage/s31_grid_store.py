from __future__ import annotations

from typing import Dict, Set, Tuple

from .facade import Bounds, Coord, GridCell, StorageUpsert
from .s32_set_manager import SetManager


class GridStore:
    """Sparse grid storage with delegated set management."""

    def __init__(self) -> None:
        self._cells: Dict[Coord, GridCell] = {}
        self._sets = SetManager()

    def apply_upsert(self, data: StorageUpsert) -> None:
        """Apply batch updates to grid and sets."""
        # Update cells
        self._cells.update(data.cells)
        
        # Delegate set updates to SetManager
        self._sets.apply_set_updates(
            revealed_add=data.revealed_add,
            unresolved_add=data.unresolved_add,
            unresolved_remove=data.unresolved_remove,
            frontier_add=data.frontier_add,
            frontier_remove=data.frontier_remove,
        )

    def get_frontier_slice(self) -> Set[Coord]:
        """Return frontier coordinates."""
        return self._sets.get_frontier()

    def get_revealed(self) -> Set[Coord]:
        """Return revealed coordinates."""
        return self._sets.get_revealed()

    def get_unresolved(self) -> Set[Coord]:
        """Return unresolved coordinates."""
        return self._sets.get_unresolved()

    def get_cells_in_bounds(self, bounds: Bounds) -> Dict[Coord, GridCell]:
        """Extract cells within rectangular bounds."""
        x_min, y_min, x_max, y_max = bounds
        result = {}
        for coord, cell in self._cells.items():
            x, y = coord
            if x_min <= x <= x_max and y_min <= y <= y_max:
                result[coord] = cell
        return result

    def iter_frontier_in_bounds(self, bounds: Bounds) -> Set[Coord]:
        """Iterate frontier coordinates within bounds."""
        return self._sets.iter_frontier_in_bounds(bounds)
