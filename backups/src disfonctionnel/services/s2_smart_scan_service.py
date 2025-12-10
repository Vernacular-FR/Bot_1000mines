#!/usr/bin/env python3
"""
Service SmartScan Phase 3 : consomme CapturePatch, écrit directement dans TensorGrid/HintCache.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time
from time import perf_counter

import numpy as np

from src.lib.s3_tensor.runtime import ensure_tensor_runtime
from src.lib.s3_tensor.tensor_grid import TensorGrid
from src.lib.s3_tensor.types import CellType
from src.lib.s3_tensor.grid_state import GridDB
from src.lib.s3_tensor.mapper import VisionToGameMapper
from src.lib.s2_recognition.template_matching_fixed import (
    FixedTemplateMatcher,
    build_grid_analysis_from_results,
)


@dataclass
class CapturePatch:
    image_path: str
    bounds: Tuple[int, int, int, int]  # (start_x, start_y, end_x, end_y)
    usable_mask: Optional[np.ndarray] = None


try:
    from scipy import ndimage  # type: ignore
    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    ndimage = None
    _HAS_SCIPY = False


class SmartScanService:
    def __init__(
        self,
        paths: Dict[str, str],
        templates_dir: str = "src/lib/s2_recognition/s21_templates/symbols",
        *,
        enable_grid_db: bool = False,
    ):
        self.paths = paths
        self.matcher = FixedTemplateMatcher(templates_dir)
        self.runtime = ensure_tensor_runtime(paths)
        self.enable_grid_db = enable_grid_db
        self.grid_db_path = paths.get("grid_db")
        if not self.grid_db_path:
            raise ValueError("grid_db est requis pour SmartScanService")
        self.grid_db = None
        self.last_summary: Optional[Dict[str, object]] = None
        self.max_dirty_components = 6

        if enable_grid_db:
            self.grid_db = GridDB(self.grid_db_path)

    def process_patches(self, patches: List[CapturePatch]) -> Dict[str, object]:
        tick_id = self.runtime.next_tick()
        updates = 0
        if self.enable_grid_db and self.grid_db:
            self.grid_db.clear_all()
        start_time = time.time()
        total_cells_processed = 0

        patch_profiles = []

        for patch in patches:
            patch_profile = {"bounds": patch.bounds}

            recognize_start = perf_counter()
            results = self.matcher.recognize_grid(patch.image_path, patch.bounds)
            grid_analysis = build_grid_analysis_from_results(patch.image_path, results, patch.bounds)
            patch_profile["recognition_ms"] = (perf_counter() - recognize_start) * 1000.0

            total_cells_processed += grid_analysis.get_cell_count()
            tensor_start = perf_counter()
            updates += self._write_tensor_update(grid_analysis, patch, tick_id)
            patch_profile["tensor_ms"] = (perf_counter() - tensor_start) * 1000.0

            grid_db_start = perf_counter()
            self._write_grid_db(grid_analysis)
            patch_profile["grid_db_ms"] = (perf_counter() - grid_db_start) * 1000.0

            patch_profile["total_ms"] = (
                patch_profile["recognition_ms"]
                + patch_profile["tensor_ms"]
                + patch_profile["grid_db_ms"]
            )
            patch_profiles.append(patch_profile)

        duration = time.time() - start_time
        summary = {}
        symbol_distribution = {}
        if self.enable_grid_db and self.grid_db:
            self.grid_db.flush_to_disk()
            summary = self.grid_db.get_summary()
            symbol_distribution = summary.get("symbol_distribution", {})
            self.last_summary = summary
        grid_stats = self.runtime.tensor_grid.stats()
        known_ratio = grid_stats.get("known_ratio", 0.0)
        frontier_cells = grid_stats.get("frontier_cells", 0)
        dirty_cells = grid_stats.get("dirty_cells", 0)
        avg_patch_ms = (
            sum(p["total_ms"] for p in patch_profiles) / len(patch_profiles)
            if patch_profiles else 0.0
        )
        slowest_patch = max(patch_profiles, key=lambda p: p["total_ms"], default=None)

        metrics = {
            "duration": duration,
            "cells_processed": total_cells_processed,
            "cells_per_second": (total_cells_processed / duration) if duration > 0 else 0.0,
            "known_ratio": known_ratio,
            "frontier_cells": frontier_cells,
            "dirty_cells": dirty_cells,
            "patch_profiles": patch_profiles,
        }
        print(
            "[S2][SmartScan] "
            f"tick={tick_id} patches={len(patches)} "
            f"cells={total_cells_processed} "
            f"{metrics['cells_per_second']:.1f} cells/s "
            f"known_ratio={known_ratio:.3f} "
            f"frontier={frontier_cells} dirty={dirty_cells}"
        )
        if slowest_patch:
            print(
                "[S2][Profiling] "
                f"avg={avg_patch_ms:.1f}ms "
                f"max={slowest_patch['total_ms']:.1f}ms "
                f"recognition={slowest_patch['recognition_ms']:.1f}ms "
                f"tensor={slowest_patch['tensor_ms']:.1f}ms "
                f"grid_db={slowest_patch['grid_db_ms']:.1f}ms "
                f"bounds={slowest_patch['bounds']}"
            )

        dirty_sets = self.runtime.tensor_grid.publish_dirty_sets()
        snapshot = self.runtime.tensor_grid.snapshot()
        self.runtime.trace_recorder.capture(
            tick_id,
            snapshot,
            {
                "stage": "S2_smart_scan",
                "patches": len(patches),
                "cells_processed": total_cells_processed,
                "duration": duration,
                "known_ratio": known_ratio,
                "frontier_cells": frontier_cells,
                "dirty_cells": dirty_cells,
            },
        )

        response = {
            "tick_id": tick_id,
            "updates": updates,
            "dirty_sets": dirty_sets,
            "summary": summary,
            "symbol_distribution": symbol_distribution,
            "metrics": metrics,
        }
        response["db_path"] = self.grid_db_path
        return response

    def _write_tensor_update(self, grid_analysis, patch: CapturePatch, tick_id: int) -> int:
        start_x, start_y, end_x, end_y = patch.bounds
        prev_view = self.runtime.tensor_grid.get_solver_view(patch.bounds)
        prev_codes = prev_view["values"]
        prev_confidences = prev_view["confidence"]
        height, width = prev_codes.shape

        codes = prev_codes.copy()
        confidences = prev_confidences.copy()
        frontier_mask = np.zeros((height, width), dtype=bool)
        dirty_mask = np.zeros((height, width), dtype=bool)

        for (x, y), analysis in grid_analysis.cells.items():
            rel_x = x - start_x
            rel_y = y - start_y
            if 0 <= rel_x < width and 0 <= rel_y < height:
                new_code = TensorGrid.encode_cell_type(analysis.cell_type)
                old_code = int(prev_codes[rel_y, rel_x])
                new_conf = float(analysis.confidence)
                old_conf = float(prev_confidences[rel_y, rel_x])
                if new_code != old_code or abs(new_conf - old_conf) > 1e-6:
                    codes[rel_y, rel_x] = new_code
                    confidences[rel_y, rel_x] = new_conf
                    dirty_mask[rel_y, rel_x] = True

        # Marquer la frontière (cellules inconnues adjacentes à des nombres)
        for (x, y), analysis in grid_analysis.cells.items():
            if analysis.cell_type.value.startswith("number_"):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        rel_x = nx - start_x
                        rel_y = ny - start_y
                        if 0 <= rel_x < width and 0 <= rel_y < height:
                            if codes[rel_y, rel_x] == TensorGrid.encode_cell_type(CellType.UNREVEALED):
                                frontier_mask[rel_y, rel_x] = True
                                if dirty_mask[rel_y, rel_x] is False and dirty_mask.any():
                                    dirty_mask[rel_y, rel_x] = True
                rel_x = x - start_x
                rel_y = y - start_y
                if 0 <= rel_x < width and 0 <= rel_y < height and dirty_mask[rel_y, rel_x]:
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = x + dx, y + dy
                            rel_xn = nx - start_x
                            rel_yn = ny - start_y
                            if 0 <= rel_xn < width and 0 <= rel_yn < height:
                                if codes[rel_yn, rel_xn] == TensorGrid.encode_cell_type(CellType.UNREVEALED):
                                    dirty_mask[rel_yn, rel_xn] = True

        if patch.usable_mask is not None:
            mask = patch.usable_mask.astype(bool)
            confidences[~mask] = 0.0

        if not dirty_mask.any():
            return 0

        updated_cells = int(dirty_mask.sum())

        self.runtime.tensor_grid.update_region(
            patch.bounds,
            codes,
            confidences,
            frontier_mask=frontier_mask,
            dirty_mask=dirty_mask,
            tick_id=tick_id,
        )
        component_bounds = self._extract_dirty_components(patch.bounds, dirty_mask)
        if component_bounds:
            for bounds in component_bounds[: self.max_dirty_components]:
                self.runtime.hint_cache.publish_dirty_set(bounds=bounds, priority=10, tick_id=tick_id)
        else:
            self.runtime.hint_cache.publish_dirty_set(bounds=patch.bounds, priority=5, tick_id=tick_id)
        return updated_cells

    def _extract_dirty_components(
        self,
        patch_bounds: Tuple[int, int, int, int],
        dirty_mask: np.ndarray,
        padding: int = 1,
    ) -> List[Tuple[int, int, int, int]]:
        if not dirty_mask.any():
            return []

        if _HAS_SCIPY and ndimage is not None:
            labeled, num_features = ndimage.label(dirty_mask)
        else:
            labeled, num_features = self._label_components(dirty_mask)

        components: List[Tuple[int, int, int, int]] = []
        start_x, start_y, end_x, end_y = patch_bounds
        for label in range(1, num_features + 1):
            coords = np.argwhere(labeled == label)
            if coords.size == 0:
                continue
            rel_y_min, rel_x_min = coords.min(axis=0)
            rel_y_max, rel_x_max = coords.max(axis=0)
            abs_x_min = max(start_x + rel_x_min - padding, start_x)
            abs_y_min = max(start_y + rel_y_min - padding, start_y)
            abs_x_max = min(start_x + rel_x_max + padding, end_x)
            abs_y_max = min(start_y + rel_y_max + padding, end_y)
            if abs_x_min > abs_x_max or abs_y_min > abs_y_max:
                continue
            components.append((abs_x_min, abs_y_min, abs_x_max, abs_y_max))
        return components

    def _label_components(self, mask: np.ndarray) -> Tuple[np.ndarray, int]:
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

    def _write_grid_db(self, grid_analysis) -> None:
        if not (self.enable_grid_db and self.grid_db):
            return

        for (x, y), analysis in grid_analysis.cells.items():
            symbol = VisionToGameMapper.map_cell_type(analysis.cell_type)
            self.grid_db.add_cell(
                x,
                y,
                {
                    "type": symbol.value,
                    "confidence": float(max(0.0, min(1.0, analysis.confidence))),
                    "state": "TO_PROCESS",
                },
            )
