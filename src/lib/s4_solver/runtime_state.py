"""Snapshot mutable interne au solver avec dirty flags par cellule.

Module dédié à la gestion de l'état interne du solver pendant l'exécution.
Permet aux sous-modules de travailler sur un snapshot partagé et cohérent,
sans passer par storage.apply_upsert() intermédiaire.
"""

from __future__ import annotations

from typing import Dict, Set
from src.lib.s3_storage.types import Coord, GridCell, StorageUpsert

# StorageSnapshot est un alias pour Dict[Coord, GridCell]
StorageSnapshot = Dict[Coord, GridCell]


class SolverRuntime:
    """Snapshot mutable interne au solver avec tracking des cellules modifiées."""

    def __init__(self, initial_snapshot: StorageSnapshot):
        """Initialise le runtime avec un snapshot initial.
        
        Args:
            initial_snapshot: Snapshot initial du storage (copié en interne)
        """
        # Snapshot interne mutable
        self.snapshot: Dict[Coord, GridCell] = dict(initial_snapshot)
        
        # Dirty flags : coordonnées des cellules modifiées depuis le dernier clear
        self.dirty: Set[Coord] = set()
        
        # Snapshot initial pour comparaison finale
        self._initial_snapshot = initial_snapshot

    def apply_upsert(self, upsert: StorageUpsert) -> None:
        """Applique un StorageUpsert au snapshot interne et marque les dirty flags.
        
        Args:
            upsert: StorageUpsert à appliquer
        """
        if not upsert.cells:
            return
        
        for coord, new_cell in upsert.cells.items():
            old_cell = self.snapshot.get(coord)
            
            # Vérifier si la cellule a vraiment changé
            if old_cell != new_cell:
                self.snapshot[coord] = new_cell
                self.dirty.add(coord)
            elif coord not in self.snapshot:
                # Nouvelle cellule
                self.snapshot[coord] = new_cell
                self.dirty.add(coord)

    def clear_dirty(self) -> None:
        """Réinitialise les dirty flags après une passe."""
        self.dirty.clear()

    def get_snapshot(self) -> StorageSnapshot:
        """Retourne une copie du snapshot interne courant (pour lecture seule)."""
        return dict(self.snapshot)

    def get_dirty_coords(self) -> Set[Coord]:
        """Retourne l'ensemble des coordonnées modifiées."""
        return set(self.dirty)

    def get_changed_cells(self) -> Dict[Coord, GridCell]:
        """Retourne uniquement les cellules modifiées (dirty=True)."""
        return {coord: self.snapshot[coord] for coord in self.dirty}

    def has_changes(self) -> bool:
        """Vérifie s'il y a des cellules modifiées."""
        return len(self.dirty) > 0

    def get_final_upsert(self) -> StorageUpsert:
        """Construit un StorageUpsert final contenant toutes les cellules modifiées.
        
        Compare le snapshot interne au snapshot initial et retourne les différences.
        """
        changed_cells: Dict[Coord, GridCell] = {}
        
        for coord, cell in self.snapshot.items():
            initial_cell = self._initial_snapshot.get(coord)
            if initial_cell != cell:
                changed_cells[coord] = cell
        
        return StorageUpsert(
            cells=changed_cells,
            to_visualize=set(),
        )
