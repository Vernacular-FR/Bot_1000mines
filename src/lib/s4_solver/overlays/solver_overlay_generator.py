#!/usr/bin/env python3
"""
SolverOverlayGenerator - Overlays des solutions du solver
Génère des overlays à partir des cellules stockées dans GridDB,
avec un style visuel cohérent avec OptimizedOverlayGenerator.
"""

import os
from typing import Dict, Any
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

from src.lib.config import PATHS, CELL_SIZE, CELL_BORDER
from src.lib.s3_tensor.grid_state import GamePersistence, GridDB


class SolverOverlayGenerator:
    """Génère des overlays de la grille à partir de GridDB"""

    def __init__(
        self,
        cell_size: int = CELL_SIZE,
        output_dir: str | None = None,
        render_cells: bool = False,
    ):
        self.cell_size = cell_size
        self.cell_border = CELL_BORDER
        self.total_size = self.cell_size + self.cell_border
        self.output_dir = output_dir  # Obligatoire, plus de valeur par défaut
        self.render_cells = render_cells

        # Couleurs alignées sur OptimizedOverlayGenerator.TYPE_COLORS
        self.TYPE_COLORS: Dict[str, tuple[int, int, int]] = {
            "empty": (128, 128, 128),
            "unrevealed": (255, 255, 255),
            "flag": (255, 0, 0),
            "mine": (0, 0, 0),
            "number_1": (0, 0, 255),
            "number_2": (0, 255, 0),
            "number_3": (255, 0, 0),
            "number_4": (128, 0, 128),
            "number_5": (255, 165, 0),
            "number_6": (0, 255, 255),
            "number_7": (0, 0, 0),
            "number_8": (64, 64, 64),
            "unknown": (255, 255, 0),
        }

        # Bordures alignées sur OptimizedOverlayGenerator.BORDER_COLORS
        self.BORDER_COLORS: Dict[str, tuple[int, int, int]] = {
            "empty": (64, 64, 64),
            "unrevealed": (180, 180, 180),
            "flag": (200, 0, 0),
            "number_1": (0, 50, 150),
            "number_2": (0, 150, 0),
            "number_3": (200, 0, 0),
            "number_4": (100, 0, 100),
            "number_5": (200, 100, 0),
            "number_6": (0, 150, 150),
            "number_7": (0, 0, 0),
            "number_8": (50, 50, 50),
            "unknown": (200, 200, 0),
        }

        # Précharger quelques polices
        self.fonts = self._preload_fonts()

        # Créer le dossier de sortie
        os.makedirs(self.output_dir, exist_ok=True)

    def _preload_fonts(self) -> Dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
        fonts: Dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}
        try:
            fonts["small"] = ImageFont.truetype("arial.ttf", 8)
            fonts["medium"] = ImageFont.truetype("arial.ttf", 10)
            fonts["large"] = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            fonts["small"] = ImageFont.load_default()
            fonts["medium"] = ImageFont.load_default()
            fonts["large"] = ImageFont.load_default()
        return fonts

    def generate_overlay_from_db(self, screenshot_path: str, grid_db: GridDB, 
                              game_id: str = None, iteration_num: int = None) -> str:
        """Génère un overlay solver pour un screenshot donné à partir de GridDB"""
        if not os.path.exists(screenshot_path):
            print(f"ERREUR: Screenshot inexistant pour overlay solver: {screenshot_path}")
            return ""

        # Charger l'image de base
        base_image = Image.open(screenshot_path).convert("RGBA")
        overlay_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        # Récupérer les cellules et les bounds depuis la DB
        summary = grid_db.get_summary()
        cells = grid_db.get_all_cells()

        x_min, y_min, _, _ = summary.get("bounds", [0, 0, 0, 0])

        # Dessiner chaque cellule (désactivé par défaut pour ne garder que les actions)
        if self.render_cells:
            for cell in cells:
                cell_type = cell.get("type", "unknown")
                x = cell.get("x", 0)
                y = cell.get("y", 0)

                # Coordonnées pixel en utilisant les bounds pour normaliser
                pixel_x = (x - x_min) * self.total_size
                pixel_y = (y - y_min) * self.total_size

                color = self.TYPE_COLORS.get(cell_type, (255, 255, 0))
                border_color = self.BORDER_COLORS.get(cell_type, (128, 128, 128))

                # Gestion des zones (contour coloré)
                metadata = cell.get("metadata", {})
                zone_id = metadata.get("zone_id")
                zone_color = None
                
                if zone_id is not None:
                    # Générer une couleur de zone basée sur l'ID
                    import random
                    random.seed(zone_id) # Toujours la même couleur pour la même zone
                    r = random.randint(100, 255)
                    g = random.randint(100, 255)
                    b = random.randint(100, 255)
                    zone_color = (r, g, b)
                    
                    # Si c'est une case inconnue avec zone, on utilise la couleur de zone
                    if cell_type in ["unknown", "unrevealed"]:
                        # Mélanger jaune et couleur de zone
                        color = tuple((c1 + c2) // 2 for c1, c2 in zip(color, zone_color))

                box = [
                    pixel_x,
                    pixel_y,
                    pixel_x + self.cell_size - 1,
                    pixel_y + self.cell_size - 1,
                ]

                # Remplissage semi-transparent
                alpha = 100
                draw.rectangle(box, fill=color + (alpha,), outline=border_color + (255,), width=2)
                
                # Si on a un ID de zone, dessiner un petit carré de couleur dans le coin
                if zone_id is not None and zone_color is not None:
                    zone_indicator_size = 4
                    zone_box = [
                        pixel_x + self.cell_size - zone_indicator_size - 1,
                        pixel_y + 1,
                        pixel_x + self.cell_size - 1,
                        pixel_y + zone_indicator_size + 1
                    ]
                    draw.rectangle(zone_box, fill=zone_color + (255,))

        # Dessiner les actions en attente (Surlignage)
        actions = grid_db.get_pending_actions()
        for action in actions:
            ax, ay = action.get("coordinates", (0, 0))
            action_type = action.get("type", "unknown")
            
            # Coordonnées pixel
            pixel_x = (ax - x_min) * self.total_size
            pixel_y = (ay - y_min) * self.total_size
            
            box = [
                pixel_x,
                pixel_y,
                pixel_x + self.cell_size - 1,
                pixel_y + self.cell_size - 1,
            ]
            
            if action_type == 'reveal':
                # Cadre VERT épais pour REVEAL
                draw.rectangle(box, outline=(0, 255, 0, 255), width=4)
            elif action_type == 'flag':
                # Cadre ROUGE épais pour FLAG
                draw.rectangle(box, outline=(255, 0, 0, 255), width=4)

        # Composer l'overlay avec l'image de base
        overlay_image = Image.alpha_composite(base_image, overlay_layer).convert("RGB")

        # Nom de fichier avec bonne nomenclature
        if game_id and iteration_num is not None:
            # Extraire les coordonnées depuis le nom du fichier base
            base_name = os.path.splitext(os.path.basename(screenshot_path))[0]
            parts = base_name.split("_")
            if len(parts) >= 4:
                coords = "_".join(parts[-4:])  # Prend les 4 derniers parties pour les coordonnées
                filename = f"{game_id}_iter{iteration_num}_solver_{coords}.png"
            else:
                filename = f"{game_id}_iter{iteration_num}_solver.png"
        else:
            # Fallback ancienne méthode
            base_name = os.path.splitext(os.path.basename(screenshot_path))[0]
            filename = f"{base_name}_solver_overlay.png"
        filepath = os.path.join(self.output_dir, filename)

        overlay_image.save(filepath, optimize=True)
        print(f"INFO: Overlay solver généré: {filepath}")

        return filepath
