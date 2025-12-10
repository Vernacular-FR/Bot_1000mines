"""
MetadataExtractor - Extraction des métadonnées de patches (S1.3)

Extrait et enrichit les métadonnées des patches d'images:
- Coordonnées de cellules utilisables
- Métadonnées de qualité et confiance
- Informations de contexte et temporalité
- Interface avec TensorGrid pour mise à jour
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

# Optional cv2 dependency with fallback
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

from .s12_patch_segmenter import ImagePatch, SegmentationResult, PatchType
from ..s0_navigation.s03_coordinate_converter import CoordinateConverter, GridBounds
from ..s3_tensor.tensor_grid import TensorGrid, CellSymbol


class MetadataType(Enum):
    """Types de métadonnées extraites"""
    COORDINATES = "coordinates"           # Coordonnées grille
    QUALITY = "quality"                   # Qualité du patch
    CONTEXT = "context"                   # Contexte spatial/temporel
    CONFIDENCE = "confidence"             # Confiance de reconnaissance
    TEMPORAL = "temporal"                 # Informations temporelles


@dataclass
class CellMetadata:
    """Métadonnées complètes pour une cellule"""
    grid_coordinates: Tuple[int, int]
    screen_coordinates: Tuple[int, int]
    canvas_coordinates: Tuple[float, float]
    
    # Qualité et confiance
    quality_score: float
    confidence: float
    variance: float
    edge_strength: float
    
    # Contexte
    neighbor_count: int
    distance_to_center: float
    is_frontier_candidate: bool
    
    # Temporel
    timestamp: float
    capture_sequence: int
    
    # Métadonnées étendues
    patch_id: str
    metadata_type: List[MetadataType]
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_tensor_grid_format(self) -> Dict[str, Any]:
        """Convertit au format TensorGrid"""
        return {
            'symbol': CellSymbol.UNKNOWN,  # Sera déterminé par S2
            'confidence': self.confidence,
            'quality': self.quality_score,
            'coordinates': self.grid_coordinates,
            'timestamp': self.timestamp,
            'metadata': {
                'variance': self.variance,
                'edge_strength': self.edge_strength,
                'neighbor_count': self.neighbor_count,
                'is_frontier': self.is_frontier_candidate
            }
        }


@dataclass
class ExtractionResult:
    """Résultat de l'extraction de métadonnées"""
    success: bool
    cell_metadata: List[CellMetadata]
    extraction_time: float
    metadata_summary: Dict[str, Any]
    
    def get_high_quality_cells(self, threshold: float = 0.7) -> List[CellMetadata]:
        """Retourne les cellules de haute qualité"""
        return [m for m in self.cell_metadata if m.quality_score >= threshold]
    
    def get_frontier_candidates(self) -> List[CellMetadata]:
        """Retourne les candidates à la frontière"""
        return [m for m in self.cell_metadata if m.is_frontier_candidate]


