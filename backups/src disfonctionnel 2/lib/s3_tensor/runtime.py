#!/usr/bin/env python3
"""
Gestion du runtime Tensor (TensorGrid + HintCache + TraceRecorder).
Permet de partager un même runtime entre S2 et S4 pour une partie donnée.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional

from .tensor_grid import TensorGrid
from .hint_cache import HintCache
from .trace_recorder import TraceRecorder


@dataclass
class TensorRuntime:
    base_path: str
    tensor_grid: TensorGrid
    hint_cache: HintCache
    trace_recorder: TraceRecorder
    tick_counter: int = 0

    def next_tick(self) -> int:
        self.tick_counter += 1
        return self.tick_counter


_RUNTIMES: Dict[str, TensorRuntime] = {}


def _paths_key(paths: Dict[str, str]) -> str:
    grid_db_path = paths.get("grid_db")
    if not grid_db_path:
        raise ValueError("paths['grid_db'] est requis pour initialiser TensorRuntime")
    return os.path.dirname(os.path.abspath(grid_db_path))


def ensure_tensor_runtime(paths: Dict[str, str]) -> TensorRuntime:
    """
    Retourne un runtime partagé pour la partie (identifiée par le dossier grid_db).
    Crée le runtime au besoin (TensorGrid + HintCache + TraceRecorder).
    """
    base_path = _paths_key(paths)
    runtime = _RUNTIMES.get(base_path)
    if runtime is None:
        traces_dir = os.path.join(base_path, "traces")
        os.makedirs(traces_dir, exist_ok=True)
        runtime = TensorRuntime(
            base_path=base_path,
            tensor_grid=TensorGrid(),
            hint_cache=HintCache(),
            trace_recorder=TraceRecorder(traces_dir),
        )
        _RUNTIMES[base_path] = runtime
    return runtime


def reset_tensor_runtime(paths: Dict[str, str]) -> None:
    """
    Utilitaire pour les tests : supprime le runtime associé aux paths donnés.
    """
    base_path = _paths_key(paths)
    _RUNTIMES.pop(base_path, None)
