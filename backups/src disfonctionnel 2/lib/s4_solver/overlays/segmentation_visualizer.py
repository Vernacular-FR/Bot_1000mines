import os
import random
from typing import Dict, Tuple
from PIL import Image, ImageDraw, ImageFont
from src.lib.s4_solver.core.segmentation import Segmentation, Zone
from src.lib.s4_solver.core.grid_analyzer import GridAnalyzer
from src.lib.config import CELL_SIZE, CELL_BORDER

class SegmentationVisualizer:
    def __init__(self, output_dir):  # Obligatoire, plus de valeur par défaut
        self.output_dir = output_dir
        self.cell_size = CELL_SIZE
        self.cell_border = CELL_BORDER
        self.total_size = self.cell_size + self.cell_border
        os.makedirs(self.output_dir, exist_ok=True)
        
        try:
            self.font = ImageFont.truetype("arial.ttf", 10)
        except:
            self.font = ImageFont.load_default()

    def visualize(self, analyzer: GridAnalyzer, segmentation: Segmentation, base_image_path: str, 
                  game_id: str = None, iteration_num: int = None) -> str:
        """
        Génère une visualisation de la segmentation sur l'image de base.
        
        Args:
            analyzer: GridAnalyzer contenant l'état de la grille
            segmentation: Segmentation avec les zones et composantes à visualiser
            base_image_path: Chemin vers l'image de base (screenshot)
            game_id: Identifiant de la partie (optionnel, pour le nommage)
            iteration_num: Numéro d'itération (optionnel, pour le nommage)
            
        Returns:
            str: Chemin vers l'image de visualisation générée, ou chaîne vide si erreur
        """
        if not os.path.exists(base_image_path):
            print(f"Error: Image {base_image_path} not found")
            return ""

        base_image = Image.open(base_image_path).convert("RGBA")
        overlay = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Generate colors for components (not zones)
        # Component ID -> Color
        colors = {}
        
        # Draw Components (not individual zones)
        min_x, min_y, _, _ = analyzer.get_bounds()
        
        for comp in segmentation.components:
            # Random distinct color per component
            if comp.id not in colors:
                # Use HSL-like logic or just random RGB
                # Avoiding too dark or too light
                r = random.randint(50, 200)
                g = random.randint(50, 200)
                b = random.randint(50, 200)
                colors[comp.id] = (r, g, b, 180) # Alpha 180
            
            color = colors[comp.id]
            
            # Draw all zones in this component with the same color
            for zone in comp.zones:
                for (x, y) in zone.cells:
                    # Calculate pixel position
                    # Grid coords are absolute, but we need to map to image relative to bounds
                    # Grid already has min_x, min_y from DB
                    
                    pixel_x = (x - min_x) * self.total_size
                    pixel_y = (y - min_y) * self.total_size
                    
                    box = [
                        pixel_x, pixel_y,
                        pixel_x + self.cell_size, pixel_y + self.cell_size
                    ]
                    
                    # Fill component
                    draw.rectangle(box, fill=color)
                    
                # Draw Zone ID for each zone (but with component color)
                for (x, y) in zone.cells:
                    pixel_x = (x - min_x) * self.total_size
                    pixel_y = (y - min_y) * self.total_size
                    text_pos = (pixel_x + 2, pixel_y + 2)
                    draw.text(text_pos, f"Z{zone.id}", fill=(255, 255, 255), font=self.font)

        # Draw component boundaries or separators if needed
        # For now, just draw constraints as before

        # Draw Constraints (Numbered cells that cause the zones)
        # We can highlight the numbers that are part of the frontier constraints
        # Let's draw red borders around them
        
        constraint_cells = set()
        for zone in segmentation.zones:
            for c in zone.constraints:
                constraint_cells.add(c)
                
        for (cx, cy) in constraint_cells:
            pixel_x = (cx - min_x) * self.total_size
            pixel_y = (cy - min_y) * self.total_size
             
            box = [
                pixel_x, pixel_y,
                pixel_x + self.cell_size, pixel_y + self.cell_size
            ]
            draw.rectangle(box, outline=(255, 0, 0, 255), width=2)

        # Combine
        final_image = Image.alpha_composite(base_image, overlay)
        
        # Save avec bonne nomenclature
        if game_id and iteration_num is not None:
            # Extraire les coordonnées depuis le nom du fichier base
            base_name = os.path.basename(base_image_path).replace(".png", "")
            parts = base_name.split("_")
            if len(parts) >= 4:
                coords = "_".join(parts[-4:])  # Prend les 4 derniers parties pour les coordonnées
                filename = f"{game_id}_iter{iteration_num}_segmentation_{coords}.png"
            else:
                filename = f"{game_id}_iter{iteration_num}_segmentation.png"
        else:
            # Fallback ancienne méthode
            filename = os.path.basename(base_image_path).replace(".png", "_segmentation.png")
        
        save_path = os.path.join(self.output_dir, filename)
        final_image.save(save_path)
        print(f"Segmentation overlay saved to {save_path}")
        return save_path
