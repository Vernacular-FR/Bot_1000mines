"""Overlay de segmentation : visualise les composantes et zones du CSP."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from src.lib.s4_solver.s4b_csp_solver.segmentation import Segmentation
from src.config import CELL_SIZE, CELL_BORDER

if TYPE_CHECKING:
    from src.lib.s0_browser.export_context import ExportContext


def render_segmentation_overlay(
    base_image: Image.Image,
    segmentation: Segmentation,
    export_ctx: Optional["ExportContext"] = None,
    bounds: Optional[tuple[int, int, int, int]] = None,
    stride: Optional[int] = None,
) -> Optional[Path]:
    """Dessine un overlay coloré représentant les composantes et zones du CSP.
    
    Args:
        base_image: Image de base (PIL Image)
        segmentation: Objet Segmentation avec composantes et zones
        export_ctx: Contexte d'export (optionnel)
        bounds: Tuple (min_col, min_row, max_col, max_row)
        stride: Pas de grille en pixels
    
    Returns:
        Chemin du fichier PNG généré, ou None si erreur
    """
    if not segmentation or not segmentation.components:
        return None
    
    if not bounds:
        return None
    if not stride:
        stride = CELL_SIZE + CELL_BORDER
    if stride <= 0:
        return None
    
    # Créer l'overlay transparent
    overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Charger la police
    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except OSError:
        font = ImageFont.load_default()
    
    min_col, min_row, _, _ = bounds
    
    # Générer des couleurs pour chaque composante
    colors = {}
    for comp in segmentation.components:
        if comp.id not in colors:
            colors[comp.id] = (
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200),
                180,
            )
    
    # Dessiner les zones colorées par composante
    for comp in segmentation.components:
        color = colors[comp.id]
        for zone in comp.zones:
            # Dessiner les cellules de la zone
            for (x, y) in zone.cells:
                px = (x - min_col) * stride
                py = (y - min_row) * stride
                draw.rectangle(
                    [(px, py), (px + stride, py + stride)],
                    fill=color,
                    outline=(255, 255, 255, 200),
                    width=1,
                )
            
            # Ajouter l'ID de la zone
            if zone.cells:
                x, y = zone.cells[0]
                px = (x - min_col) * stride
                py = (y - min_row) * stride
                draw.text(
                    (px + 2, py + 2),
                    f"Z{zone.id}",
                    fill=(255, 255, 255),
                    font=font,
                )
    
    # Dessiner les contraintes (cellules numérotées) en surbrillance rouge
    constraint_cells = set()
    for zone in segmentation.zones:
        if hasattr(zone, 'constraints'):
            constraint_cells.update(zone.constraints)
    
    for (cx, cy) in constraint_cells:
        px = (cx - min_col) * stride
        py = (cy - min_row) * stride
        draw.rectangle(
            [(px, py), (px + stride, py + stride)],
            outline=(255, 0, 0, 255),
            width=2,
        )
    
    # Composer l'overlay avec l'image de base
    composed = Image.alpha_composite(base_image.convert("RGBA"), overlay)
    
    # Sauvegarder le résultat avec la même nomenclature que les autres overlays
    if export_ctx:
        out_path = export_ctx.solver_overlay_path("s4c2_segmentation")
        out_dir = out_path.parent
    else:
        out_dir = Path("temp") / "games" / "manual" / "s4c2_segmentation"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "segmentation_overlay.png"
    
    composed.save(out_path)
    
    # Sauvegarder les métadonnées JSON
    try:
        json_dir = out_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "bounds": bounds,
            "stride": stride,
            "components": len(segmentation.components),
            "zones": len(segmentation.zones),
            "constraint_cells": len(constraint_cells),
        }
        if export_ctx:
            json_path = export_ctx.json_path("s4c2_segmentation", "segmentation")
        else:
            json_path = json_dir / "segmentation_overlay.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    return out_path
