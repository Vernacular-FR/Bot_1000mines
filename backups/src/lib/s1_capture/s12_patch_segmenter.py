"""
PatchSegmenter - Segmentation d'images alignée sur viewport (S1.2)

Segmente les captures d'écran en patches utilisables:
- Alignement précis sur les bornes viewport_bounds
- Extraction des patches de cellules individuelles
- Gestion des masques d'interface pour exclusion
- Optimisation mémoire pour les grandes grilles
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

# Optional cv2 dependency with fallback
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

from ..s0_navigation.s03_coordinate_converter import CoordinateConverter, GridBounds
from ..s0_navigation.s02_interface_detector import InterfaceMask
from ..s3_tensor.tensor_grid import CellSymbol


class PatchType(Enum):
    """Types de patches d'images"""
    CELL_PATCH = "cell_patch"           # Patch individuel de cellule
    REGION_PATCH = "region_patch"       # Patch de région multiple
    VIEWPORT_PATCH = "viewport_patch"   # Patch du viewport complet
    FRONTIER_PATCH = "frontier_patch"   # Patch des zones de frontière


@dataclass
class ImagePatch:
    """Patch d'image avec métadonnées"""
    patch_id: str
    patch_type: PatchType
    image_data: np.ndarray
    grid_bounds: GridBounds
    screen_bounds: Tuple[int, int, int, int]  # (x, y, w, h) écran
    confidence: float
    metadata: Dict[str, Any]
    
    def is_valid(self) -> bool:
        """Vérifie si le patch est valide"""
        return (self.image_data is not None and 
                self.image_data.size > 0 and
                self.confidence > 0.0)
    
    def get_center(self) -> Tuple[int, int]:
        """Retourne le centre du patch en coordonnées grille"""
        cx = (self.grid_bounds.x_min + self.grid_bounds.x_max) // 2
        cy = (self.grid_bounds.y_min + self.grid_bounds.y_max) // 2
        return (cx, cy)


@dataclass
class SegmentationResult:
    """Résultat de la segmentation d'image"""
    success: bool
    patches: List[ImagePatch]
    viewport_bounds: GridBounds
    segmentation_time: float
    metadata: Dict[str, Any]
    
    def get_patches_by_type(self, patch_type: PatchType) -> List[ImagePatch]:
        """Retourne les patches par type"""
        return [p for p in self.patches if p.patch_type == patch_type]
    
    def get_cell_patches(self) -> List[ImagePatch]:
        """Retourne uniquement les patches de cellules"""
        return self.get_patches_by_type(PatchType.CELL_PATCH)


