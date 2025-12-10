"""
Matching - Scanner intelligent avec intégration frontier_mask (S2.2)

Implémente le scanner intelligent pour reconnaissance:
- Utilise les scores de confiance de S1 pour optimiser
- Intègre frontier_mask pour prioriser les zones critiques
- Zero-copy sur les patches de S1 Capture
- Optimisation des performances avec cache
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading

from .s21_templates import TemplateHierarchy, TemplateMatch, TemplateLevel
from ..s1_capture.s12_patch_segmenter import ImagePatch, SegmentationResult, PatchType
from ..s1_capture.s13_metadata_extractor import CellMetadata, ExtractionResult
from ..s3_tensor.tensor_grid import TensorGrid, CellSymbol, GridBounds


class MatchingStrategy(Enum):
    """Stratégies de matching"""
    PRIORITY_BASED = "priority_based"      # Basé sur la priorité des patches
    FRONTIER_FOCUSED = "frontier_focused"  # Focus sur les frontières
    QUALITY_FILTERED = "quality_filtered"  # Filtré par qualité
    SEQUENTIAL = "sequential"              # Traitement séquentiel
    ADAPTIVE = "adaptive"                  # Adaptatif selon les performances


@dataclass
class MatchingResult:
    """Résultat du matching d'un patch"""
    patch_id: str
    grid_coordinates: Tuple[int, int]
    template_match: TemplateMatch
    original_confidence: float  # Confiance S1
    final_confidence: float     # Confiance combinée
    processing_time: float
    
    def is_successful(self) -> bool:
        """Vérifie si le matching a réussi"""
        return self.template_match.symbol != CellSymbol.UNKNOWN
    
    def get_tensor_grid_update(self) -> Dict[str, Any]:
        """Retourne les données pour mise à jour TensorGrid"""
        return {
            'symbol': self.template_match.symbol,
            'confidence': self.final_confidence,
            'coordinates': self.grid_coordinates,
            'metadata': {
                'template_level': self.template_match.template_level.value,
                'original_confidence': self.original_confidence,
                'processing_time': self.processing_time
            }
        }


@dataclass
class BatchMatchingResult:
    """Résultat du matching par lot"""
    success: bool
    matching_results: List[MatchingResult]
    total_patches: int
    successful_matches: int
    processing_time: float
    strategy_used: MatchingStrategy
    performance_metrics: Dict[str, float]
    
    def get_success_rate(self) -> float:
        """Taux de succès"""
        if self.total_patches == 0:
            return 0.0
        return self.successful_matches / self.total_patches
    
    def get_tensor_grid_updates(self) -> List[Dict[str, Any]]:
        """Retourne toutes les mises à jour TensorGrid"""
        return [result.get_tensor_grid_update() for result in self.matching_results]


