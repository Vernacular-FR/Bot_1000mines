"""Point d'entrée principal pour l'analyse vision."""


from __future__ import annotations

import io
import time
from src.config import CELL_SIZE, CELL_BORDER
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image

from src.lib.s0_coordinates.types import Coord, GridBounds
from .s2_types import VisionInput, VisionResult, CellMatch
from .s2a_template_matcher import CenterTemplateMatcher, MatchResult


_default_matcher: Optional[CenterTemplateMatcher] = None


def _get_matcher() -> CenterTemplateMatcher:
    global _default_matcher
    if _default_matcher is None:
        _default_matcher = CenterTemplateMatcher()
    return _default_matcher


def analyze(input: VisionInput) -> VisionResult:
    """Analyse les images capturées et retourne les cellules reconnues."""
    start_time = time.time()
    matcher = _get_matcher()
    
    matches: List[CellMatch] = []
    errors: List[str] = []
    
    for canvas_id, image_bytes in input.images.items():
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            
            # Utiliser les bounds pour calculer la taille de la grille si disponibles
            if input.bounds:
                cols = input.bounds.max_col - input.bounds.min_col + 1
                rows = input.bounds.max_row - input.bounds.min_row + 1
                print(f"[VISION] Utilisation des bounds pour la taille: {cols}x{rows}")
                print(f"[VISION] Image dimensions: {image.width}x{image.height}, cell_size={input.cell_size}")
                print(f"[VISION] Expected size based on image: {image.width//input.cell_size}x{image.height//input.cell_size}")
            else:
                # Calculer la taille de grille basée sur l'image
                cols = image.width // input.cell_size
                rows = image.height // input.cell_size
                print(f"[VISION] Utilisation des dimensions image: {cols}x{rows}")
            
            # Classification de la grille
            grid_results = matcher.classify_grid(
                image=image,
                grid_top_left=(0, 0),
                grid_size=(cols, rows),
                stride=CELL_SIZE + CELL_BORDER,
                known_set=input.known_set,
                bounds_offset=(input.bounds.min_col, input.bounds.min_row) if input.bounds else None,
            )
            
            # Convertir les résultats en CellMatch
            for (row, col), result in grid_results.items():
                abs_row = (input.bounds.min_row if input.bounds else 0) + row
                abs_col = (input.bounds.min_col if input.bounds else 0) + col
                
                matches.append(CellMatch(
                    coord=Coord(row=abs_row, col=abs_col),
                    symbol=result.symbol,
                    confidence=result.confidence,
                    distance=result.distance,
                    threshold=result.threshold,
                ))
                
        except Exception as e:
            errors.append(f"Erreur canvas {canvas_id}: {e}")
    
    return VisionResult(
        matches=matches,
        timestamp=time.time(),
        errors=errors,
        metadata={
            "duration": time.time() - start_time,
            "canvas_count": len(input.images),
        },
    )


def analyze_image(
    image: Image.Image,
    bounds: GridBounds,
    cell_size: int = 24,
    known_set: Optional[Set[Tuple[int, int]]] = None,
) -> VisionResult:
    """Analyse une image PIL directement."""
    matcher = _get_matcher()
    start_time = time.time()
    
    cols = image.width // cell_size
    rows = image.height // cell_size
    
    grid_results = matcher.classify_grid(
        image=image,
        grid_top_left=(0, 0),
        grid_size=(cols, rows),
        stride=CELL_SIZE + CELL_BORDER,
        known_set=known_set,
        bounds_offset=(bounds.min_col, bounds.min_row),
    )
    
    matches = [
        CellMatch(
            coord=Coord(row=bounds.min_row + row, col=bounds.min_col + col),
            symbol=result.symbol,
            confidence=result.confidence,
            distance=result.distance,
            threshold=result.threshold,
        )
        for (row, col), result in grid_results.items()
    ]
    
    return VisionResult(
        matches=matches,
        timestamp=time.time(),
        metadata={"duration": time.time() - start_time},
    )
