"""GPU-accelerated downscaler pour détection rapide des cellules UNREVEALED."""

from __future__ import annotations

import time
from typing import Set, Tuple, Optional
import numpy as np
from src.config import CELL_SIZE


class GPUDownscaler:
    """Détecte les cellules UNREVEALED via downscale GPU 25× ou CPU fallback."""

    def __init__(self):
        self._gpu_available: Optional[bool] = None

    def detect_unrevealed(
        self,
        image_np: np.ndarray,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int = CELL_SIZE,
    ) -> Set[Tuple[int, int]]:
        """
        Détecte les cellules UNREVEALED (zones blanches uniformes).
        
        Essaie GPU downscale d'abord, fallback CPU pre-screening si indisponible.
        
        Args:
            image_np: Image numpy (H, W, 3) en uint8
            grid_top_left: (x, y) coin supérieur gauche de la grille
            grid_size: (cols, rows) dimensions de la grille en cellules
            stride: Taille en pixels entre deux cellules (défaut: CELL_SIZE=24)
        
        Returns:
            Set de tuples (row, col) des cellules UNREVEALED détectées
        """
        t0 = time.time()
        
        # Vérifier GPU disponibilité une seule fois
        if self._gpu_available is None:
            self._gpu_available = self._check_gpu_available()

        if self._gpu_available:
            try:
                result = self._downscale_gpu(image_np, grid_top_left, grid_size, stride)
                elapsed = time.time() - t0
                cols, rows = grid_size
                total_cells = rows * cols
                print(f"[VISION_PERF] GPU downscale: {elapsed*1000:.2f}ms | {total_cells} cells | {elapsed*1000/total_cells:.3f}ms/cell")
                return result
            except Exception as e:
                print(f"[GPU_DOWNSCALER] GPU failed: {e}, fallback to CPU")
                self._gpu_available = False

        # Fallback CPU
        result = self._downscale_cpu(image_np, grid_top_left, grid_size, stride)
        elapsed = time.time() - t0
        cols, rows = grid_size
        total_cells = rows * cols
        print(f"[VISION_PERF] CPU pre-screening: {elapsed*1000:.2f}ms | {total_cells} cells | {elapsed*1000/total_cells:.3f}ms/cell")
        return result

    def _check_gpu_available(self) -> bool:
        """Vérifie si PyTorch + CUDA sont disponibles."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _downscale_gpu(
        self,
        image_np: np.ndarray,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int,
    ) -> Set[Tuple[int, int]]:
        """
        Downscale GPU 25× pour détecter UNREVEALED.
        
        Stratégie : 512×512 → ~20×20 pixels (1 pixel = 1 cellule)
        Pixels blancs uniformes = UNREVEALED certains
        """
        import torch

        start_x, start_y = grid_top_left
        cols, rows = grid_size

        # Extraire région grille complète
        grid_height = rows * stride
        grid_width = cols * stride
        grid_region = image_np[
            start_y : start_y + grid_height,
            start_x : start_x + grid_width
        ]

        if grid_region.shape[0] < stride or grid_region.shape[1] < stride:
            return set()

        # Copier vers GPU (float32, normalisé [0, 1])
        image_tensor = torch.from_numpy(grid_region).float().cuda() / 255.0
        image_tensor = image_tensor.unsqueeze(0).permute(0, 3, 1, 2)  # (1, 3, H, W)

        # Downscale vers taille grille (chaque pixel = 1 cellule)
        downscaled = torch.nn.functional.interpolate(
            image_tensor,
            size=(rows, cols),
            mode='bilinear',
            align_corners=False
        )  # (1, 3, rows, cols)

        # Détecter pixels blancs uniformes
        # mean >= 0.88 (225/255) et std < 0.02 (5/255)
        mean = downscaled.mean(dim=1, keepdim=True)  # (1, 1, rows, cols)
        std = downscaled.std(dim=1, keepdim=True)    # (1, 1, rows, cols)

        white_mask = (mean >= 0.88) & (std < 0.02)  # (1, 1, rows, cols)
        white_mask = white_mask.squeeze().cpu().numpy()  # (rows, cols)

        # Convertir en coordonnées de cellules
        unrevealed_cells = set()
        if white_mask.ndim == 0:  # Cas 1×1
            if white_mask:
                unrevealed_cells.add((0, 0))
        elif white_mask.ndim == 1:  # Cas 1D
            for idx in range(len(white_mask)):
                if white_mask[idx]:
                    unrevealed_cells.add((0, idx) if rows == 1 else (idx, 0))
        else:  # Cas 2D normal
            for row in range(white_mask.shape[0]):
                for col in range(white_mask.shape[1]):
                    if white_mask[row, col]:
                        unrevealed_cells.add((row, col))

        return unrevealed_cells

    def _downscale_cpu(
        self,
        image_np: np.ndarray,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int,
    ) -> Set[Tuple[int, int]]:
        """
        Downscale CPU pre-screening (fallback optimisé).
        
        Stratégie : Échantillonnage 3 points par cellule (centre + 2 bords)
        Optimisé différemment selon la taille de la grille.
        """
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        total_cells = rows * cols
        
        # Pour les petites grilles (< 50k cellules), utiliser les boucles Python
        if total_cells < 50000:
            return self._downscale_cpu_small(image_np, grid_top_left, grid_size, stride)
        else:
            return self._downscale_cpu_large(image_np, grid_top_left, grid_size, stride)
    
    def _downscale_cpu_small(
        self,
        image_np: np.ndarray,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int,
    ) -> Set[Tuple[int, int]]:
        """Version optimisée pour petites grilles avec boucles Python."""
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        unrevealed_cells = set()

        # Points d'échantillonnage : centre + 2 bords opposés
        sample_points = [(12, 12), (6, 12), (18, 12)]

        for row in range(rows):
            for col in range(cols):
                all_white = True
                for offset_x, offset_y in sample_points:
                    x0 = start_x + col * stride + offset_x
                    y0 = start_y + row * stride + offset_y

                    if y0 >= image_np.shape[0] or x0 >= image_np.shape[1]:
                        all_white = False
                        break

                    pixel = image_np[y0, x0]
                    if pixel.mean() < 230.0:
                        all_white = False
                        break

                if all_white:
                    unrevealed_cells.add((row, col))

        return unrevealed_cells
    
    def _downscale_cpu_large(
        self,
        image_np: np.ndarray,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int,
    ) -> Set[Tuple[int, int]]:
        """Version vectorisée numpy pour grandes grilles."""
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        
        # Points d'échantillonnage optimisés : centre + 2 bords opposés
        sample_offsets = np.array([
            [12, 12],  # Centre
            [6, 12],   # Gauche
            [18, 12],  # Droite
        ])
        
        # Précalculer toutes les positions de cellules
        row_indices, col_indices = np.meshgrid(np.arange(rows), np.arange(cols), indexing='ij')
        
        # Calculer positions pour tous les échantillons
        sample_positions = []
        for offset in sample_offsets:
            x_positions = start_x + col_indices * stride + offset[0]
            y_positions = start_y + row_indices * stride + offset[1]
            sample_positions.append((x_positions, y_positions))
        
        # Vérifier les limites une seule fois
        img_h, img_w = image_np.shape[:2]
        valid_mask = np.ones((rows, cols), dtype=bool)
        
        for x_pos, y_pos in sample_positions:
            valid_mask &= (x_pos >= 0) & (x_pos < img_w) & (y_pos >= 0) & (y_pos < img_h)
        
        # Échantillonner tous les pixels en une fois
        all_samples = []
        for x_pos, y_pos in sample_positions:
            # Masquer les positions invalides
            x_valid = np.where(valid_mask, x_pos, 0)
            y_valid = np.where(valid_mask, y_pos, 0)
            samples = image_np[y_valid, x_valid]
            all_samples.append(samples.mean(axis=2))  # Moyenne RGB
        
        # Combiner les échantillons
        sample_array = np.stack(all_samples, axis=2)  # Shape: (rows, cols, 3)
        
        # Cellules unrevealed = tous les échantillons blancs (> 230)
        unrevealed_mask = np.all(sample_array > 230.0, axis=2) & valid_mask
        
        # Convertir en set de coordonnées
        unrevealed_coords = set(zip(*np.where(unrevealed_mask)))
        
        return unrevealed_coords
