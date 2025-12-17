from __future__ import annotations

from typing import Set, Tuple

Coord = Tuple[int, int]


class SetManager:
    """Manage four sets: revealed, known, active, frontier, and to_visualize."""

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
        """Apply incremental updates to all sets."""
        self._revealed_set.update(revealed_add)

        self._active_set.update(active_add)
        self._active_set.difference_update(active_remove)
        
        # Purge TO_VISUALIZE from active_set
        self._active_set.difference_update(to_visualize)

        self._frontier_set.update(frontier_add)
        self._frontier_set.difference_update(frontier_remove)

        # Frontière ne doit pas contenir de cases révélées
        self._frontier_set.difference_update(self._revealed_set)

        # TO_VISUALIZE est une pile (coords à recapturer) maintenue en add only par s4
        self._to_visualize.update(to_visualize)

    def get_revealed(self) -> Set[Coord]:
        """Return revealed coordinates."""
        return set(self._revealed_set)

    def get_active(self) -> Set[Coord]:
        """Return active coordinates."""
        return set(self._active_set)

    def get_frontier(self) -> Set[Coord]:
        """Return frontier coordinates."""
        return set(self._frontier_set)

    def get_to_visualize(self) -> Set[Coord]:
        """Return coordinates to re-capture."""
        return set(self._to_visualize)

    def iter_frontier_in_bounds(self, bounds: Tuple[int, int, int, int]) -> Set[Coord]:
        """Iterate frontier coordinates within bounds."""
        x_min, y_min, x_max, y_max = bounds
        result = set()
        for coord in self._frontier_set:
            x, y = coord
            if x_min <= x <= x_max and y_min <= y <= y_max:
                result.add(coord)
        return result

    # Individual set operations for incremental updates
    def remove_from_all_sets(self, coord: Coord) -> None:
        """Remove coord from all sets."""
        self._revealed_set.discard(coord)
        self._known_set.discard(coord)
        self._active_set.discard(coord)
        self._frontier_set.discard(coord)
        # Note: to_visualize is only managed by solver, not removed here

    def add_to_known(self, coord: Coord) -> None:
        """Add coord to known_set."""
        self._known_set.add(coord)

    def add_to_revealed(self, coord: Coord) -> None:
        """Add coord to revealed_set."""
        self._revealed_set.add(coord)

    def add_to_active(self, coord: Coord) -> None:
        """Add coord to active_set."""
        self._active_set.add(coord)

    def add_to_frontier(self, coord: Coord) -> None:
        """Add coord to frontier_set."""
        self._frontier_set.add(coord)

    def get_known(self) -> Set[Coord]:
        """Return known coordinates."""
        return set(self._known_set)
