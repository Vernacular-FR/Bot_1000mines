from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence, Tuple

from .facade import Bounds, CellState, FrontierMetrics, GridCell, SolverStatus

Coord = Tuple[int, int]


def compute_frontier_metrics(
    cells: Dict[Coord, GridCell], coords: Iterable[Coord]
) -> FrontierMetrics:
    coord_list: Sequence[Coord] = tuple(coords)
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
        1 for coord in coord_list if cells.get(coord, _DUMMY_CELL).state == CellState.FLAG
    )
    pending_actions = sum(
        1
        for coord in coord_list
        if cells.get(coord, _DUMMY_CELL).solver_status == SolverStatus.TO_PROCESS
    )
    bbox = compute_bbox(coord_list)
    attractor_score = min(1.0, pending_actions / max(1, size))

    return FrontierMetrics(
        size=size,
        flag_density=flag_count / size,
        bbox=bbox,
        pending_actions=pending_actions,
        attractor_score=attractor_score,
    )


def compute_bbox(coords: Iterable[Coord]) -> Optional[Bounds]:
    xs = [coord[0] for coord in coords]
    ys = [coord[1] for coord in coords]
    if not xs:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (min_x, min_y, (max_x - min_x) + 1, (max_y - min_y) + 1)


_DUMMY_CELL = GridCell(x=0, y=0, state=CellState.UNKNOWN)
