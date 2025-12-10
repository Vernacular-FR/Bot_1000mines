#!/usr/bin/env python3
"""
TensorGrid
==========

Backbone mémoire partagé entre Vision (S2), Tensor Core (S3) et Solver (S4).
Le module fournit :
    - un stockage dense (valeurs, confiance, âge, frontier mask, dirty mask)
    - des API d'écriture incrémentale `update_region` / `mark_dirty`
    - une vue read-only pour le solver `get_solver_view`
    - des statistiques pour Pathfinder / instrumentation
    - un système simple de publication des dirty sets
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .types import CellType

GridBounds = Tuple[int, int, int, int]  # (x_min, y_min, x_max, y_max)


DEFAULT_UNKNOWN_CODE = -1  # Valeur par défaut quand aucune info Vision n'est disponible


@dataclass
class DirtySet:
    bounds: GridBounds
    reason: str = "update"
    tick_id: Optional[int] = None


class TensorGrid:
    """
    Stockage dense des cellules de la grille.

    Implémentation actuelle : arrays NumPy redimensionnés dynamiquement.
    Une fenêtre glissante sera introduite plus tard pour contenir l'empreinte mémoire.
    """

    def __init__(
        self,
        width: int = 256,
        height: int = 256,
        padding: int = 64,
    ):
        self.padding = padding
        self.shape = (height, width)

        self.values = np.full(self.shape, DEFAULT_UNKNOWN_CODE, dtype=np.int8)
        self.confidence = np.zeros(self.shape, dtype=np.float32)
        self.age = np.zeros(self.shape, dtype=np.uint32)
        self.frontier_mask = np.zeros(self.shape, dtype=bool)
        self.dirty_mask = np.zeros(self.shape, dtype=bool)

        self._pending_dirty_sets: List[DirtySet] = []
        self._last_solver_view: Optional[Dict[str, np.ndarray]] = None
        self._tick_counter = 0
        self.offset_x = 0
        self.offset_y = 0

    # ------------------------------------------------------------------ #
    # Dimensionnement
    # ------------------------------------------------------------------ #
    def _ensure_bounds(self, bounds: GridBounds) -> Tuple[slice, slice]:
        x_min, y_min, x_max, y_max = bounds
        if x_min > x_max or y_min > y_max:
            raise ValueError(f"Bounds invalides: {bounds}")

        if x_min + self.offset_x < 0 or y_min + self.offset_y < 0:
            shift_x = max(0, -(x_min + self.offset_x))
            shift_y = max(0, -(y_min + self.offset_y))
            self._shift_origin(shift_x, shift_y)

        adj_x_min = x_min + self.offset_x
        adj_y_min = y_min + self.offset_y
        adj_x_max = x_max + self.offset_x
        adj_y_max = y_max + self.offset_y

        need_width = max(adj_x_max + 1, self.shape[1])
        need_height = max(adj_y_max + 1, self.shape[0])

        if need_width > self.shape[1] or need_height > self.shape[0]:
            self._resize(
                width=max(need_width + self.padding, self.shape[1]),
                height=max(need_height + self.padding, self.shape[0]),
            )

        x_slice = slice(adj_x_min, adj_x_max + 1)
        y_slice = slice(adj_y_min, adj_y_max + 1)
        return y_slice, x_slice  # NumPy utilise [row, col] -> [y, x]

    def _resize(self, width: int, height: int) -> None:
        new_shape = (height, width)
        self.values = self._resize_array(self.values, new_shape, DEFAULT_UNKNOWN_CODE)
        self.confidence = self._resize_array(self.confidence, new_shape, 0.0)
        self.age = self._resize_array(self.age, new_shape, 0)
        self.frontier_mask = self._resize_array(self.frontier_mask, new_shape, False)
        self.dirty_mask = self._resize_array(self.dirty_mask, new_shape, False)
        self.shape = new_shape

    @staticmethod
    def _resize_array(array: np.ndarray, new_shape: Tuple[int, int], fill_value) -> np.ndarray:
        result = np.full(new_shape, fill_value, dtype=array.dtype)
        h = min(array.shape[0], new_shape[0])
        w = min(array.shape[1], new_shape[1])
        result[:h, :w] = array[:h, :w]
        return result

    def _shift_origin(self, shift_x: int, shift_y: int) -> None:
        if shift_x == 0 and shift_y == 0:
            return

        new_shape = (self.shape[0] + shift_y, self.shape[1] + shift_x)
        self.values = self._shift_array(self.values, new_shape, shift_x, shift_y, DEFAULT_UNKNOWN_CODE)
        self.confidence = self._shift_array(self.confidence, new_shape, shift_x, shift_y, 0.0)
        self.age = self._shift_array(self.age, new_shape, shift_x, shift_y, 0)
        self.frontier_mask = self._shift_array(self.frontier_mask, new_shape, shift_x, shift_y, False)
        self.dirty_mask = self._shift_array(self.dirty_mask, new_shape, shift_x, shift_y, False)

        self.shape = new_shape
        self.offset_x += shift_x
        self.offset_y += shift_y

    @staticmethod
    def _shift_array(array: np.ndarray, new_shape: Tuple[int, int], shift_x: int, shift_y: int, fill_value):
        result = np.full(new_shape, fill_value, dtype=array.dtype)
        result[shift_y:shift_y + array.shape[0], shift_x:shift_x + array.shape[1]] = array
        return result

    # ------------------------------------------------------------------ #
    # Mise à jour & publication des dirty sets
    # ------------------------------------------------------------------ #
    def update_region(
        self,
        bounds: GridBounds,
        codes: np.ndarray,
        confidences: np.ndarray,
        *,
        frontier_mask: Optional[np.ndarray] = None,
        dirty_mask: Optional[np.ndarray] = None,
        age_increment: int = 1,
        tick_id: Optional[int] = None,
    ) -> None:
        """
        Applique les mises à jour vision sur une région.
        Les arrays NumPy passés en argument doivent correspondre à la taille de `bounds`.
        """

        region_slice = self._ensure_bounds(bounds)
        region_shape = (
            region_slice[0].stop - region_slice[0].start,
            region_slice[1].stop - region_slice[1].start,
        )

        def _ensure_array(data: np.ndarray, name: str) -> np.ndarray:
            arr = np.asarray(data)
            if arr.shape != region_shape:
                raise ValueError(f"{name} shape mismatch {arr.shape} != {region_shape}")
            return arr

        codes = _ensure_array(codes, "codes").astype(np.int8, copy=False)
        confidences = _ensure_array(confidences, "confidences").astype(np.float32, copy=False)

        self.values[region_slice] = codes
        self.confidence[region_slice] = confidences

        self.age[region_slice] += age_increment

        if frontier_mask is not None:
            frontier = _ensure_array(frontier_mask, "frontier_mask").astype(bool, copy=False)
            self.frontier_mask[region_slice] = frontier

        if dirty_mask is not None:
            dirty = _ensure_array(dirty_mask, "dirty_mask").astype(bool, copy=False)
            self.dirty_mask[region_slice] = dirty
        else:
            # fallback : toutes les cases du patch deviennent dirty
            self.dirty_mask[region_slice] = True

        self._pending_dirty_sets.append(DirtySet(bounds=bounds, tick_id=tick_id))
        self._tick_counter += 1

    def mark_dirty(self, bounds: GridBounds, reason: str = "manual", tick_id: Optional[int] = None) -> None:
        region_slice = self._ensure_bounds(bounds)
        self.dirty_mask[region_slice] = True
        self._pending_dirty_sets.append(DirtySet(bounds=bounds, reason=reason, tick_id=tick_id))

    def publish_dirty_sets(self) -> List[DirtySet]:
        dirty_sets = self._pending_dirty_sets[:]
        self._pending_dirty_sets.clear()
        return dirty_sets

    # ------------------------------------------------------------------ #
    # Vues & statistiques
    # ------------------------------------------------------------------ #
    def get_solver_view(self, bounds: Optional[GridBounds] = None) -> Dict[str, np.ndarray]:
        """
        Retourne une vue (copie) des tenseurs pour le solver.
        """
        if bounds is None:
            view = {
                "values": self.values.copy(),
                "confidence": self.confidence.copy(),
                "age": self.age.copy(),
                "frontier_mask": self.frontier_mask.copy(),
                "dirty_mask": self.dirty_mask.copy(),
            }
        else:
            region_slice = self._ensure_bounds(bounds)
            view = {
                "values": self.values[region_slice].copy(),
                "confidence": self.confidence[region_slice].copy(),
                "age": self.age[region_slice].copy(),
                "frontier_mask": self.frontier_mask[region_slice].copy(),
                "dirty_mask": self.dirty_mask[region_slice].copy(),
            }

        self._last_solver_view = view
        return view

    def stats(self) -> Dict[str, float]:
        known_mask = self.values != DEFAULT_UNKNOWN_CODE
        total_cells = self.values.size
        known_ratio = float(known_mask.sum()) / float(total_cells) if total_cells else 0.0
        frontier_cells = int(self.frontier_mask.sum())
        dirty_cells = int(self.dirty_mask.sum())

        return {
            "total_cells": total_cells,
            "known_ratio": known_ratio,
            "frontier_cells": frontier_cells,
            "dirty_cells": dirty_cells,
            "tick_counter": self._tick_counter,
        }

    def snapshot(self) -> Dict[str, np.ndarray]:
        """
        Utilisé par TraceRecorder pour sérialiser l'état.
        """
        return {
            "values": self.values.copy(),
            "confidence": self.confidence.copy(),
            "age": self.age.copy(),
            "frontier_mask": self.frontier_mask.copy(),
            "dirty_mask": self.dirty_mask.copy(),
        }

    # ------------------------------------------------------------------ #
    # Utilitaires
    # ------------------------------------------------------------------ #
    @staticmethod
    def encode_cell_type(cell_type: CellType) -> int:
        """
        Conversion simple CellType -> int8
        (permet d'étendre facilement les encodages plus tard).
        """
        mapping = {
            CellType.EMPTY: 0,
            CellType.UNREVEALED: 1,
            CellType.FLAG: 2,
            CellType.MINE: 3,
            CellType.NUMBER_1: 11,
            CellType.NUMBER_2: 12,
            CellType.NUMBER_3: 13,
            CellType.NUMBER_4: 14,
            CellType.NUMBER_5: 15,
            CellType.NUMBER_6: 16,
            CellType.NUMBER_7: 17,
            CellType.NUMBER_8: 18,
            CellType.UNKNOWN: DEFAULT_UNKNOWN_CODE,
        }
        return mapping.get(cell_type, DEFAULT_UNKNOWN_CODE)

    @staticmethod
    def decode_cell_type(code: int) -> CellType:
        inverse_map = {
            0: CellType.EMPTY,
            1: CellType.UNREVEALED,
            2: CellType.FLAG,
            3: CellType.MINE,
            11: CellType.NUMBER_1,
            12: CellType.NUMBER_2,
            13: CellType.NUMBER_3,
            14: CellType.NUMBER_4,
            15: CellType.NUMBER_5,
            16: CellType.NUMBER_6,
            17: CellType.NUMBER_7,
            18: CellType.NUMBER_8,
        }
        return inverse_map.get(code, CellType.UNKNOWN)

    def export_symbol_distribution(self) -> Dict[str, int]:
        unique, counts = np.unique(self.values, return_counts=True)
        result: Dict[str, int] = {}
        for code, count in zip(unique.tolist(), counts.tolist()):
            cell_type = self.decode_cell_type(code)
            result[cell_type.value] = result.get(cell_type.value, 0) + count
        return result


class TensorGridView:
    """
    Adaptateur léger pour exposer une fenêtre (bounds) d'un TensorGrid
    sans recopier systématiquement les données côté solver.
    """

    def __init__(self, tensor_grid: TensorGrid, bounds: Optional[GridBounds] = None):
        self.tensor_grid = tensor_grid
        self.bounds = bounds

    def as_dict(self) -> Dict[str, np.ndarray]:
        return self.tensor_grid.get_solver_view(self.bounds)

    def iter_cells(self) -> Iterable[Tuple[int, int, CellType, float]]:
        view = self.as_dict()
        values = view["values"]
        confidence = view["confidence"]
        h, w = values.shape
        x_offset = 0
        y_offset = 0
        if self.bounds:
            x_offset, y_offset = self.bounds[0], self.bounds[1]

        for y in range(h):
            for x in range(w):
                yield (
                    x + x_offset,
                    y + y_offset,
                    TensorGrid.decode_cell_type(int(values[y, x])),
                    float(confidence[y, x]),
                )
