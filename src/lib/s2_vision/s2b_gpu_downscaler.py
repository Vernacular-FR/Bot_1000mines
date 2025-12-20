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
        
        Stratégie : Échantillonnage 1 pixel par cellule (centre)
        Détecte cellules blanches uniformes rapidement
        """
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        unrevealed_cells = set()

        # Échantillonner seulement le centre de chaque cellule (12, 12)
        center_x, center_y = 12, 12

        # Vectoriser l'accès aux pixels
        for row in range(rows):
            for col in range(cols):
                x0 = start_x + col * stride + center_x
                y0 = start_y + row * stride + center_y

                # Vérifier si cellule hors limites
                if y0 >= image_np.shape[0] or x0 >= image_np.shape[1]:
                    continue

                # Échantillonner 1 pixel (centre)
                pixel = image_np[y0, x0]
                mean_val = pixel.mean()  # Moyenne RGB

                # Si très blanc → UNREVEALED probable
                if mean_val >= 230.0:
                    unrevealed_cells.add((row, col))

        return unrevealed_cells
