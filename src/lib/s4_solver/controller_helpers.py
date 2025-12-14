from __future__ import annotations

from dataclasses import replace
from typing import Dict, Iterable, Set, Tuple

from src.lib.s3_storage.facade import (
    ActionStatus,
    Bounds,
    GridCell,
    LogicalCellState,
    SolverStatus,
)

Coord = Tuple[int, int]


def compute_bounds(coords: Set[Coord]) -> Bounds:
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    min_x, max_x = min(xs) - 2, max(xs) + 3
    min_y, max_y = min(ys) - 2, max(ys) + 3
    return (min_x, min_y, max_x, max_y)


def build_metadata_updates(
    cells: Dict[Coord, GridCell],
    frontier_coords: Set[Coord],
    safe_cells: Iterable[Coord],
    flag_cells: Iterable[Coord],
) -> Dict[Coord, GridCell]:
    safe_set = set(safe_cells)
    flag_set = set(flag_cells)
    updated: Dict[Coord, GridCell] = {}

    for coord, cell in cells.items():
        desired_status = _classify_solver_status(coord, cell, frontier_coords, cells)
        desired_action = cell.action_status

        if coord in safe_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.SAFE
        elif coord in flag_set:
            desired_status = SolverStatus.SOLVED
            desired_action = ActionStatus.FLAG
        elif desired_action != ActionStatus.NONE:
            desired_action = ActionStatus.NONE

        if desired_status != cell.solver_status or desired_action != cell.action_status:
            updated[coord] = replace(
                cell,
                solver_status=desired_status,
                action_status=desired_action,
            )

    return updated


def _classify_solver_status(
    coord: Coord,
    cell: GridCell,
    frontier_coords: Set[Coord],
    cells: Dict[Coord, GridCell],
) -> SolverStatus:
    if coord in frontier_coords and cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.FRONTIER

    if cell.logical_state == LogicalCellState.OPEN_NUMBER:
        if _has_unrevealed_neighbor(coord, cells):
            return SolverStatus.ACTIVE
        return SolverStatus.SOLVED

    if cell.logical_state in {LogicalCellState.EMPTY, LogicalCellState.CONFIRMED_MINE}:
        return SolverStatus.SOLVED

    if cell.logical_state == LogicalCellState.UNREVEALED:
        return SolverStatus.NONE

    return cell.solver_status


def _has_unrevealed_neighbor(coord: Coord, cells: Dict[Coord, GridCell]) -> bool:
    for nx, ny in _iter_neighbors(coord):
        neighbor = cells.get((nx, ny))
        if neighbor and neighbor.logical_state == LogicalCellState.UNREVEALED:
            return True
    return False


def _iter_neighbors(coord: Coord):
    x, y = coord
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield x + dx, y + dy
