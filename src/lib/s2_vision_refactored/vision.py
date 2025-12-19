"""Analyse vision : point d'entrée principal."""

import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

from PIL import Image

from src.config import CELL_SIZE, CELL_BORDER
from src.lib.s0_coordinates.types import Coord, GridBounds
from .types import VisionInput, VisionResult, CellMatch, MatchResult
from .matcher import CenterTemplateMatcher


class VisionAnalyzer:
    """Analyseur vision pour la reconnaissance des cellules."""

    def __init__(self, manifest_path: Optional[Path] = None):
        self.matcher = CenterTemplateMatcher(manifest_path)
        self.cell_stride = CELL_SIZE + CELL_BORDER

    def analyze(self, input: VisionInput) -> VisionResult:
        """Analyse une image et retourne les cellules reconnues."""
        timestamp = time.time()
        
        # Convertir les known_coords en set de tuples si nécessaire
        known_set = None
        if input.known_coords:
            known_set = {(c.row, c.col) if isinstance(c, Coord) else c for c in input.known_coords}

        # Calcul de la taille de grille depuis les bounds
        grid_size = (input.bounds.width, input.bounds.height)
        
        # Classification via le matcher
        raw_results = self.matcher.classify_grid(
            image=input.image,
            grid_top_left=(0, 0),  # L'image est déjà croppée aux bounds
            grid_size=grid_size,
            stride=self.cell_stride,
            allowed_symbols=input.allowed_symbols,
            known_set=known_set,
            bounds_offset=(input.bounds.min_col, input.bounds.min_row),
        )

        # Conversion en CellMatch avec coordonnées absolues
        matches: List[CellMatch] = []
        for (row, col), result in raw_results.items():
            abs_coord = Coord(
                row=input.bounds.min_row + row,
                col=input.bounds.min_col + col,
            )
            matches.append(CellMatch.from_match_result(abs_coord, result))

        return VisionResult(
            matches=matches,
            bounds=input.bounds,
            timestamp=timestamp,
            metadata={"cell_stride": self.cell_stride},
        )

    def analyze_image_file(
        self,
        image_path: str | Path,
        bounds: GridBounds,
        known_coords: Optional[Set[Tuple[int, int]]] = None,
    ) -> VisionResult:
        """Analyse une image depuis un fichier."""
        image = Image.open(image_path).convert("RGB")
        input = VisionInput(
            image=image,
            bounds=bounds,
            known_coords=known_coords,
        )
        return self.analyze(input)


# === API fonctionnelle ===

_default_analyzer: Optional[VisionAnalyzer] = None


def _get_analyzer() -> VisionAnalyzer:
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = VisionAnalyzer()
    return _default_analyzer


def analyze(input: VisionInput) -> VisionResult:
    """Analyse une image et retourne les cellules reconnues."""
    return _get_analyzer().analyze(input)


def analyze_grid(
    image: Image.Image,
    bounds: GridBounds,
    known_coords: Optional[Set[Tuple[int, int]]] = None,
) -> VisionResult:
    """Analyse une grille (API simplifiée)."""
    input = VisionInput(
        image=image,
        bounds=bounds,
        known_coords=known_coords,
    )
    return _get_analyzer().analyze(input)