class PatchSegmenter:
    """
    Segmenteur d'images pour l'extraction de patches alignés
    
    Fonctionnalités:
    - Alignement précis sur les coordonnées TensorGrid
    - Segmentation intelligente avec masques d'interface
    - Optimisation mémoire et performance
    - Support pour différents types de patches
    """
    
    def __init__(self, coordinate_converter: CoordinateConverter,
                 patch_margin: int = 2,
                 enable_interface_masking: bool = True,
                 min_patch_size: int = 10):
        """
        Initialise le segmenteur de patches
        
        Args:
            coordinate_converter: Convertisseur de coordonnées S0
            patch_margin: Marge autour des cellules (pixels)
            enable_interface_masking: Activer le masquage d'interface
            min_patch_size: Taille minimale des patches
        """
        # Dépendances
        self.coordinate_converter = coordinate_converter
        
        # Configuration
        self.patch_margin = patch_margin
        self.enable_interface_masking = enable_interface_masking
        self.min_patch_size = min_patch_size
        
        # État et cache
        self._last_segmentation: Optional[SegmentationResult] = None
        self._patch_counter: int = 0
        
        # Statistiques
        self._stats = {
            'segmentations_performed': 0,
            'total_patches_extracted': 0,
            'average_segmentation_time': 0.0,
            'patches_per_segmentation': 0.0
        }
    
    def segment_viewport(self, screenshot: np.ndarray,
                        viewport_bounds: GridBounds,
                        interface_mask: Optional[InterfaceMask] = None) -> SegmentationResult:
        """
        Segment le viewport en patches de cellules
        
        Args:
            screenshot: Capture d'écran complète
            viewport_bounds: Bornes du viewport dans la grille
            interface_mask: Masque d'interface pour exclusion
            
        Returns:
            Résultat de la segmentation
        """
        import time
        start_time = time.time()
        
        try:
            # Valider les entrées
            if not self._validate_inputs(screenshot, viewport_bounds):
                return SegmentationResult(
                    success=False,
                    patches=[],
                    viewport_bounds=viewport_bounds,
                    segmentation_time=0.0,
                    metadata={'error': 'Invalid inputs'}
                )
            
            # Extraire la région du viewport
            viewport_region = self._extract_viewport_region(screenshot, viewport_bounds)
            
            if viewport_region is None:
                return SegmentationResult(
                    success=False,
                    patches=[],
                    viewport_bounds=viewport_bounds,
                    segmentation_time=0.0,
                    metadata={'error': 'Failed to extract viewport'}
                )
            
            # Segmenter en patches de cellules
            patches = self._segment_into_cell_patches(
                viewport_region, viewport_bounds, interface_mask
            )
            
            # Créer le résultat
            segmentation_time = time.time() - start_time
            result = SegmentationResult(
                success=True,
                patches=patches,
                viewport_bounds=viewport_bounds,
                segmentation_time=segmentation_time,
                metadata={
                    'screenshot_shape': screenshot.shape,
                    'viewport_shape': viewport_region.shape,
                    'patches_count': len(patches),
                    'interface_masking': self.enable_interface_masking
                }
            )
            
            # Mettre à jour les statistiques
            self._update_stats(len(patches), segmentation_time)
            
            # Mettre en cache
            self._last_segmentation = result
            
            return result
            
        except Exception as e:
            return SegmentationResult(
                success=False,
                patches=[],
                viewport_bounds=viewport_bounds,
                segmentation_time=time.time() - start_time,
                metadata={'error': str(e)}
            )
    
    def segment_region(self, screenshot: np.ndarray,
                      region_bounds: GridBounds,
                      interface_mask: Optional[InterfaceMask] = None) -> List[ImagePatch]:
        """
        Segment une région spécifique en patches
        
        Args:
            screenshot: Capture d'écran
            region_bounds: Bornes de la région à segmenter
            interface_mask: Masque d'interface
            
        Returns:
            Liste des patches de la région
        """
        # Segmenter le viewport complet
        viewport_result = self.segment_viewport(screenshot, region_bounds, interface_mask)
        
        if not viewport_result.success:
            return []
        
        # Filtrer les patches dans la région demandée
        region_patches = []
        for patch in viewport_result.patches:
            if self._bounds_intersect(patch.grid_bounds, region_bounds):
                region_patches.append(patch)
        
        return region_patches
    
    def extract_single_cell_patch(self, screenshot: np.ndarray,
                                 grid_x: int, grid_y: int) -> Optional[ImagePatch]:
        """
        Extrait un patch pour une seule cellule
        
        Args:
            screenshot: Capture d'écran
            grid_x, grid_y: Coordonnées grille de la cellule
            
        Returns:
            Patch de la cellule ou None si échec
        """
        try:
            # Calculer les bornes de la cellule
            cell_bounds = self.coordinate_converter.get_cell_bounds(grid_x, grid_y)
            
            # Convertir en coordonnées écran
            screen_bounds = self._grid_bounds_to_screen_bounds(cell_bounds)
            
            # Extraire le patch
            patch_image = self._extract_patch_from_screenshot(
                screenshot, screen_bounds
            )
            
            if patch_image is None:
                return None
            
            # Créer le patch
            patch = ImagePatch(
                patch_id=f"cell_{grid_x}_{grid_y}",
                patch_type=PatchType.CELL_PATCH,
                image_data=patch_image,
                grid_bounds=GridBounds(grid_x, grid_y, grid_x, grid_y),
                screen_bounds=screen_bounds,
                confidence=1.0,
                metadata={'single_cell': True}
            )
            
            return patch
            
        except Exception:
            return None
    
    def extract_frontier_patches(self, screenshot: np.ndarray,
                                viewport_bounds: GridBounds,
                                frontier_mask: np.ndarray,
                                interface_mask: Optional[InterfaceMask] = None) -> List[ImagePatch]:
        """
        Extrait les patches des zones de frontière
        
        Args:
            screenshot: Capture d'écran
            viewport_bounds: Bornes du viewport
            frontier_mask: Masque des cellules de frontière
            interface_mask: Masque d'interface
            
        Returns:
            Liste des patches de frontière
        """
        # Segmenter le viewport complet
        viewport_result = self.segment_viewport(screenshot, viewport_bounds, interface_mask)
        
        if not viewport_result.success:
            return []
        
        # Filtrer les patches de frontière
        frontier_patches = []
        for patch in viewport_result.get_cell_patches():
            # Vérifier si la cellule est dans la frontière
            cx, cy = patch.get_center()
            
            # Convertir en coordonnées locales pour le masque
            local_x = cx - viewport_bounds.x_min
            local_y = cy - viewport_bounds.y_min
            
            if (0 <= local_x < frontier_mask.shape[1] and 
                0 <= local_y < frontier_mask.shape[0] and
                frontier_mask[local_y, local_x]):
                
                patch.patch_type = PatchType.FRONTIER_PATCH
                frontier_patches.append(patch)
        
        return frontier_patches
    
    def _validate_inputs(self, screenshot: np.ndarray,
                        viewport_bounds: GridBounds) -> bool:
        """Valide les entrées de segmentation"""
        if screenshot is None or screenshot.size == 0:
            return False
        
        if viewport_bounds.width() <= 0 or viewport_bounds.height() <= 0:
            return False
        
        return True
    
    def _extract_viewport_region(self, screenshot: np.ndarray,
                                viewport_bounds: GridBounds) -> Optional[np.ndarray]:
        """Extrait la région du viewport de la capture"""
        try:
            # Convertir les bornes grille en bornes écran
            screen_bounds = self._grid_bounds_to_screen_bounds(viewport_bounds)
            
            x, y, w, h = screen_bounds
            
            # Valider les coordonnées
            if (x < 0 or y < 0 or x + w > screenshot.shape[1] or 
                y + h > screenshot.shape[0]):
                return None
            
            # Extraire la région
            viewport_region = screenshot[y:y+h, x:x+w]
            
            return viewport_region
            
        except Exception:
            return None
    
    def _segment_into_cell_patches(self, viewport_region: np.ndarray,
                                  viewport_bounds: GridBounds,
                                  interface_mask: Optional[InterfaceMask]) -> List[ImagePatch]:
        """Segmente la région viewport en patches de cellules"""
        patches = []
        
        cell_size = self.coordinate_converter.get_effective_cell_size()
        
        # Parcourir toutes les cellules du viewport
        for grid_y in range(viewport_bounds.y_min, viewport_bounds.y_max + 1):
            for grid_x in range(viewport_bounds.x_min, viewport_bounds.x_max + 1):
                # Calculer les coordonnées locales dans le viewport
                local_x = grid_x - viewport_bounds.x_min
                local_y = grid_y - viewport_bounds.y_min
                
                # Calculer les coordonnées pixel dans le viewport
                pixel_x = local_x * cell_size
                pixel_y = local_y * cell_size
                
                # Extraire le patch de cellule
                cell_patch = self._extract_cell_patch_from_viewport(
                    viewport_region, pixel_x, pixel_y, cell_size
                )
                
                if cell_patch is not None:
                    # Vérifier le masque d'interface
                    if self.enable_interface_masking and interface_mask:
                        if self._is_patch_masked(cell_patch, interface_mask, 
                                               pixel_x, pixel_y):
                            continue
                    
                    # Créer le patch
                    patch = ImagePatch(
                        patch_id=f"cell_{self._patch_counter}",
                        patch_type=PatchType.CELL_PATCH,
                        image_data=cell_patch,
                        grid_bounds=GridBounds(grid_x, grid_y, grid_x, grid_y),
                        screen_bounds=self._calculate_screen_bounds(
                            grid_x, grid_y, cell_size
                        ),
                        confidence=self._calculate_patch_confidence(cell_patch),
                        metadata={
                            'local_coords': (local_x, local_y),
                            'pixel_coords': (pixel_x, pixel_y)
                        }
                    )
                    
                    patches.append(patch)
                    self._patch_counter += 1
        
        return patches
    
    def _extract_cell_patch_from_viewport(self, viewport_region: np.ndarray,
                                        pixel_x: int, pixel_y: int,
                                        cell_size: int) -> Optional[np.ndarray]:
        """Extrait un patch de cellule de la région viewport"""
        try:
            # Ajouter la marge
            x_start = max(0, pixel_x - self.patch_margin)
            y_start = max(0, pixel_y - self.patch_margin)
            x_end = min(viewport_region.shape[1], pixel_x + cell_size + self.patch_margin)
            y_end = min(viewport_region.shape[0], pixel_y + cell_size + self.patch_margin)
            
            # Extraire le patch
            patch = viewport_region[y_start:y_end, x_start:x_end]
            
            # Valider la taille
            if patch.size < self.min_patch_size * self.min_patch_size:
                return None
            
            return patch
            
        except Exception:
            return None
    
    def _extract_patch_from_screenshot(self, screenshot: np.ndarray,
                                      screen_bounds: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Extrait un patch de la capture d'écran"""
        try:
            x, y, w, h = screen_bounds
            
            # Valider les coordonnées
            if (x < 0 or y < 0 or x + w > screenshot.shape[1] or 
                y + h > screenshot.shape[0]):
                return None
            
            return screenshot[y:y+h, x:x+w]
            
        except Exception:
            return None
    
    def _is_patch_masked(self, patch: np.ndarray, interface_mask: InterfaceMask,
                        pixel_x: int, pixel_y: int) -> bool:
        """Vérifie si un patch est masqué par l'interface"""
        # Vérifier les coins du patch
        h, w = patch.shape[:2]
        
        corners = [
            (pixel_x, pixel_y),
            (pixel_x + w - 1, pixel_y),
            (pixel_x, pixel_y + h - 1),
            (pixel_x + w - 1, pixel_y + h - 1)
        ]
        
        for x, y in corners:
            if interface_mask.should_exclude_pixel(x, y):
                return True
        
        return False
    
    def _calculate_screen_bounds(self, grid_x: int, grid_y: int,
                                cell_size: int) -> Tuple[int, int, int, int]:
        """Calcule les bornes écran d'un patch"""
        canvas_x, canvas_y = self.coordinate_converter.grid_to_canvas(grid_x, grid_y)
        screen_x, screen_y = self.coordinate_converter.canvas_to_screen(canvas_x, canvas_y)
        
        return (
            screen_x - self.patch_margin,
            screen_y - self.patch_margin,
            cell_size + 2 * self.patch_margin,
            cell_size + 2 * self.patch_margin
        )
    
    def _grid_bounds_to_screen_bounds(self, grid_bounds: GridBounds) -> Tuple[int, int, int, int]:
        """Convertit les bornes grille en bornes écran"""
        canvas_bounds = self.coordinate_converter.grid_bounds_to_canvas(grid_bounds)
        screen_x, screen_y = self.coordinate_converter.canvas_to_screen(
            canvas_bounds.x_min, canvas_bounds.y_min
        )
        
        return (
            screen_x,
            screen_y,
            canvas_bounds.width(),
            canvas_bounds.height()
        )
    
    def _calculate_patch_confidence(self, patch: np.ndarray) -> float:
        """Calcule la confiance d'un patch basée sur sa qualité"""
        if patch is None or patch.size == 0:
            return 0.0
        
        # Calculer la variance comme mesure de confiance
        if len(patch.shape) == 3:
            # Image couleur: utiliser la variance moyenne des canaux
            variance = np.mean([np.var(patch[:, :, i]) for i in range(3)])
        else:
            # Image niveaux de gris
            variance = np.var(patch)
        
        # Normaliser la variance en confiance (0.0..1.0)
        # Variance élevée = plus de détails = plus grande confiance
        confidence = min(1.0, variance / 1000.0)
        
        return confidence
    
    def _bounds_intersect(self, bounds1: GridBounds, bounds2: GridBounds) -> bool:
        """Vérifie si deux bornes se croisent"""
        return not (bounds1.x_max < bounds2.x_min or bounds1.x_min > bounds2.x_max or
                   bounds1.y_max < bounds2.y_min or bounds1.y_min > bounds2.y_max)
    
    def _update_stats(self, patches_count: int, segmentation_time: float) -> None:
        """Met à jour les statistiques"""
        self._stats['segmentations_performed'] += 1
        self._stats['total_patches_extracted'] += patches_count
        
        # Mettre à jour le temps moyen
        total_seg = self._stats['segmentations_performed']
        current_avg = self._stats['average_segmentation_time']
        self._stats['average_segmentation_time'] = (
            (current_avg * (total_seg - 1) + segmentation_time) / total_seg
        )
        
        # Mettre à jour le nombre moyen de patches
        self._stats['patches_per_segmentation'] = (
            self._stats['total_patches_extracted'] / total_seg
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du segmenteur"""
        stats = self._stats.copy()
        stats.update({
            'patch_counter': self._patch_counter,
            'has_cached_result': self._last_segmentation is not None,
            'configuration': {
                'patch_margin': self.patch_margin,
                'interface_masking': self.enable_interface_masking,
                'min_patch_size': self.min_patch_size
            }
        })
        return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        self._stats = {
            'segmentations_performed': 0,
            'total_patches_extracted': 0,
            'average_segmentation_time': 0.0,
            'patches_per_segmentation': 0.0
        }
        self._patch_counter = 0
    
    def get_last_result(self) -> Optional[SegmentationResult]:
        """Retourne le dernier résultat de segmentation"""
        return self._last_segmentation
