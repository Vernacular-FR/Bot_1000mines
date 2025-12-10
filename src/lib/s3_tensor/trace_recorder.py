#!/usr/bin/env python3
"""
TraceRecorder
=============

Capture les snapshots TensorGrid + décisions solver pour analyse, replay
et apprentissage. Les snapshots sont stockés sous forme de fichiers NumPy
compressés (.npz) dans temp/games/{game_id}/traces/.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

import numpy as np


class TraceRecorder:
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)
        self.counter = 0

    def capture(self, tick_id: int, tensor_snapshot: Dict[str, np.ndarray], solver_state: Dict[str, object]) -> str:
        """
        Sérialise un tick sous forme .npz et retourne le chemin.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"trace_tick_{tick_id:05d}_{timestamp}.npz"
        save_path = os.path.join(self.base_path, filename)

        np.savez_compressed(save_path, **tensor_snapshot, solver_state=np.array(solver_state, dtype=object))
        self.counter += 1
        return save_path

    def mark_event(self, tick_id: int, message: str) -> str:
        """
        Ajoute un petit fichier texte pour les événements notables (erreur, win, etc.).
        """
        filename = f"event_{tick_id:05d}.txt"
        save_path = os.path.join(self.base_path, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\n{message}\n")
        return save_path

    def stats(self) -> Dict[str, int]:
        return {
            "snapshots_recorded": self.counter,
            "files_in_trace_dir": len(os.listdir(self.base_path)),
        }
