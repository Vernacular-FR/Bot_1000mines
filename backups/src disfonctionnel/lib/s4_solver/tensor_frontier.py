#!/usr/bin/env python3
"""
TensorFrontier - Adaptateur Frontier pour TensorGrid (S4)

Objectifs :
    - Segmenter rapidement le frontier_mask issu de TensorGrid
    - Fournir des zones structurées pour le solver (Stats, priorités)
    - Exploiter HintCache pour prioriser les zones sales
    - Offrir un cache pour éviter les extractions redondantes
"""

from __future__ import annotations

import time
from time import perf_counter
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

try:  # Optionnel : SciPy pour l'étiquetage rapide
    from scipy import ndimage  # type: ignore

    _HAS_SCIPY = True
except Exception:  # pragma: no cover - SciPy peut être absent
    ndimage = None
    _HAS_SCIPY = False

from src.lib.s3_tensor.hint_cache import HintCache, HintEvent
from src.lib.s3_tensor.tensor_grid import GridBounds, TensorGrid
from src.lib.s3_tensor.types import CellType

UNKNOWN_CODE = TensorGrid.encode_cell_type(CellType.UNREVEALED)
FLAG_CODE = TensorGrid.encode_cell_type(CellType.FLAG)
NUMBER_CODE_MAP = {
    TensorGrid.encode_cell_type(CellType.NUMBER_1): 1,
    TensorGrid.encode_cell_type(CellType.NUMBER_2): 2,
    TensorGrid.encode_cell_type(CellType.NUMBER_3): 3,
    TensorGrid.encode_cell_type(CellType.NUMBER_4): 4,
    TensorGrid.encode_cell_type(CellType.NUMBER_5): 5,
    TensorGrid.encode_cell_type(CellType.NUMBER_6): 6,
    TensorGrid.encode_cell_type(CellType.NUMBER_7): 7,
    TensorGrid.encode_cell_type(CellType.NUMBER_8): 8,
}


class FrontierZoneType(Enum):
    CSP_SOLVABLE = "csp_solvable"
    MONTE_CARLO = "monte_carlo"
    NEURAL_ASSIST = "neural_assist"
    TRIVIAL = "trivial"


@dataclass
class FrontierZone:
    zone_id: str
    zone_type: FrontierZoneType
    bounds: GridBounds
    unknown_cells: Set[Tuple[int, int]]
    number_cells: Dict[Tuple[int, int], int]
    safe_cells: Set[Tuple[int, int]]
    mine_cells: Set[Tuple[int, int]]
    complexity_score: float
    priority: float
    metadata: Dict[str, Any]

    def size(self) -> int:
        return len(self.unknown_cells)

    def constraint_density(self) -> float:
        if not self.unknown_cells:
            return 0.0
        return len(self.number_cells) / len(self.unknown_cells)

    def is_trivial(self) -> bool:
        return bool(self.safe_cells or self.mine_cells) and not self.unknown_cells


@dataclass
class SolverContext:
    tensor_grid: TensorGrid
    hint_cache: HintCache
    global_bounds: GridBounds
    frontier_zones: List[FrontierZone]
    total_unknown: int
    total_frontier: int
    processing_time: float
    metadata: Dict[str, Any]


