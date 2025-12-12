from __future__ import annotations

from typing import Set, Tuple

Coord = Tuple[int, int]


class SetManager:
    """Manages three sets: revealed, unresolved, frontier."""

    def __init__(self) -> None:
        self._revealed_set: Set[Coord] = set()
        self._unresolved_set: Set[Coord] = set()
        self._frontier_set: Set[Coord] = set()

    def apply_set_updates(
        self,
        *,
        revealed_add: Set[Coord],
        unresolved_add: Set[Coord],
        unresolved_remove: Set[Coord],
        frontier_add: Set[Coord],
        frontier_remove: Set[Coord],
    ) -> None:
        """Apply incremental updates to all three sets."""
        self._revealed_set.update(revealed_add)
        
        self._unresolved_set.update(unresolved_add)
        self._unresolved_set.difference_update(unresolved_remove)
        
        self._frontier_set.update(frontier_add)
        self._frontier_set.difference_update(frontier_remove)

    def get_revealed(self) -> Set[Coord]:
        """Return revealed coordinates."""
        return set(self._revealed_set)

    def get_unresolved(self) -> Set[Coord]:
        """Return unresolved coordinates."""
        return set(self._unresolved_set)

    def get_frontier(self) -> Set[Coord]:
        """Return frontier coordinates."""
        return set(self._frontier_set)

    def iter_frontier_in_bounds(self, bounds: Tuple[int, int, int, int]) -> Set[Coord]:
        """Iterate frontier coordinates within bounds."""
        x_min, y_min, x_max, y_max = bounds
        result = set()
        for coord in self._frontier_set:
            x, y = coord
            if x_min <= x <= x_max and y_min <= y <= y_max:
                result.add(coord)
        return result
