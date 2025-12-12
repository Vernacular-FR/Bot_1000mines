from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple

from .facade import (
    Bounds,
    FrontierSlice,
    GridCell,
    StorageUpsert,
)
from .s32_frontier_metrics import compute_frontier_metrics

Coord = Tuple[int, int]


class GridStore:
    """Low-level storage for the sparse grid, revealed set, and frontier set."""

    def __init__(self) -> None:
        self._cells: Dict[Coord, GridCell] = {}
        self._revealed: Set[Coord] = set()
        self._frontier: Set[Coord] = set()

    # ------------------------------------------------------------------ #
    # Mutations                                                          #
    # ------------------------------------------------------------------ #
    def apply_upsert(self, data: StorageUpsert) -> None:
        for coord, cell in data.cells.items():
            self._cells[coord] = cell
            if cell.state.is_revealed:
                self._revealed.add(coord)
            elif coord in self._revealed:
                self._revealed.discard(coord)

        self._revealed |= data.revealed_add

        self._frontier |= data.frontier_add
        self._frontier -= data.frontier_remove

    def mark_processed(self, positions: Iterable[Coord]) -> None:
        self._frontier -= set(positions)

    # ------------------------------------------------------------------ #
    # Accessors                                                          #
    # ------------------------------------------------------------------ #
    def get_frontier_slice(self) -> FrontierSlice:
        coords = set(self._frontier)
        metrics = compute_frontier_metrics(self._cells, coords)
        return FrontierSlice(coords=coords, metrics=metrics)

    def get_revealed(self) -> Set[Coord]:
        return set(self._revealed)

    def get_cells_in_bounds(self, bounds: Bounds) -> Dict[Coord, GridCell]:
        x, y, width, height = bounds
        x_max = x + width
        y_max = y + height
        return {
            coord: cell
            for coord, cell in self._cells.items()
            if x <= coord[0] < x_max and y <= coord[1] < y_max
        }

    def iter_frontier_in_bounds(self, bounds: Bounds) -> Iterable[Coord]:
        x, y, width, height = bounds
        x_max = x + width
        y_max = y + height
        return (
            coord
            for coord in self._frontier
            if x <= coord[0] < x_max and y <= coord[1] < y_max
        )
