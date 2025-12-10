#!/usr/bin/env python3
"""
HintCache
==========

File d'évènements léger utilisée pour synchroniser Vision/Tensor/Solver.
Chaque entrée décrit soit :
    - un dirty set (zone à rescanner / résoudre)
    - un composant solver prioritaire
    - un message libre (debug, instrumentation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional


@dataclass(order=True)
class HintEvent:
    priority: int
    kind: str = field(compare=False)
    payload: Dict[str, object] = field(compare=False)
    tick_id: Optional[int] = field(default=None, compare=False)


class HintCache:
    """File prioritaire thread-safe pour publier/consommer les hints."""

    def __init__(self):
        self._events: List[HintEvent] = []
        self._lock = Lock()
        self._counter = 0

    # ------------------------------------------------------------------ #
    # Publication
    # ------------------------------------------------------------------ #
    def publish(self, kind: str, payload: Dict[str, object], *, priority: int = 0, tick_id: Optional[int] = None) -> None:
        event = HintEvent(priority=priority, kind=kind, payload=payload, tick_id=tick_id)
        with self._lock:
            self._events.append(event)
            self._events.sort(reverse=True)  # priorité plus élevée en premier
            self._counter += 1

    def publish_dirty_set(self, bounds, *, reason: str = "update", priority: int = 0, tick_id: Optional[int] = None) -> None:
        self.publish(
            kind="dirty_set",
            payload={"bounds": bounds, "reason": reason},
            priority=priority,
            tick_id=tick_id,
        )

    def publish_solver_request(self, component_id: str, cells: List[tuple], *, priority: int = 0, tick_id: Optional[int] = None) -> None:
        self.publish(
            kind="solver_request",
            payload={"component_id": component_id, "cells": cells},
            priority=priority,
            tick_id=tick_id,
        )

    def publish_info(self, message: str, *, priority: int = -1, tick_id: Optional[int] = None) -> None:
        self.publish(kind="info", payload={"message": message}, priority=priority, tick_id=tick_id)

    # ------------------------------------------------------------------ #
    # Consommation
    # ------------------------------------------------------------------ #
    def fetch(self, max_items: Optional[int] = None) -> List[HintEvent]:
        with self._lock:
            if max_items is None or max_items >= len(self._events):
                items = self._events[:]
                self._events.clear()
            else:
                items = self._events[:max_items]
                self._events = self._events[max_items:]
        return items

    def peek(self) -> List[HintEvent]:
        with self._lock:
            return self._events[:]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, int]:
        with self._lock:
            kind_counts: Dict[str, int] = {}
            for event in self._events:
                kind_counts[event.kind] = kind_counts.get(event.kind, 0) + 1
            return {
                "pending_events": len(self._events),
                "published_events": self._counter,
                **{f"kind_{k}": v for k, v in kind_counts.items()},
            }
