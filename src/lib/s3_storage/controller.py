from __future__ import annotations

from typing import Dict, Set, Tuple

from .facade import Bounds, Coord, FrontierSlice, GridCell, StorageControllerApi, StorageUpsert
from .s31_grid_store import GridStore


class StorageController(StorageControllerApi):
    """Facade for sparse grid storage with three sets management."""

    def __init__(self) -> None:
        self._store = GridStore()

    def upsert(self, data: StorageUpsert) -> None:
        """Apply batch updates to grid and sets."""
        self._store.apply_upsert(data)

    def get_frontier(self) -> FrontierSlice:
        """Return frontier slice (coordinates only)."""
        return FrontierSlice(coords=self._store.get_frontier_slice())

    def get_revealed(self) -> Set[Coord]:
        """Return revealed coordinates."""
        return self._store.get_revealed()

    def get_unresolved(self) -> Set[Coord]:
        """Return unresolved coordinates."""
        return self._store.get_unresolved()

    def get_cells(self, bounds: Bounds) -> Dict[Coord, GridCell]:
        """Extract cells within rectangular bounds."""
        return self._store.get_cells_in_bounds(bounds)

    def export_json(self, viewport_bounds: Bounds) -> Dict[str, object]:
        """Export visible cells and frontier for WebExtension."""
        cells = self._store.get_cells_in_bounds(viewport_bounds)
        cell_payload = [
            {
                "x": cell.x,
                "y": cell.y,
                "state": cell.state.value,
                "value": cell.value,
                "solver_status": cell.solver_status.value,
                "source": cell.source.value,
            }
            for cell in cells.values()
        ]
        frontier_subset = list(self._store.iter_frontier_in_bounds(viewport_bounds))

        return {
            "bounds": viewport_bounds,
            "cells": cell_payload,
            "frontier": frontier_subset,
        }
