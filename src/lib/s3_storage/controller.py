from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, Optional, Set

from .facade import (
    Bounds,
    CellState,
    FrontierMetrics,
    FrontierSlice,
    GridCell,
    SolverStatus,
    StorageControllerApi,
    StorageUpsert,
)


class StorageController(StorageControllerApi):
    def __init__(self) -> None:
        self._cells: Dict[tuple[int, int], GridCell] = {}
        self._revealed: Set[tuple[int, int]] = set()
        self._frontier: Set[tuple[int, int]] = set()

    # Public API -------------------------------------------------------------
    def upsert(self, data: StorageUpsert) -> None:
        for coord, cell in data.cells.items():
            self._cells[coord] = cell
            if cell.state.is_revealed:
                self._revealed.add(coord)
            elif coord in self._revealed:
                self._revealed.discard(coord)

        self._revealed |= data.revealed_add

        self._frontier |= data.frontier_add
        self._frontier -= data.frontier_remove

    def get_frontier(self) -> FrontierSlice:
        coords = set(self._frontier)
        metrics = self._compute_frontier_metrics(coords)
        return FrontierSlice(coords=coords, metrics=metrics)

    def get_revealed(self) -> Set[tuple[int, int]]:
        return set(self._revealed)

    def mark_processed(self, positions: Set[tuple[int, int]]) -> None:
        self._frontier -= positions

    def get_cells(self, bounds: Bounds) -> Dict[tuple[int, int], GridCell]:
        x, y, width, height = bounds
        x_max = x + width
        y_max = y + height
        return {
            coord: cell
            for coord, cell in self._cells.items()
            if x <= coord[0] < x_max and y <= coord[1] < y_max
        }

    def export_json(self, viewport_bounds: Bounds) -> Dict[str, object]:
        cells = self.get_cells(viewport_bounds)
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

        frontier_subset = [
            coord for coord in self._frontier if self._in_bounds(coord, viewport_bounds)
        ]

        return {
            "bounds": viewport_bounds,
            "cells": cell_payload,
            "frontier": frontier_subset,
        }

    # Internal helpers ------------------------------------------------------
    def _compute_frontier_metrics(
        self, coords: Iterable[tuple[int, int]]
    ) -> FrontierMetrics:
        coord_list = list(coords)
        size = len(coord_list)
        if size == 0:
            return FrontierMetrics(
                size=0,
                flag_density=0.0,
                bbox=None,
                pending_actions=0,
                attractor_score=0.0,
            )

        flag_count = sum(
            1 for coord in coord_list if self._cells.get(coord, _DUMMY_CELL).state == CellState.FLAG
        )
        pending_actions = sum(
            1
            for coord in coord_list
            if self._cells.get(coord, _DUMMY_CELL).solver_status == SolverStatus.TO_PROCESS
        )
        bbox = _compute_bbox(coord_list)
        attractor_score = min(1.0, pending_actions / max(1, size))

        return FrontierMetrics(
            size=size,
            flag_density=flag_count / size,
            bbox=bbox,
            pending_actions=pending_actions,
            attractor_score=attractor_score,
        )

    def _in_bounds(self, coord: tuple[int, int], bounds: Bounds) -> bool:
        x, y, width, height = bounds
        return x <= coord[0] < x + width and y <= coord[1] < y + height


_DUMMY_CELL = GridCell(x=0, y=0, state=CellState.UNKNOWN)


def _compute_bbox(coords: Iterable[tuple[int, int]]) -> Optional[Bounds]:
    xs = [coord[0] for coord in coords]
    ys = [coord[1] for coord in coords]
    if not xs:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (min_x, min_y, (max_x - min_x) + 1, (max_y - min_y) + 1)
