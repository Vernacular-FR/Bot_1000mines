"""
Module d'overlay combiné structuré en 3 couches :
- GridOverlayLayer : dessin de la grille
- InterfaceOverlayLayer : dessin des éléments d'interface
- CombinedOverlayAssembler : assemblage et I/O
"""

import os
from datetime import datetime
from typing import Tuple
from PIL import Image, ImageDraw, ImageFont


class GridOverlayLayer:
    """Responsable du dessin de la grille (CoordinateConverter ou fallback)."""

    @staticmethod
    def draw(draw: ImageDraw.Draw, image_size: Tuple[int, int],
             grid_bounds: Tuple[int, int, int, int], coord_system=None, viewport_mapper=None) -> int:
        """Dessine la grille et renvoie le nombre de lignes tracées."""
        if coord_system is None:
            raise ValueError("GridOverlayLayer requires a CoordinateConverter instance")

        try:
            resolved_bounds = GridOverlayLayer._resolve_bounds(coord_system, viewport_mapper, image_size, grid_bounds)
            to_screen = GridOverlayLayer._build_grid_to_screen(coord_system)

            lines_drawn = GridOverlayLayer._draw_grid_lines(
                draw,
                resolved_bounds['grid_bounds'],
                resolved_bounds['screen_bounds'],
                to_screen
            )
            GridOverlayLayer._draw_axis_labels(
                draw,
                resolved_bounds['grid_bounds'],
                resolved_bounds['screen_bounds'],
                to_screen
            )
            GridOverlayLayer._mark_origin(
                draw,
                resolved_bounds['grid_bounds'],
                resolved_bounds['screen_bounds'],
                to_screen
            )

            x_min, y_min, x_max, y_max = resolved_bounds['grid_bounds']
            print(f"[GRID] Grid drawn: ({x_min},{y_min})->({x_max},{y_max})")
            return lines_drawn

        except Exception as e:
            print(f"[GRID] Error with CoordinateConverter: {e}")
            import traceback
            traceback.print_exc()
            raise

    @staticmethod
    def _resolve_bounds(coord_system, viewport_mapper, image_size, grid_bounds):
        if viewport_mapper:
            viewport_bounds = viewport_mapper.get_viewport_bounds()
            if viewport_bounds:
                resolved_grid = tuple(viewport_bounds['grid_bounds'])
                screen_bounds = tuple(viewport_bounds['screen_bounds'])
            else:
                resolved_grid = grid_bounds
                screen_bounds = (0, 0, image_size[0], image_size[1])
        else:
            resolved_grid = grid_bounds
            screen_bounds = (0, 0, image_size[0], image_size[1])

        return {
            'grid_bounds': resolved_grid,
            'screen_bounds': screen_bounds,
        }

    @staticmethod
    def _build_grid_to_screen(coord_system):
        return coord_system.grid_to_screen

    @staticmethod
    def _draw_grid_lines(draw, grid_bounds, screen_bounds, to_screen):
        x_min, y_min, x_max, y_max = grid_bounds
        screen_left, screen_top, screen_right, screen_bottom = screen_bounds
        lines_drawn = 0

        for boundary_x in range(x_min, x_max + 2):
            try:
                boundary_screen_x, _ = to_screen(boundary_x, y_min)
            except Exception as conv_err:
                print(f"[GRID] vertical boundary error {boundary_x}: {conv_err}")
                continue
            if screen_left - 2 <= boundary_screen_x <= screen_right + 2:
                draw.line([
                    (int(round(boundary_screen_x)), int(round(screen_top))),
                    (int(round(boundary_screen_x)), int(round(screen_bottom)))
                ], fill=(0, 0, 255), width=1)
                lines_drawn += 1

        for boundary_y in range(y_min, y_max + 2):
            try:
                _, boundary_screen_y = to_screen(x_min, boundary_y)
            except Exception as conv_err:
                print(f"[GRID] horizontal boundary error {boundary_y}: {conv_err}")
                continue
            if screen_top - 2 <= boundary_screen_y <= screen_bottom + 2:
                draw.line([
                    (int(round(screen_left)), int(round(boundary_screen_y))),
                    (int(round(screen_right)), int(round(boundary_screen_y)))
                ], fill=(0, 0, 255), width=1)
                lines_drawn += 1

        return lines_drawn

    @staticmethod
    def _draw_axis_labels(draw, grid_bounds, screen_bounds, to_screen):
        x_min, y_min, x_max, y_max = grid_bounds
        screen_left, screen_top, screen_right, screen_bottom = screen_bounds

        try:
            font = ImageFont.truetype("arial.ttf", 8)
        except Exception:
            font = ImageFont.load_default()

        for x in range(x_min, x_max + 1, 5):
            try:
                label_x, _ = to_screen(x + 0.5, y_min)
            except Exception:
                continue
            if screen_left <= label_x <= screen_right:
                draw.text((label_x - 5, max(screen_top + 2, 0)), str(x), fill=(0, 0, 255), font=font)

        for y in range(y_min, y_max + 1, 5):
            try:
                _, label_y = to_screen(x_min, y + 0.5)
            except Exception:
                continue
            if screen_top <= label_y <= screen_bottom:
                draw.text((screen_left + 2, label_y - 5), str(y), fill=(0, 0, 255), font=font)

    @staticmethod
    def _mark_origin(draw, grid_bounds, screen_bounds, to_screen):
        x_min, y_min, x_max, y_max = grid_bounds
        screen_left, screen_top, screen_right, screen_bottom = screen_bounds

        if not (x_min <= 0 <= x_max + 1 and y_min <= 0 <= y_max + 1):
            return

        try:
            origin_x, origin_y = to_screen(0, 0)
        except Exception:
            return

        if not (
            origin_x is not None and origin_y is not None and
            screen_left <= origin_x <= screen_right and
            screen_top <= origin_y <= screen_bottom
        ):
            return

        try:
            font = ImageFont.truetype("arial.ttf", 8)
        except Exception:
            font = ImageFont.load_default()

        draw.rectangle([origin_x, origin_y, origin_x + 3, origin_y + 3], fill=(0, 255, 0), outline=(0, 255, 0))
        draw.text((origin_x + 5, origin_y + 5), "0,0", fill=(0, 255, 0), font=font)