class MetadataExtractor:
    """
    Extracteur de métadonnées pour les patches d'images
    
    Fonctionnalités:
    - Extraction de coordonnées précises
    - Analyse de qualité des patches
    - Calcul de métriques de confiance
    - Enrichissement contextuel et temporel
    """
    
    def __init__(self, coordinate_converter: CoordinateConverter,
                 quality_threshold: float = 0.5,
                 enable_context_analysis: bool = True,
                 enable_temporal_tracking: bool = True):
        """
        Initialise l'extracteur de métadonnées
        
        Args:
            coordinate_converter: Convertisseur de coordonnées S0
            quality_threshold: Seuil de qualité minimum
            enable_context_analysis: Activer l'analyse contextuelle
            enable_temporal_tracking: Activer le suivi temporel
        """
        # Dépendances
        self.coordinate_converter = coordinate_converter
        
        # Configuration
        self.quality_threshold = quality_threshold
        self.enable_context_analysis = enable_context_analysis
        self.enable_temporal_tracking = enable_temporal_tracking
        
        # État et suivi
        self._capture_sequence: int = 0
        self._cell_history: Dict[Tuple[int, int], List[CellMetadata]] = {}
        self._last_extraction_time: float = 0.0
        
        # Cache et optimisations
        self._quality_cache: Dict[str, float] = {}
        self._cache_max_size: int = 1000
        
        # Statistiques
        self._stats = {
            'extractions_performed': 0,
            'total_cells_processed': 0,
            'high_quality_cells': 0,
            'frontier_candidates': 0,
            'average_extraction_time': 0.0
        }
    
    def extract_metadata(self, segmentation_result: SegmentationResult) -> ExtractionResult:
        """
        Extrait les métadonnées d'un résultat de segmentation
        
        Args:
            segmentation_result: Résultat de la segmentation S1.2
            
        Returns:
            Résultat de l'extraction de métadonnées
        """
        start_time = time.time()
        
        try:
            if not segmentation_result.success or not segmentation_result.patches:
                return ExtractionResult(
                    success=False,
                    cell_metadata=[],
                    extraction_time=0.0,
                    metadata_summary={'error': 'No valid patches'}
                )
            
            # Extraire les métadonnées pour chaque patch
            all_metadata = []
            
            for patch in segmentation_result.patches:
                if patch.patch_type == PatchType.CELL_PATCH:
                    cell_metadata = self._extract_cell_metadata(patch, segmentation_result)
                    if cell_metadata:
                        all_metadata.append(cell_metadata)
            
            # Analyser le contexte si activé
            if self.enable_context_analysis:
                self._analyze_context(all_metadata, segmentation_result.viewport_bounds)
            
            # Mettre à jour le suivi temporel
            if self.enable_temporal_tracking:
                self._update_temporal_tracking(all_metadata)
            
            # Créer le résumé
            summary = self._create_metadata_summary(all_metadata)
            
            # Mettre à jour les statistiques
            extraction_time = time.time() - start_time
            self._update_stats(len(all_metadata), extraction_time)
            
            return ExtractionResult(
                success=True,
                cell_metadata=all_metadata,
                extraction_time=extraction_time,
                metadata_summary=summary
            )
            
        except Exception as e:
            return ExtractionResult(
                success=False,
                cell_metadata=[],
                extraction_time=time.time() - start_time,
                metadata_summary={'error': str(e)}
            )
    
    def extract_single_patch_metadata(self, patch: ImagePatch) -> Optional[CellMetadata]:
        """
        Extrait les métadonnées d'un patch individuel
        
        Args:
            patch: Patch d'image à analyser
            
        Returns:
            Métadonnées de la cellule ou None si échec
        """
        try:
            if patch.patch_type != PatchType.CELL_PATCH:
                return None
            
            # Extraction de base
            metadata = self._extract_cell_metadata(patch)
            
            if metadata and self.enable_context_analysis:
                # Analyse contextuelle simplifiée
                metadata.neighbor_count = 0  # Sera calculé avec plus de contexte
                metadata.distance_to_center = 0.0
            
            return metadata
            
        except Exception:
            return None
    
    def get_tensor_grid_updates(self, extraction_result: ExtractionResult) -> List[Dict[str, Any]]:
        """
        Convertit les métadonnées en mises à jour TensorGrid
        
        Args:
            extraction_result: Résultat de l'extraction
            
        Returns:
            Liste des mises à jour pour TensorGrid
        """
        if not extraction_result.success:
            return []
        
        updates = []
        
        for cell_metadata in extraction_result.cell_metadata:
            if cell_metadata.quality_score >= self.quality_threshold:
                update = cell_metadata.to_tensor_grid_format()
                updates.append(update)
        
        return updates
    
    def get_cell_history(self, grid_x: int, grid_y: int, 
                        max_entries: int = 10) -> List[CellMetadata]:
        """
        Retourne l'historique d'une cellule
        
        Args:
            grid_x, grid_y: Coordonnées grille
            max_entries: Nombre maximum d'entrées
            
        Returns:
            Historique des métadonnées
        """
        key = (grid_x, grid_y)
        history = self._cell_history.get(key, [])
        
        return history[-max_entries:] if history else []
    
    def _extract_cell_metadata(self, patch: ImagePatch,
                              segmentation_result: Optional[SegmentationResult] = None) -> Optional[CellMetadata]:
        """Extrait les métadonnées de base d'un patch"""
        try:
            # Coordonnées grille
            grid_coords = patch.get_center()
            
            # Coordonnées écran et canvas
            screen_coords = (
                patch.screen_bounds[0] + patch.screen_bounds[2] // 2,
                patch.screen_bounds[1] + patch.screen_bounds[3] // 2
            )
            
            canvas_coords = self.coordinate_converter.grid_to_canvas(*grid_coords)
            
            # Analyse de qualité
            quality_metrics = self._analyze_patch_quality(patch.image_data)
            
            # Créer les métadonnées
            metadata = CellMetadata(
                grid_coordinates=grid_coords,
                screen_coordinates=screen_coords,
                canvas_coordinates=canvas_coords,
                quality_score=quality_metrics['quality'],
                confidence=patch.confidence,
                variance=quality_metrics['variance'],
                edge_strength=quality_metrics['edge_strength'],
                neighbor_count=0,  # Sera calculé dans l'analyse contextuelle
                distance_to_center=0.0,  # Sera calculé dans l'analyse contextuelle
                is_frontier_candidate=False,  # Sera déterminé dans l'analyse contextuelle
                timestamp=time.time(),
                capture_sequence=self._capture_sequence,
                patch_id=patch.patch_id,
                metadata_type=[MetadataType.COORDINATES, MetadataType.QUALITY, MetadataType.CONFIDENCE],
                additional_data=patch.metadata.copy()
            )
            
            return metadata
            
        except Exception:
            return None
    
    def _analyze_patch_quality(self, patch_image: np.ndarray) -> Dict[str, float]:
        """Analyse la qualité d'un patch d'image"""
        try:
            # Convertir en niveaux de gris si nécessaire
            if len(patch_image.shape) == 3:
                gray = cv2.cvtColor(patch_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = patch_image
            
            # Calculer la variance
            variance = float(np.var(gray))
            
            # Calculer la force des contours
            edges = cv2.Canny(gray, 50, 150)
            edge_strength = float(np.sum(edges > 0) / edges.size)
            
            # Calculer le score de qualité combiné
            # Variance élevée + contours forts = bonne qualité
            normalized_variance = min(1.0, variance / 1000.0)
            quality = (normalized_variance * 0.7 + edge_strength * 0.3)
            
            return {
                'quality': quality,
                'variance': variance,
                'edge_strength': edge_strength
            }
            
        except Exception:
            return {
                'quality': 0.0,
                'variance': 0.0,
                'edge_strength': 0.0
            }
    
    def _analyze_context(self, cell_metadata: List[CellMetadata],
                        viewport_bounds: GridBounds) -> None:
        """Analyse le contexte spatial des cellules"""
        if not cell_metadata:
            return
        
        # Calculer le centre du viewport
        center_x = (viewport_bounds.x_min + viewport_bounds.x_max) // 2
        center_y = (viewport_bounds.y_min + viewport_bounds.y_max) // 2
        
        # Analyser chaque cellule
        for metadata in cell_metadata:
            grid_x, grid_y = metadata.grid_coordinates
            
            # Distance au centre
            metadata.distance_to_center = np.sqrt(
                (grid_x - center_x) ** 2 + (grid_y - center_y) ** 2
            )
            
            # Compter les voisins (cellules adjacentes)
            neighbors = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    
                    neighbor_x, neighbor_y = grid_x + dx, grid_y + dy
                    
                    # Vérifier si un voisin existe dans les métadonnées
                    for other in cell_metadata:
                        if other.grid_coordinates == (neighbor_x, neighbor_y):
                            neighbors += 1
                            break
            
            metadata.neighbor_count = neighbors
            
            # Déterminer si c'est une candidate à la frontière
            # (basse qualité, peu de voisins, loin du centre)
            metadata.is_frontier_candidate = (
                metadata.quality_score < 0.6 and
                neighbors < 4 and
                metadata.distance_to_center > 5
            )
            
            # Ajouter le type de métadonnées contextuelles
            if MetadataType.CONTEXT not in metadata.metadata_type:
                metadata.metadata_type.append(MetadataType.CONTEXT)
    
    def _update_temporal_tracking(self, cell_metadata: List[CellMetadata]) -> None:
        """Met à jour le suivi temporel des cellules"""
        self._capture_sequence += 1
        
        for metadata in cell_metadata:
            key = metadata.grid_coordinates
            
            # Ajouter à l'historique
            if key not in self._cell_history:
                self._cell_history[key] = []
            
            self._cell_history[key].append(metadata)
            
            # Limiter l'historique
            if len(self._cell_history[key]) > 50:
                self._cell_history[key] = self._cell_history[key][-25:]
            
            # Ajouter le type de métadonnées temporelles
            if MetadataType.TEMPORAL not in metadata.metadata_type:
                metadata.metadata_type.append(MetadataType.TEMPORAL)
        
        self._last_extraction_time = time.time()
    
    def _create_metadata_summary(self, cell_metadata: List[CellMetadata]) -> Dict[str, Any]:
        """Crée un résumé des métadonnées extraites"""
        if not cell_metadata:
            return {'total_cells': 0}
        
        # Statistiques de qualité
        qualities = [m.quality_score for m in cell_metadata]
        confidences = [m.confidence for m in cell_metadata]
        
        high_quality_count = sum(1 for q in qualities if q >= self.quality_threshold)
        frontier_count = sum(1 for m in cell_metadata if m.is_frontier_candidate)
        
        return {
            'total_cells': len(cell_metadata),
            'high_quality_cells': high_quality_count,
            'frontier_candidates': frontier_count,
            'average_quality': np.mean(qualities),
            'average_confidence': np.mean(confidences),
            'quality_distribution': {
                'low': sum(1 for q in qualities if q < 0.3),
                'medium': sum(1 for q in qualities if 0.3 <= q < 0.7),
                'high': sum(1 for q in qualities if q >= 0.7)
            },
            'capture_sequence': self._capture_sequence
        }
    
    def _update_stats(self, cells_count: int, extraction_time: float) -> None:
        """Met à jour les statistiques"""
        self._stats['extractions_performed'] += 1
        self._stats['total_cells_processed'] += cells_count
        
        # Mettre à jour le temps moyen
        total_extractions = self._stats['extractions_performed']
        current_avg = self._stats['average_extraction_time']
        self._stats['average_extraction_time'] = (
            (current_avg * (total_extractions - 1) + extraction_time) / total_extractions
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de l'extracteur"""
        stats = self._stats.copy()
        stats.update({
            'capture_sequence': self._capture_sequence,
            'tracked_cells': len(self._cell_history),
            'cache_size': len(self._quality_cache),
            'configuration': {
                'quality_threshold': self.quality_threshold,
                'context_analysis': self.enable_context_analysis,
                'temporal_tracking': self.enable_temporal_tracking
            }
        })
        return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        self._stats = {
            'extractions_performed': 0,
            'total_cells_processed': 0,
            'high_quality_cells': 0,
            'frontier_candidates': 0,
            'average_extraction_time': 0.0
        }
        self._capture_sequence = 0
    
    def clear_history(self) -> None:
        """Efface l'historique des cellules"""
        self._cell_history.clear()
        self._quality_cache.clear()