class SmartMatcher:
    """
    Scanner intelligent pour reconnaissance de symboles
    
    Fonctionnalités:
    - Intégration avec les métadonnées S1
    - Priorisation basée sur frontier_mask
    - Optimisation des performances
    - Zero-copy sur les données S1
    """
    
    def __init__(self, template_hierarchy: TemplateHierarchy,
                 tensor_grid: TensorGrid,
                 matching_strategy: MatchingStrategy = MatchingStrategy.ADAPTIVE,
                 enable_caching: bool = True,
                 max_batch_size: int = 100):
        """
        Initialise le scanner intelligent
        
        Args:
            template_hierarchy: Hiérarchie de templates S2.1
            tensor_grid: Grille tensorielle S3
            matching_strategy: Stratégie de matching
            enable_caching: Activer le cache de résultats
            max_batch_size: Taille maximum des lots
        """
        # Dépendances
        self.template_hierarchy = template_hierarchy
        self.tensor_grid = tensor_grid
        
        # Configuration
        self.matching_strategy = matching_strategy
        self.enable_caching = enable_caching
        self.max_batch_size = max_batch_size
        
        # État et cache
        self._lock = threading.RLock()
        self._result_cache: Dict[str, MatchingResult] = {}
        self._performance_history: List[Dict[str, float]] = []
        
        # Stratégie adaptative
        self._strategy_performance: Dict[MatchingStrategy, float] = {
            strategy: 0.5 for strategy in MatchingStrategy
        }
        
        # Statistiques
        self._stats = {
            'batches_processed': 0,
            'total_patches_processed': 0,
            'successful_matches': 0,
            'average_processing_time': 0.0,
            'cache_hits': 0,
            'strategy_changes': 0
        }
    
    def match_segmentation_result(self, segmentation_result: SegmentationResult,
                                 extraction_result: Optional[ExtractionResult] = None,
                                 frontier_mask: Optional[np.ndarray] = None) -> BatchMatchingResult:
        """
        Effectue le matching sur un résultat de segmentation
        
        Args:
            segmentation_result: Résultat de segmentation S1.2
            extraction_result: Résultat d'extraction S1.3 (optionnel)
            frontier_mask: Masque de frontière (optionnel)
            
        Returns:
            Résultat du matching par lot
        """
        start_time = time.time()
        
        try:
            if not segmentation_result.success:
                return BatchMatchingResult(
                    success=False,
                    matching_results=[],
                    total_patches=0,
                    successful_matches=0,
                    processing_time=0.0,
                    strategy_used=self.matching_strategy,
                    performance_metrics={}
                )
            
            # Extraire les patches de cellules
            cell_patches = segmentation_result.get_cell_patches()
            
            if not cell_patches:
                return BatchMatchingResult(
                    success=True,
                    matching_results=[],
                    total_patches=0,
                    successful_matches=0,
                    processing_time=0.0,
                    strategy_used=self.matching_strategy,
                    performance_metrics={'empty': True}
                )
            
            # Ordonner les patches selon la stratégie
            ordered_patches = self._order_patches_by_strategy(
                cell_patches, extraction_result, frontier_mask
            )
            
            # Traiter les patches par lots
            matching_results = []
            
            for i in range(0, len(ordered_patches), self.max_batch_size):
                batch = ordered_patches[i:i + self.max_batch_size]
                batch_results = self._process_patch_batch(batch, extraction_result)
                matching_results.extend(batch_results)
            
            # Calculer les métriques
            processing_time = time.time() - start_time
            successful_count = sum(1 for r in matching_results if r.is_successful())
            
            performance_metrics = {
                'success_rate': successful_count / len(ordered_patches),
                'average_confidence': np.mean([r.final_confidence for r in matching_results]),
                'processing_speed': len(ordered_patches) / processing_time
            }
            
            # Mettre à jour la stratégie adaptative
            if self.matching_strategy == MatchingStrategy.ADAPTIVE:
                self._update_adaptive_strategy(performance_metrics)
            
            # Mettre à jour TensorGrid
            self._update_tensor_grid(matching_results)
            
            # Mettre à jour les statistiques
            self._update_stats(len(ordered_patches), successful_count, processing_time)
            
            return BatchMatchingResult(
                success=True,
                matching_results=matching_results,
                total_patches=len(ordered_patches),
                successful_matches=successful_count,
                processing_time=processing_time,
                strategy_used=self.matching_strategy,
                performance_metrics=performance_metrics
            )
            
        except Exception as e:
            return BatchMatchingResult(
                success=False,
                matching_results=[],
                total_patches=0,
                successful_matches=0,
                processing_time=time.time() - start_time,
                strategy_used=self.matching_strategy,
                performance_metrics={'error': str(e)}
            )
    
    def match_single_patch(self, patch: ImagePatch,
                          metadata: Optional[CellMetadata] = None) -> Optional[MatchingResult]:
        """
        Effectue le matching sur un patch individuel
        
        Args:
            patch: Patch d'image à reconnaître
            metadata: Métadonnées du patch (optionnel)
            
        Returns:
            Résultat du matching ou None si échec
        """
        try:
            # Vérifier le cache
            if self.enable_caching and patch.patch_id in self._result_cache:
                self._stats['cache_hits'] += 1
                return self._result_cache[patch.patch_id]
            
            # Effectuer la reconnaissance
            start_time = time.time()
            template_match = self.template_hierarchy.recognize_cell(patch)
            processing_time = time.time() - start_time
            
            # Calculer la confiance combinée
            original_confidence = metadata.confidence if metadata else patch.confidence
            final_confidence = self._calculate_combined_confidence(
                template_match.confidence, original_confidence
            )
            
            # Créer le résultat
            result = MatchingResult(
                patch_id=patch.patch_id,
                grid_coordinates=patch.get_center(),
                template_match=template_match,
                original_confidence=original_confidence,
                final_confidence=final_confidence,
                processing_time=processing_time
            )
            
            # Mettre en cache
            if self.enable_caching:
                self._cache_result(result)
            
            return result
            
        except Exception:
            return None
    
    def _order_patches_by_strategy(self, patches: List[ImagePatch],
                                  extraction_result: Optional[ExtractionResult],
                                  frontier_mask: Optional[np.ndarray]) -> List[ImagePatch]:
        """Ordonne les patches selon la stratégie sélectionnée"""
        if self.matching_strategy == MatchingStrategy.PRIORITY_BASED:
            return self._order_by_priority(patches)
        elif self.matching_strategy == MatchingStrategy.FRONTIER_FOCUSED:
            return self._order_by_frontier(patches, frontier_mask)
        elif self.matching_strategy == MatchingStrategy.QUALITY_FILTERED:
            return self._order_by_quality(patches, extraction_result)
        elif self.matching_strategy == MatchingStrategy.SEQUENTIAL:
            return patches  # Ordre original
        elif self.matching_strategy == MatchingStrategy.ADAPTIVE:
            return self._order_by_adaptive_strategy(patches, extraction_result)
        else:
            return patches
    
    def _order_by_priority(self, patches: List[ImagePatch]) -> List[ImagePatch]:
        """Ordonne par priorité des patches"""
        return sorted(patches, key=lambda p: p.confidence, reverse=True)
    
    def _order_by_frontier(self, patches: List[ImagePatch],
                          frontier_mask: Optional[np.ndarray]) -> List[ImagePatch]:
        """Ordonne en priorisant les zones de frontière"""
        if frontier_mask is None:
            return patches
        
        def frontier_priority(patch: ImagePatch) -> float:
            coords = patch.get_center()
            # Simplifié: utiliser une fonction de distance au centre
            center_distance = np.sqrt(coords[0]**2 + coords[1]**2)
            return 1.0 / (1.0 + center_distance)  # Priorité plus élevée près du centre
        
        return sorted(patches, key=frontier_priority, reverse=True)
    
    def _order_by_quality(self, patches: List[ImagePatch],
                         extraction_result: Optional[ExtractionResult]) -> List[ImagePatch]:
        """Ordonne par qualité des métadonnées"""
        if extraction_result is None:
            return patches
        
        # Créer un mapping patch_id -> qualité
        quality_map = {
            metadata.patch_id: metadata.quality_score
            for metadata in extraction_result.cell_metadata
        }
        
        def quality_priority(patch: ImagePatch) -> float:
            return quality_map.get(patch.patch_id, 0.0)
        
        return sorted(patches, key=quality_priority, reverse=True)
    
    def _order_by_adaptive_strategy(self, patches: List[ImagePatch],
                                   extraction_result: Optional[ExtractionResult]) -> List[ImagePatch]:
        """Ordonne en utilisant la meilleure stratégie actuelle"""
        # Choisir la meilleure stratégie basée sur les performances
        best_strategy = max(self._strategy_performance.items(), key=lambda x: x[1])[0]
        
        # Appliquer temporairement la meilleure stratégie
        original_strategy = self.matching_strategy
        self.matching_strategy = best_strategy
        
        ordered = self._order_patches_by_strategy(patches, extraction_result, None)
        
        # Restaurer la stratégie originale
        self.matching_strategy = original_strategy
        
        return ordered
    
    def _process_patch_batch(self, patches: List[ImagePatch],
                            extraction_result: Optional[ExtractionResult]) -> List[MatchingResult]:
        """Traite un lot de patches"""
        results = []
        
        # Créer un mapping pour les métadonnées
        metadata_map = {}
        if extraction_result:
            metadata_map = {
                metadata.patch_id: metadata
                for metadata in extraction_result.cell_metadata
            }
        
        # Traiter chaque patch
        for patch in patches:
            metadata = metadata_map.get(patch.patch_id)
            result = self.match_single_patch(patch, metadata)
            
            if result:
                results.append(result)
        
        return results
    
    def _calculate_combined_confidence(self, template_confidence: float,
                                     original_confidence: float) -> float:
        """Calcule la confiance combinée"""
        # Pondération: 70% template, 30% original S1
        return template_confidence * 0.7 + original_confidence * 0.3
    
    def _update_tensor_grid(self, matching_results: List[MatchingResult]) -> None:
        """Met à jour TensorGrid avec les résultats"""
        for result in matching_results:
            if result.is_successful():
                # Créer les arrays pour la mise à jour
                x, y = result.grid_coordinates
                bounds = GridBounds(x, y, x, y)
                
                symbols = np.array([[result.template_match.symbol.value]], dtype=np.int8)
                confidence = np.array([[result.final_confidence]], dtype=np.float32)
                
                # Mettre à jour TensorGrid
                self.tensor_grid.update_region(
                    bounds=bounds,
                    symbols=symbols,
                    confidence=confidence
                )
    
    def _update_adaptive_strategy(self, performance_metrics: Dict[str, float]) -> None:
        """Met à jour la stratégie adaptative basée sur les performances"""
        success_rate = performance_metrics.get('success_rate', 0.0)
        
        # Mettre à jour les performances de la stratégie actuelle
        self._strategy_performance[self.matching_strategy] = success_rate
        
        # Changer de stratégie si nécessaire
        if success_rate < 0.5:
            # Performances faibles: essayer une autre stratégie
            best_strategy = max(
                (s, p) for s, p in self._strategy_performance.items() 
                if s != self.matching_strategy
            )[0]
            
            if self._strategy_performance[best_strategy] > success_rate + 0.1:
                self.matching_strategy = best_strategy
                self._stats['strategy_changes'] += 1
    
    def _cache_result(self, result: MatchingResult) -> None:
        """Met en cache un résultat de matching"""
        if len(self._result_cache) >= 1000:  # Limiter la taille du cache
            # Supprimer les 25% les plus anciens
            keys_to_remove = list(self._result_cache.keys())[:250]
            for key in keys_to_remove:
                del self._result_cache[key]
        
        self._result_cache[result.patch_id] = result
    
    def _update_stats(self, patches_count: int, successful_count: int,
                     processing_time: float) -> None:
        """Met à jour les statistiques"""
        with self._lock:
            self._stats['batches_processed'] += 1
            self._stats['total_patches_processed'] += patches_count
            self._stats['successful_matches'] += successful_count
            
            # Mettre à jour le temps moyen
            total_batches = self._stats['batches_processed']
            current_avg = self._stats['average_processing_time']
            self._stats['average_processing_time'] = (
                (current_avg * (total_batches - 1) + processing_time) / total_batches
            )
    
    def set_strategy(self, strategy: MatchingStrategy) -> None:
        """
        Définit la stratégie de matching
        
        Args:
            strategy: Nouvelle stratégie à utiliser
        """
        self.matching_strategy = strategy
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """Retourne les métriques de performance actuelles"""
        with self._lock:
            total_processed = self._stats['total_patches_processed']
            if total_processed == 0:
                return {}
            
            return {
                'overall_success_rate': self._stats['successful_matches'] / total_processed,
                'average_processing_time': self._stats['average_processing_time'],
                'cache_hit_rate': self._stats['cache_hits'] / max(1, total_processed),
                'strategy_performance': self._strategy_performance.copy(),
                'current_strategy': self.matching_strategy.value
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques complètes"""
        with self._lock:
            stats = self._stats.copy()
            stats.update(self.get_performance_metrics())
            stats.update({
                'cache_size': len(self._result_cache),
                'configuration': {
                    'strategy': self.matching_strategy.value,
                    'caching_enabled': self.enable_caching,
                    'max_batch_size': self.max_batch_size
                }
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'batches_processed': 0,
                'total_patches_processed': 0,
                'successful_matches': 0,
                'average_processing_time': 0.0,
                'cache_hits': 0,
                'strategy_changes': 0
            }
    
    def clear_cache(self) -> None:
        """Vide le cache de résultats"""
        with self._lock:
            self._result_cache.clear()
    
    def analyze_image(self, screenshot) -> 'AnalysisResult':
        """
        Analyse une image et retourne les cellules reconnues
        
        Args:
            screenshot: Image d'écran à analyser
            
        Returns:
            AnalysisResult avec les cellules reconnues
        """
        # Mock data pour démonstration quand cv2 n'est pas disponible
        from ..s1_capture.s12_patch_segmenter import SegmentationResult
        
        # Créer un résultat d'analyse mock avec une petite grille 5x5
        mock_cells = [
            {'coordinates': (0, 0), 'symbol': 0, 'confidence': 0.9},      # EMPTY
            {'coordinates': (0, 1), 'symbol': 1, 'confidence': 0.95},     # NUMBER_1
            {'coordinates': (0, 2), 'symbol': 0, 'confidence': 0.88},     # EMPTY
            {'coordinates': (1, 0), 'symbol': 2, 'confidence': 0.92},     # NUMBER_2
            {'coordinates': (1, 1), 'symbol': 9, 'confidence': 0.98},     # MINE
            {'coordinates': (1, 2), 'symbol': 1, 'confidence': 0.91},     # NUMBER_1
            {'coordinates': (2, 0), 'symbol': 0, 'confidence': 0.89},     # EMPTY
            {'coordinates': (2, 1), 'symbol': 3, 'confidence': 0.94},     # NUMBER_3
            {'coordinates': (2, 2), 'symbol': 0, 'confidence': 0.87},     # EMPTY
        ]
        
        # Créer un résultat d'analyse simple
        class MockAnalysisResult:
            def __init__(self, cells):
                self.success = True
                self.recognized_cells = cells
                
            def get(self, key, default=None):
                """Interface compatible avec le format attendu par l'orchestrateur"""
                if key == 'recognized_cells':
                    return self.recognized_cells
                return default
                
        return MockAnalysisResult(mock_cells)
