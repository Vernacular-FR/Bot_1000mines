"""
Module d'overlay combiné structuré en 3 couches :
- GridOverlayLayer : dessin de la grille
- InterfaceOverlayLayer : dessin des éléments d'interface
- CombinedOverlayAssembler : assemblage et I/O
"""

import os
from datetime import datetime
from typing import Tuple

import numpy as np
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


class InterfaceOverlayLayer:
    """Responsable du dessin des éléments d'interface."""

    @staticmethod
    def draw(draw: ImageDraw.Draw, interface_elements: list) -> int:
        elements_drawn = 0
        try:
            font = ImageFont.truetype("arial.ttf", 10)
        except Exception:
            font = ImageFont.load_default()

        for element in interface_elements or []:
            if 'bounds' in element:
                x1, y1, x2, y2 = element['bounds']
            elif 'screenshot_x' in element and 'screenshot_y' in element:
                x1 = element['screenshot_x']
                y1 = element['screenshot_y']
                x2 = element.get('screenshot_x2', x1 + element.get('width', 20))
                y2 = element.get('screenshot_y2', y1 + element.get('height', 20))
            else:
                continue

            draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=2)
            name = element.get('name', f'element_{elements_drawn + 1}')
            draw.text((x1 + 2, y1 + 2), name, fill=(255, 0, 0), font=font)
            elements_drawn += 1

        return elements_drawn


class CombinedOverlayAssembler:
    """Assemble grille + interface et gère l'I/O (un seul fichier)."""

    USABLE_MASK_COLOR = (0, 255, 0, 100)
    UNUSABLE_MASK_COLOR = (255, 0, 0, 120)

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(
        self,
        base_image: Image.Image,
        interface_elements: list,
        grid_bounds: Tuple[int, int, int, int] = None,
        coord_system=None,
        viewport_mapper=None,
        filename: str = None,
        usable_mask=None,
    ) -> str:
        try:
            combined_image = base_image.copy()
            overlay_layer = Image.new("RGBA", combined_image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay_layer)

            resolved_bounds = grid_bounds or (-30, -15, 30, 15)
            interface_count = InterfaceOverlayLayer.draw(draw, interface_elements)
            grid_lines = GridOverlayLayer.draw(draw, combined_image.size, resolved_bounds, coord_system, viewport_mapper)
            if usable_mask is not None and coord_system:
                self._draw_usable_mask(draw, usable_mask, resolved_bounds, coord_system)

            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font = ImageFont.load_default()
            summary_text = f"Interface: {interface_count} éléments | Grille: {'oui' if coord_system else 'non'}"
            draw.text((10, 10), summary_text, fill=(128, 0, 128), font=font)
            if usable_mask is not None:
                mask_stats = self._usable_mask_stats(usable_mask)
                draw.text((10, 26), mask_stats, fill=(0, 128, 0), font=font)

            shifted_overlay = Image.new("RGBA", overlay_layer.size, (0, 0, 0, 0))
            shifted_overlay.paste(overlay_layer, (-1, -1))  # TODO -1px offset à diagnostiquer

            combined_rgba = combined_image.convert("RGBA")
            combined_rgba = Image.alpha_composite(combined_rgba, shifted_overlay)
            combined_image = combined_rgba.convert(base_image.mode)

            overlay_filename = filename or f"combined_overlay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            overlay_path = os.path.join(self.output_dir, overlay_filename)
            combined_image.save(overlay_path)

            print(f"[COMBINED] Overlay combiné généré: {overlay_path}")
            print(f"  Interface: {interface_count} éléments")
            print(f"  Grille: {grid_lines} lignes")

            return overlay_path

        except Exception as e:
            print(f"[ERREUR] Erreur lors de l'assemblage: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_from_screenshot(
        self,
        screenshot_path: str,
        interface_elements: list,
        grid_bounds: Tuple[int, int, int, int] = None,
        coord_system=None,
        viewport_mapper=None,
        filename: str = None,
        usable_mask=None,
    ) -> str:
        try:
            base_image = Image.open(screenshot_path)
            return self.generate(
                base_image,
                interface_elements,
                grid_bounds,
                coord_system,
                viewport_mapper,
                filename,
                usable_mask,
            )
        except Exception as e:
            print(f"[ERREUR] Erreur lors du chargement du screenshot: {e}")
            return None

    @staticmethod
    def create_combined_overlay(
        screenshot_path: str,
        interface_elements: list,
        grid_bounds: Tuple[int, int, int, int] = None,
        coord_system=None,
        output_dir: str = "assets/screenshots/overlays",
        usable_mask=None,
    ) -> str:
        assembler = CombinedOverlayAssembler(output_dir)
        return assembler.generate_from_screenshot(
            screenshot_path,
            interface_elements,
            grid_bounds,
            coord_system,
            usable_mask=usable_mask,
        )

    def _draw_usable_mask(self, draw, usable_mask, grid_bounds, coord_system):
        mask = np.asarray(usable_mask, dtype=bool)
        start_x, start_y, end_x, end_y = grid_bounds
        expected_width = end_x - start_x + 1
        expected_height = end_y - start_y + 1
        if mask.shape != (expected_height, expected_width):
            print(f"[MASK] Dimensions inattendues mask={mask.shape} vs attendu=({expected_height},{expected_width})")
        cell_total = getattr(coord_system, "cell_total", getattr(coord_system, "cell_size", 24))

        for gy in range(min(mask.shape[0], expected_height)):
            grid_y = start_y + gy
            for gx in range(min(mask.shape[1], expected_width)):
                grid_x = start_x + gx
                cell_left, cell_top = coord_system.grid_to_screen(grid_x, grid_y)
                cell_right = cell_left + cell_total
                cell_bottom = cell_top + cell_total
                color = self.USABLE_MASK_COLOR if mask[gy, gx] else self.UNUSABLE_MASK_COLOR
                draw.rectangle(
                    [
                        int(round(cell_left)),
                        int(round(cell_top)),
                        int(round(cell_right)),
                        int(round(cell_bottom)),
                    ],
                    fill=color,
                    outline=None,
                )

    @staticmethod
    def _usable_mask_stats(usable_mask) -> str:
        mask = np.asarray(usable_mask, dtype=bool)
        total = mask.size
        usable = int(mask.sum())
        ratio = (usable / total * 100.0) if total else 0.0
        return f"Usable mask: {usable}/{total} ({ratio:.1f}%)"
