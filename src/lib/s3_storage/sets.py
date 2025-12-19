"""Gestion des ensembles de cellules."""

from __future__ import annotations

from typing import Set, Tuple

Coord = Tuple[int, int]


class SetManager:
    """Gère les ensembles : revealed, known, active, frontier, to_visualize."""

    def __init__(self) -> None:
        self._revealed_set: Set[Coord] = set()
        self._known_set: Set[Coord] = set()
        self._active_set: Set[Coord] = set()
        self._frontier_set: Set[Coord] = set()
        self._to_visualize: Set[Coord] = set()

    def apply_set_updates(
        self,
        *,
        revealed_add: Set[Coord],
        active_add: Set[Coord],
        active_remove: Set[Coord],
        frontier_add: Set[Coord],
        frontier_remove: Set[Coord],
        to_visualize: Set[Coord],
    ) -> None:
        """Applique les mises à jour incrémentales aux ensembles."""
        self._revealed_set.update(revealed_add)
        self._active_set.update(active_add)
        self._active_set.difference_update(active_remove)
        self._active_set.difference_update(to_visualize)
        self._frontier_set.update(frontier_add)
        self._frontier_set.difference_update(frontier_remove)
        self._frontier_set.difference_update(self._revealed_set)
        self._to_visualize.update(to_visualize)

    def get_revealed(self) -> Set[Coord]:
        return set(self._revealed_set)

    def get_active(self) -> Set[Coord]:
        return set(self._active_set)

    def get_frontier(self) -> Set[Coord]:
        return set(self._frontier_set)

    def get_to_visualize(self) -> Set[Coord]:
        return set(self._to_visualize)

    def get_known(self) -> Set[Coord]:
        return set(self._known_set)

    def remove_from_state_sets(self, coord: Coord) -> None:
        """Retire une coord des ensembles d'état (sauf known)."""
        self._revealed_set.discard(coord)
        self._active_set.discard(coord)
        self._frontier_set.discard(coord)

    def add_to_known(self, coord: Coord) -> None:
        self._known_set.add(coord)

    def add_to_revealed(self, coord: Coord) -> None:
        self._revealed_set.add(coord)

    def add_to_active(self, coord: Coord) -> None:
        self._active_set.add(coord)

    def add_to_frontier(self, coord: Coord) -> None:
        self._frontier_set.add(coord)
