"""Propagation de contraintes pour la réduction de la frontière."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from src.lib.s3_storage.types import Coord, GridCell, LogicalCellState
from src.lib.s4_solver.types import PropagationResult


class IterativePropagator:
    """Propagation contrainte itérative sur les cellules actives."""

    def __init__(self, cells: Dict[Coord, GridCell]):
        self.cells = cells
        self.neighbors_cache: Dict[Coord, List[Coord]] = {}
        self.simulated_states: Dict[Coord, LogicalCellState] = {}
        self._precompute_neighbors()

    def _precompute_neighbors(self) -> None:
        """Précalcule les voisins pour toutes les cellules."""
        for coord in self.cells:
            self.neighbors_cache[coord] = self._get_neighbors(coord[0], coord[1])

    def _get_neighbors(self, x: int, y: int) -> List[Coord]:
        """Retourne les 8 voisins d'une cellule."""
        neighbors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.cells:
                    neighbors.append((nx, ny))
        return neighbors

    def _get_logical_state(self, coord: Coord) -> LogicalCellState:
        """Retourne l'état logique simulé ou original."""
        if coord in self.simulated_states:
            return self.simulated_states[coord]
        return self.cells[coord].logical_state

    def _get_effective_value(self, coord: Coord) -> int:
        """Calcule la valeur effective: nombre - mines confirmées."""
        cell = self.cells[coord]
        if cell.number_value is None:
            return 0
        confirmed_mines = sum(
            1 for n in self.neighbors_cache[coord]
            if self._get_logical_state(n) == LogicalCellState.CONFIRMED_MINE
        )
        return cell.number_value - confirmed_mines

    def _get_closed_neighbors(self, coord: Coord) -> List[Coord]:
        """Retourne les voisins non révélés."""
        return [
            n for n in self.neighbors_cache[coord]
            if self._get_logical_state(n) == LogicalCellState.UNREVEALED
        ]

    def propagate(self, active_set: Set[Coord]) -> PropagationResult:
        """Propagation contrainte itérative."""
        safe_cells: Set[Coord] = set()
        flag_cells: Set[Coord] = set()
        solved_cells: Set[Coord] = set()
        to_process = set(active_set)
        iteration = 0
        reasoning_parts: List[str] = []

        while to_process and iteration < 100:
            iteration += 1
            current_safe: Set[Coord] = set()
            current_flags: Set[Coord] = set()
            current_solved: Set[Coord] = set()

            for coord in list(to_process):
                cell = self.cells.get(coord)
                if not cell or cell.logical_state != LogicalCellState.OPEN_NUMBER:
                    continue
                if cell.number_value is None:
                    continue

                effective_value = self._get_effective_value(coord)
                closed_neighbors = self._get_closed_neighbors(coord)

                # Règle 1: effective_value == 0 → voisins fermés sont sûrs
                if effective_value == 0 and closed_neighbors:
                    current_safe.update(closed_neighbors)
                    current_solved.add(coord)
                    reasoning_parts.append(f"Safe at {coord}")

                # Règle 2: effective_value == nb fermés → tous sont des mines
                if effective_value == len(closed_neighbors) and effective_value > 0:
                    current_flags.update(closed_neighbors)
                    current_solved.add(coord)
                    reasoning_parts.append(f"Flag at {coord}")

            if not current_safe and not current_flags:
                break

            safe_cells.update(current_safe)
            flag_cells.update(current_flags)
            solved_cells.update(current_solved)

            for coord in current_safe:
                if coord in self.cells:
                    self.simulated_states[coord] = LogicalCellState.EMPTY

            for coord in current_flags:
                if coord in self.cells:
                    self.simulated_states[coord] = LogicalCellState.CONFIRMED_MINE

            to_process.clear()
            for coord in current_safe.union(current_flags):
                if coord in self.neighbors_cache:
                    to_process.update(self.neighbors_cache[coord])

            to_process = {
                c for c in to_process
                if c in self.cells
                and self.cells[c].logical_state == LogicalCellState.OPEN_NUMBER
                and self.cells[c].number_value is not None
                and c not in solved_cells
            }

        return PropagationResult(
            safe_cells=safe_cells,
            flag_cells=flag_cells,
            solved_cells=solved_cells,
            iterations=iteration,
            reasoning="; ".join(reasoning_parts) if reasoning_parts else "No deductions",
        )