class TensorFrontier:
    def __init__(
        self,
        tensor_grid: TensorGrid,
        hint_cache: HintCache,
        *,
        min_zone_size: int = 1,
        max_zone_size: int = 64,
        enable_hint_integration: bool = True,
    ) -> None:
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        self.min_zone_size = min_zone_size
        self.max_zone_size = max_zone_size
        self.enable_hint_integration = enable_hint_integration

        self._cached_context: Optional[SolverContext] = None
        self._last_view_hash: Optional[int] = None

    # ------------------------------------------------------------------ #
    # API principale
    # ------------------------------------------------------------------ #
    def extract_solver_context(
        self,
        solver_view: Dict[str, Any],
        hint_events: Optional[Sequence[HintEvent]] = None,
    ) -> SolverContext:
        start_time = time.time()

        profiling: Dict[str, float] = {}
        perf_start = perf_counter()

        hash_start = perf_counter()
        view_hash = self._calculate_view_hash(solver_view)
        profiling["hash"] = perf_counter() - hash_start

        if view_hash == self._last_view_hash and self._cached_context is not None:
            cached = self._cached_context
            cached.metadata.setdefault("profiling", {}).update(
                {"cache_hit": True, "total": perf_counter() - perf_start}
            )
            return self._cached_context

        bounds_start = perf_counter()
        bounds = self._extract_bounds_from_view(solver_view)
        profiling["bounds"] = perf_counter() - bounds_start

        zones_start = perf_counter()
        frontier_zones, zone_profiling = self._extract_frontier_zones(solver_view, bounds)
        profiling["zones_total"] = perf_counter() - zones_start
        for key, value in zone_profiling.items():
            profiling[f"zones_{key}"] = value

        if self.enable_hint_integration:
            hint_start = perf_counter()
            frontier_zones, hint_profile = self._apply_hint_priorities(frontier_zones, hint_events)
            profiling["hint_integration"] = perf_counter() - hint_start
            profiling.update({f"hint_{k}": v for k, v in hint_profile.items()})

        sum_start = perf_counter()
        total_unknown = int(np.sum(self._unknown_mask(solver_view["values"])))
        total_frontier = int(np.sum(solver_view["frontier_mask"]))
        profiling["summary"] = perf_counter() - sum_start

        context = SolverContext(
            tensor_grid=self.tensor_grid,
            hint_cache=self.hint_cache,
            global_bounds=bounds,
            frontier_zones=frontier_zones,
            total_unknown=total_unknown,
            total_frontier=total_frontier,
            processing_time=time.time() - start_time,
            metadata={
                "view_hash": view_hash,
                "has_scipy": _HAS_SCIPY,
                "zones": len(frontier_zones),
                "profiling": {
                    **profiling,
                    "cache_hit": False,
                    "total": perf_counter() - perf_start,
                },
            },
        )

        self._cached_context = context
        self._last_view_hash = view_hash
        return context

    # ------------------------------------------------------------------ #
    # Extraction & Segmentation
    # ------------------------------------------------------------------ #
    def _extract_frontier_zones(
        self,
        solver_view: Dict[str, Any],
        bounds: GridBounds,
    ) -> Tuple[List[FrontierZone], Dict[str, float]]:
        values = solver_view["values"]
        frontier_mask = solver_view["frontier_mask"].astype(bool)
        origin_x, origin_y = solver_view.get("origin", (bounds[0], bounds[1]))

        unknown_mask = self._unknown_mask(values)
        frontier_unknown = frontier_mask & unknown_mask
        if not np.any(frontier_unknown):
            return [], {"label": 0.0, "build": 0.0}

        label_start = perf_counter()
        labels, count = self._label_components(frontier_unknown)
        label_time = perf_counter() - label_start

        zones: List[FrontierZone] = []
        build_start = perf_counter()

        for label_id in range(1, count + 1):
            ys, xs = np.where(labels == label_id)
            if ys.size == 0:
                continue

            if ys.size < self.min_zone_size or ys.size > self.max_zone_size:
                continue

            unknown_cells: Set[Tuple[int, int]] = set()
            number_cells: Dict[Tuple[int, int], int] = {}

            for local_y, local_x in zip(ys, xs):
                gx = origin_x + local_x
                gy = origin_y + local_y
                unknown_cells.add((gx, gy))

                for ny in range(local_y - 1, local_y + 2):
                    for nx in range(local_x - 1, local_x + 2):
                        if ny < 0 or nx < 0 or ny >= values.shape[0] or nx >= values.shape[1]:
                            continue
                        if ny == local_y and nx == local_x:
                            continue
                        code = int(values[ny, nx])
                        if code in NUMBER_CODE_MAP:
                            ngx = origin_x + nx
                            ngy = origin_y + ny
                            number_cells[(ngx, ngy)] = NUMBER_CODE_MAP[code]

            if not unknown_cells or not number_cells:
                continue

            zone_bounds = self._compute_bounds(unknown_cells, number_cells)
            complexity = self._calculate_zone_complexity(unknown_cells, number_cells)
            zone_type = self._classify_zone_type(unknown_cells, number_cells, complexity)
            priority = self._calculate_zone_priority(unknown_cells, number_cells, complexity)

            zone = FrontierZone(
                zone_id=f"zone_{label_id}_{int(time.time()*1000)}",
                zone_type=zone_type,
                bounds=zone_bounds,
                unknown_cells=unknown_cells,
                number_cells=number_cells,
                safe_cells=set(),
                mine_cells=set(),
                complexity_score=complexity,
                priority=priority,
                metadata={
                    "size": len(unknown_cells),
                    "numbers": len(number_cells),
                },
            )
            zones.append(zone)

        build_time = perf_counter() - build_start

        return zones, {"label": label_time, "build": build_time}

    # ------------------------------------------------------------------ #
    # Hint integration
    # ------------------------------------------------------------------ #
    def _apply_hint_priorities(
        self,
        zones: List[FrontierZone],
        hint_events: Optional[Sequence[HintEvent]],
    ) -> Tuple[List[FrontierZone], Dict[str, float]]:
        if not hint_events:
            return zones, {"events": 0}

        dirty_bounds = [
            event.payload.get("bounds")
            for event in hint_events
            if event.kind == "dirty_set" and event.payload.get("bounds")
        ]

        if not dirty_bounds:
            return zones, {"events": len(hint_events)}

        def overlap(zone_bounds: GridBounds, hint_bounds: GridBounds) -> bool:
            zx1, zy1, zx2, zy2 = zone_bounds
            hx1, hy1, hx2, hy2 = hint_bounds
            return not (zx2 < hx1 or hx2 < zx1 or zy2 < hy1 or hy2 < zy1)

        hits = 0
        for zone in zones:
            boost = sum(1 for b in dirty_bounds if overlap(zone.bounds, b))
            if boost:
                zone.priority = min(1.0, zone.priority + 0.1 * boost)
                zone.metadata["dirty_hits"] = boost
                hits += 1

        zones.sort(key=lambda z: z.priority, reverse=True)
        return zones, {"events": len(hint_events), "zones_hit": hits}

    # ------------------------------------------------------------------ #
    # Utilitaires
    # ------------------------------------------------------------------ #
    def _unknown_mask(self, values: np.ndarray) -> np.ndarray:
        return values == UNKNOWN_CODE

    @staticmethod
    def _compute_bounds(
        unknown: Set[Tuple[int, int]],
        numbers: Dict[Tuple[int, int], int],
    ) -> GridBounds:
        all_coords = list(unknown) + list(numbers.keys())
        xs = [x for x, _ in all_coords]
        ys = [y for _, y in all_coords]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _calculate_zone_complexity(
        unknown: Set[Tuple[int, int]],
        numbers: Dict[Tuple[int, int], int],
    ) -> float:
        if not unknown:
            return 0.0
        ratio = len(numbers) / len(unknown)
        avg_number = np.mean(list(numbers.values())) if numbers else 0.0
        complexity = 0.4 * min(ratio, 1.0) + 0.4 * (avg_number / 8.0) + 0.2 * min(len(unknown) / 32.0, 1.0)
        return float(min(1.0, complexity))

    @staticmethod
    def _classify_zone_type(
        unknown: Set[Tuple[int, int]],
        numbers: Dict[Tuple[int, int], int],
        complexity: float,
    ) -> FrontierZoneType:
        if not unknown:
            return FrontierZoneType.TRIVIAL
        if complexity < 0.35:
            return FrontierZoneType.CSP_SOLVABLE
        if complexity < 0.7:
            return FrontierZoneType.MONTE_CARLO
        return FrontierZoneType.NEURAL_ASSIST

    @staticmethod
    def _calculate_zone_priority(
        unknown: Set[Tuple[int, int]],
        numbers: Dict[Tuple[int, int], int],
        complexity: float,
    ) -> float:
        if not unknown:
            return 0.0
        size_factor = max(0.0, 1.0 - abs(len(unknown) - 12) / 24.0)
        density = len(numbers) / len(unknown)
        density_factor = min(density / 2.0, 1.0)
        priority = 0.4 * size_factor + 0.4 * (1.0 - complexity) + 0.2 * density_factor
        return float(min(1.0, max(0.1, priority)))

    def _calculate_view_hash(self, solver_view: Dict[str, Any]) -> int:
        values = solver_view["values"]
        frontier_mask = solver_view["frontier_mask"]
        origin = solver_view.get("origin", (0, 0))
        stats = (
            values.shape,
            int(np.sum(values == UNKNOWN_CODE)),
            int(np.sum(frontier_mask)),
            origin,
        )
        return hash(stats)

    def _label_components(self, mask: np.ndarray) -> Tuple[np.ndarray, int]:
        if _HAS_SCIPY and ndimage is not None:
            labeled, count = ndimage.label(mask)
            return labeled.astype(np.int32), int(count)

        # Fallback sans SciPy : BFS 8-connecté
        labeled = np.zeros_like(mask, dtype=np.int32)
        current = 0
        height, width = mask.shape

        for y in range(height):
            for x in range(width):
                if not mask[y, x] or labeled[y, x] != 0:
                    continue
                current += 1
                labeled[y, x] = current
                queue: deque[Tuple[int, int]] = deque([(y, x)])
                while queue:
                    cy, cx = queue.popleft()
                    for ny in range(cy - 1, cy + 2):
                        for nx in range(cx - 1, cx + 2):
                            if ny < 0 or nx < 0 or ny >= height or nx >= width:
                                continue
                            if not mask[ny, nx] or labeled[ny, nx] != 0:
                                continue
                            labeled[ny, nx] = current
                            queue.append((ny, nx))

        return labeled, current

    @staticmethod
    def _extract_bounds_from_view(solver_view: Dict[str, Any]) -> GridBounds:
        if "bounds" in solver_view:
            bx1, by1, bx2, by2 = solver_view["bounds"]
            return int(bx1), int(by1), int(bx2), int(by2)
        origin_x, origin_y = solver_view.get("origin", (0, 0))
        height, width = solver_view["values"].shape
        return (
            origin_x,
            origin_y,
            origin_x + width - 1,
            origin_y + height - 1,
        )
