"""
PathPlanner - Planification de trajectoire basée sur densité (S6.2)

Génère les vecteurs de mouvement pour S0 Navigation:
- Barycentre de priorité à partir des zones chaudes
- Stratégie "sliding window" pour déplacements progressifs
- Optimisation de trajectoire pour minimiser les mouvements
- Intégration avec feedback S5 (état des zones résolues/bloquées)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading
import math

from .s61_density_analyzer import DensityAnalyzer, DensityMap, RegionDensity
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds
from ..s3_tensor.hint_cache import HintCache


class MovementStrategy(Enum):
    """Stratégies de mouvement"""
    BARYCENTER = "barycenter"  # Se déplacer vers le centre de masse
    HIGHEST_DENSITY = "highest_density"  # Se déplacer vers le point le plus dense
    SLIDING_WINDOW = "sliding_window"  # Fenêtre glissante progressive
    ADAPTIVE = "adaptive"  # Adaptatif selon l'état de la grille


class PathPriority(Enum):
    """Priorités de déplacement"""
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.9
    CRITICAL = 1.0


@dataclass
class MovementVector:
    """Vecteur de mouvement pour S0 Navigation"""
    dx: int  # Déplacement en X (pixels ou cellules)
    dy: int  # Déplacement en Y (pixels ou cellules)
    priority: PathPriority
    reasoning: str
    target_bounds: Optional[GridBounds] = None
    estimated_distance: float = 0.0
    
    def magnitude(self) -> float:
        """Calcule la magnitude du vecteur"""
        return math.sqrt(self.dx ** 2 + self.dy ** 2)
    
    def direction(self) -> float:
        """Calcule la direction en radians (0 = Est, π/2 = Nord)"""
        return math.atan2(-self.dy, self.dx)  # dy négatif pour axes écran


@dataclass
class PathPlan:
    """Plan de trajectoire complet"""
    current_vector: MovementVector
    alternative_vectors: List[MovementVector]
    target_regions: List[RegionDensity]
    estimated_steps: int
    confidence: float
    metadata: Dict[str, Any]
    
    def get_best_vector(self) -> MovementVector:
        """Retourne le meilleur vecteur de mouvement"""
        return max([self.current_vector] + self.alternative_vectors, 
                  key=lambda v: v.priority.value)


class PathPlanner:
    """
    Planificateur de trajectoire pour le pathfinding
    
    Fonctionnalités:
    - Calcul de barycentre de priorité
    - Stratégie sliding window pour déplacements progressifs
    - Optimisation de trajectoire
    - Intégration avec feedback S5
    """
    
    def __init__(self, density_analyzer: DensityAnalyzer, tensor_grid: TensorGrid,
                 hint_cache: HintCache, strategy: MovementStrategy = MovementStrategy.SLIDING_WINDOW,
                 max_step_size: Tuple[int, int] = (50, 50),
                 min_movement_threshold: float = 5.0):
        """
        Initialise le planificateur de trajectoire
        
        Args:
            density_analyzer: Analyseur de densité pour les données
            tensor_grid: Grille tensorielle pour contexte
            hint_cache: Cache d'indices pour optimisations
            strategy: Stratégie de mouvement par défaut
            max_step_size: Taille maximale d'un pas (dx, dy)
            min_movement_threshold: Seuil minimum pour considérer un mouvement
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.density_analyzer = density_analyzer
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.strategy = strategy
        self.max_step_size = max_step_size
        self.min_movement_threshold = min_movement_threshold
        
        # État interne
        self._last_position: Optional[Tuple[int, int]] = None
        self._current_target: Optional[GridBounds] = None
        self._path_history: List[MovementVector] = []
        
        # Feedback S5
        self._resolved_zones: List[GridBounds] = []
        self._blocked_zones: List[GridBounds] = []
        self._critical_zones: List[GridBounds] = []
        
        # Statistiques
        self._stats = {
            'plans_generated': 0,
            'total_distance_traveled': 0.0,
            'strategy_switches': 0,
            'average_plan_confidence': 0.0,
            'blocked_zone_avoidances': 0
        }
    
    def plan_next_movement(self, current_position: Optional[Tuple[int, int]] = None,
                           strategy_override: Optional[MovementStrategy] = None) -> PathPlan:
        """
        Planifie le prochain mouvement basé sur l'analyse de densité
        
        Args:
            current_position: Position actuelle (x, y)
            strategy_override: Forcer une stratégie spécifique
            
        Returns:
            Plan de trajectoire avec vecteurs et métadonnées
        """
        with self._lock:
            start_time = time.time()
            
            # Mettre à jour la position actuelle
            if current_position:
                self._last_position = current_position
            
            # Analyser la densité actuelle
            density_map = self.density_analyzer.analyze_density()
            
            # Choisir la stratégie
            current_strategy = strategy_override or self.strategy
            
            # Calculer le vecteur principal selon la stratégie
            main_vector = self._calculate_main_vector(density_map, current_strategy, current_position)
            
            # Calculer les vecteurs alternatifs
            alt_vectors = self._calculate_alternative_vectors(density_map, current_strategy)
            
            # Sélectionner les régions cibles
            target_regions = self._select_target_regions(density_map)
            
            # Estimer le nombre d'étapes
            estimated_steps = self._estimate_steps(main_vector, target_regions)
            
            # Calculer la confiance du plan
            confidence = self._calculate_plan_confidence(main_vector, density_map)
            
            # Créer le plan
            plan = PathPlan(
                current_vector=main_vector,
                alternative_vectors=alt_vectors,
                target_regions=target_regions,
                estimated_steps=estimated_steps,
                confidence=confidence,
                metadata={
                    'strategy': current_strategy.value,
                    'analysis_time': time.time() - start_time,
                    'hotspots_count': len(density_map.hotspots),
                    'target_regions_count': len(target_regions)
                }
            )
            
            # Mettre à jour l'état interne
            self._update_internal_state(plan)
            
            # Mettre à jour les statistiques
            self._update_stats(plan)
            
            return plan
    
    def _calculate_main_vector(self, density_map: DensityMap, 
                               strategy: MovementStrategy,
                               current_position: Optional[Tuple[int, int]]) -> MovementVector:
        """Calcule le vecteur de mouvement principal selon la stratégie"""
        
        if strategy == MovementStrategy.BARYCENTER:
            return self._calculate_barycenter_vector(density_map, current_position)
        elif strategy == MovementStrategy.HIGHEST_DENSITY:
            return self._calculate_highest_density_vector(density_map, current_position)
        elif strategy == MovementStrategy.SLIDING_WINDOW:
            return self._calculate_sliding_window_vector(density_map, current_position)
        elif strategy == MovementStrategy.ADAPTIVE:
            return self._calculate_adaptive_vector(density_map, current_position)
        else:
            return self._calculate_sliding_window_vector(density_map, current_position)
    
    def _calculate_barycenter_vector(self, density_map: DensityMap,
                                    current_position: Optional[Tuple[int, int]]) -> MovementVector:
        """Calcule le vecteur vers le barycentre des zones chaudes"""
        if not density_map.hotspots:
            return MovementVector(0, 0, PathPriority.LOW, "no_hotspots")
        
        # Calculer le barycentre pondéré
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        
        for x, y, density in density_map.hotspots:
            weight = density ** 2  # Pondération quadratique pour favoriser les points très denses
            weighted_x += x * weight
            weighted_y += y * weight
            total_weight += weight
        
        if total_weight == 0:
            return MovementVector(0, 0, PathPriority.LOW, "no_weight")
        
        target_x = weighted_x / total_weight
        target_y = weighted_y / total_weight
        
        # Calculer le vecteur de déplacement
        if current_position:
            dx = int(target_x - current_position[0])
            dy = int(target_y - current_position[1])
        else:
            # Pas de position actuelle, utiliser le centre de la grille
            grid_center_x = (density_map.global_bounds.x_min + density_map.global_bounds.x_max) // 2
            grid_center_y = (density_map.global_bounds.y_min + density_map.global_bounds.y_max) // 2
            dx = int(target_x - grid_center_x)
            dy = int(target_y - grid_center_y)
        
        # Limiter la taille du pas
        dx = np.clip(dx, -self.max_step_size[0], self.max_step_size[0])
        dy = np.clip(dy, -self.max_step_size[1], self.max_step_size[1])
        
        # Calculer la priorité
        magnitude = math.sqrt(dx ** 2 + dy ** 2)
        priority = self._calculate_movement_priority(magnitude, density_map)
        
        return MovementVector(
            dx=dx, dy=dy, priority=priority,
            reasoning=f"barycenter_to_{int(target_x)},{int(target_y)}",
            estimated_distance=magnitude
        )
    
    def _calculate_highest_density_vector(self, density_map: DensityMap,
                                         current_position: Optional[Tuple[int, int]]) -> MovementVector:
        """Calcule le vecteur vers le point de plus haute densité"""
        highest_point = density_map.get_highest_density_point()
        
        if not highest_point:
            return MovementVector(0, 0, PathPriority.LOW, "no_hotspots")
        
        target_x, target_y, density = highest_point
        
        # Calculer le vecteur de déplacement
        if current_position:
            dx = int(target_x - current_position[0])
            dy = int(target_y - current_position[1])
        else:
            grid_center_x = (density_map.global_bounds.x_min + density_map.global_bounds.x_max) // 2
            grid_center_y = (density_map.global_bounds.y_min + density_map.global_bounds.y_max) // 2
            dx = int(target_x - grid_center_x)
            dy = int(target_y - grid_center_y)
        
        # Limiter la taille du pas
        dx = np.clip(dx, -self.max_step_size[0], self.max_step_size[0])
        dy = np.clip(dy, -self.max_step_size[1], self.max_step_size[1])
        
        # Priorité basée sur la densité
        priority = PathPriority.HIGH if density > 0.8 else PathPriority.MEDIUM
        
        return MovementVector(
            dx=dx, dy=dy, priority=priority,
            reasoning=f"highest_density_{density:.3f}_at_{int(target_x)},{int(target_y)}",
            estimated_distance=math.sqrt(dx ** 2 + dy ** 2)
        )
    
    def _calculate_sliding_window_vector(self, density_map: DensityMap,
                                        current_position: Optional[Tuple[int, int]]) -> MovementVector:
        """Calcule le vecteur avec stratégie de fenêtre glissante"""
        if not current_position:
            return self._calculate_barycenter_vector(density_map, current_position)
        
        # Définir la fenêtre glissante autour de la position actuelle
        window_size = (self.max_step_size[0] * 2, self.max_step_size[1] * 2)
        window_bounds = GridBounds(
            x_min=current_position[0] - window_size[0] // 2,
            y_min=current_position[1] - window_size[1] // 2,
            x_max=current_position[0] + window_size[0] // 2,
            y_max=current_position[1] + window_size[1] // 2
        )
        
        # Trouver les zones chaudes dans la fenêtre
        window_hotspots = [
            (x, y, d) for x, y, d in density_map.hotspots
            if (window_bounds.x_min <= x <= window_bounds.x_max and
                window_bounds.y_min <= y <= window_bounds.y_max)
        ]
        
        if not window_hotspots:
            # Pas de zones chaudes dans la fenêtre, chercher plus loin
            return self._calculate_barycenter_vector(density_map, current_position)
        
        # Choisir la zone chaude la plus proche et la plus dense
        best_hotspot = None
        best_score = -1.0
        
        for x, y, density in window_hotspots:
            distance = math.sqrt((x - current_position[0]) ** 2 + (y - current_position[1]) ** 2)
            # Score: densité élevée et distance modérée
            score = density / (1.0 + distance / 20.0)
            
            if score > best_score:
                best_score = score
                best_hotspot = (x, y, density)
        
        if not best_hotspot:
            return MovementVector(0, 0, PathPriority.LOW, "no_best_hotspot")
        
        target_x, target_y, density = best_hotspot
        dx = int(target_x - current_position[0])
        dy = int(target_y - current_position[1])
        
        # Limiter la taille du pas (plus petit pour sliding window)
        dx = np.clip(dx, -self.max_step_size[0] // 2, self.max_step_size[0] // 2)
        dy = np.clip(dy, -self.max_step_size[1] // 2, self.max_step_size[1] // 2)
        
        # Priorité élevée pour les mouvements ciblés
        priority = PathPriority.HIGH if density > 0.6 else PathPriority.MEDIUM
        
        return MovementVector(
            dx=dx, dy=dy, priority=priority,
            reasoning=f"sliding_window_to_{int(target_x)},{int(target_y)}_density_{density:.3f}",
            estimated_distance=math.sqrt(dx ** 2 + dy ** 2)
        )
    
    def _calculate_adaptive_vector(self, density_map: DensityMap,
                                  current_position: Optional[Tuple[int, int]]) -> MovementVector:
        """Calcule le vecteur avec stratégie adaptative"""
        # Analyser l'état actuel pour choisir la meilleure stratégie
        global_stats = density_map.global_stats
        
        # Si beaucoup de zones chaudes proches, utiliser sliding window
        if global_stats.get('frontier_ratio', 0) > 0.3:
            return self._calculate_sliding_window_vector(density_map, current_position)
        
        # Si peu de zones mais très denses, viser la plus haute densité
        elif len(density_map.hotspots) < 5 and global_stats.get('max_density', 0) > 0.8:
            return self._calculate_highest_density_vector(density_map, current_position)
        
        # Sinon, utiliser le barycentre
        else:
            return self._calculate_barycenter_vector(density_map, current_position)
    
    def _calculate_alternative_vectors(self, density_map: DensityMap,
                                      strategy: MovementStrategy) -> List[MovementVector]:
        """Calcule des vecteurs de mouvement alternatifs"""
        alternatives = []
        
        # Ajouter le vecteur vers le deuxième meilleur point chaud
        if len(density_map.hotspots) >= 2:
            sorted_hotspots = sorted(density_map.hotspots, key=lambda h: h[2], reverse=True)
            second_best = sorted_hotspots[1]
            
            # Vecteur vers le deuxième meilleur (simplifié)
            dx = int(second_best[0] - (density_map.global_bounds.x_min + density_map.global_bounds.x_max) // 2)
            dy = int(second_best[1] - (density_map.global_bounds.y_min + density_map.global_bounds.y_max) // 2)
            
            alternatives.append(MovementVector(
                dx=dx, dy=dy, priority=PathPriority.MEDIUM,
                reasoning=f"alternative_to_second_best_{int(second_best[0])},{int(second_best[1])}"
            ))
        
        # Ajouter un vecteur de "recherche" si peu de zones chaudes
        if len(density_map.hotspots) < 3:
            # Mouvement exploratoire en spirale
            angle = (len(self._path_history) * 45) % 360
            dx = int(30 * math.cos(math.radians(angle)))
            dy = int(30 * math.sin(math.radians(angle)))
            
            alternatives.append(MovementVector(
                dx=dx, dy=dy, priority=PathPriority.LOW,
                reasoning=f"exploratory_spiral_angle_{angle}"
            ))
        
        return alternatives
    
    def _select_target_regions(self, density_map: DensityMap) -> List[RegionDensity]:
        """Sélectionne les régions cibles prioritaires"""
        # Filtrer les régions en excluant les zones bloquées
        valid_regions = []
        
        for region in density_map.regions:
            # Vérifier si la région n'est pas dans les zones bloquées
            is_blocked = any(self._bounds_overlap(region.bounds, blocked) 
                           for blocked in self._blocked_zones)
            
            if not is_blocked and region.get_overall_density() > 0.3:
                valid_regions.append(region)
        
        # Trier par densité et retourner les top 5
        return sorted(valid_regions, key=lambda r: r.get_overall_density(), reverse=True)[:5]
    
    def _estimate_steps(self, vector: MovementVector, target_regions: List[RegionDensity]) -> int:
        """Estime le nombre d'étapes pour atteindre les cibles"""
        if not target_regions:
            return 0
        
        # Distance moyenne aux régions cibles
        avg_distance = sum(
            math.sqrt(vector.dx ** 2 + vector.dy ** 2) for _ in target_regions
        ) / len(target_regions)
        
        # Estimer les étapes basées sur la taille du pas
        step_size = math.sqrt(self.max_step_size[0] ** 2 + self.max_step_size[1] ** 2)
        
        return max(1, int(avg_distance / (step_size * 0.7)))  # 0.7 = facteur de réalisme
    
    def _calculate_plan_confidence(self, vector: MovementVector, density_map: DensityMap) -> float:
        """Calcule la confiance dans le plan de trajectoire"""
        # Facteurs de confiance
        hotspot_factor = min(1.0, len(density_map.hotspots) / 10.0)
        density_factor = density_map.global_stats.get('average_density', 0)
        vector_factor = 1.0 - min(1.0, vector.magnitude() / 100.0)  # Préférer les mouvements modérés
        
        # Combiner les facteurs
        confidence = (0.4 * hotspot_factor + 0.4 * density_factor + 0.2 * vector_factor)
        
        return max(0.1, min(1.0, confidence))
    
    def _calculate_movement_priority(self, magnitude: float, density_map: DensityMap) -> PathPriority:
        """Calcule la priorité du mouvement"""
        if magnitude < self.min_movement_threshold:
            return PathPriority.LOW
        elif magnitude > 80:
            return PathPriority.CRITICAL
        elif density_map.global_stats.get('max_density', 0) > 0.8:
            return PathPriority.HIGH
        else:
            return PathPriority.MEDIUM
    
    def _bounds_overlap(self, bounds1: GridBounds, bounds2: GridBounds) -> bool:
        """Vérifie si deux bornes se chevauchent"""
        return not (bounds1.x_max < bounds2.x_min or bounds1.x_min > bounds2.x_max or
                   bounds1.y_max < bounds2.y_min or bounds1.y_min > bounds2.y_max)
    
    def _update_internal_state(self, plan: PathPlan) -> None:
        """Met à jour l'état interne du planificateur"""
        self._path_history.append(plan.current_vector)
        
        # Limiter l'historique
        if len(self._path_history) > 50:
            self._path_history = self._path_history[-50:]
        
        # Mettre à jour la cible actuelle
        if plan.target_regions:
            self._current_target = plan.target_regions[0].bounds
    
    def _update_stats(self, plan: PathPlan) -> None:
        """Met à jour les statistiques du planificateur"""
        self._stats['plans_generated'] += 1
        self._stats['total_distance_traveled'] += plan.current_vector.magnitude()
        
        total_plans = self._stats['plans_generated']
        current_avg = self._stats['average_plan_confidence']
        self._stats['average_plan_confidence'] = (
            (current_avg * (total_plans - 1) + plan.confidence) / total_plans
        )
    
    # Interface feedback S5
    def update_zone_status(self, zone_bounds: GridBounds, status: str) -> None:
        """
        Met à jour le statut d'une zone (feedback de S5)
        
        Args:
            zone_bounds: Bornes de la zone
            status: 'resolved', 'blocked', 'critical'
        """
        with self._lock:
            if status == 'resolved':
                if zone_bounds not in self._resolved_zones:
                    self._resolved_zones.append(zone_bounds)
                # Retirer des autres listes
                self._blocked_zones = [b for b in self._blocked_zones if not self._bounds_overlap(b, zone_bounds)]
                self._critical_zones = [b for b in self._critical_zones if not self._bounds_overlap(b, zone_bounds)]
                
            elif status == 'blocked':
                if zone_bounds not in self._blocked_zones:
                    self._blocked_zones.append(zone_bounds)
                    self._stats['blocked_zone_avoidances'] += 1
                    
            elif status == 'critical':
                if zone_bounds not in self._critical_zones:
                    self._critical_zones.append(zone_bounds)
    
    def set_strategy(self, strategy: MovementStrategy) -> None:
        """Change la stratégie de mouvement"""
        with self._lock:
            if self.strategy != strategy:
                self._stats['strategy_switches'] += 1
                self.strategy = strategy
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du planificateur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'current_strategy': self.strategy.value,
                'path_history_length': len(self._path_history),
                'resolved_zones_count': len(self._resolved_zones),
                'blocked_zones_count': len(self._blocked_zones),
                'critical_zones_count': len(self._critical_zones)
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'plans_generated': 0,
                'total_distance_traveled': 0.0,
                'strategy_switches': 0,
                'average_plan_confidence': 0.0,
                'blocked_zone_avoidances': 0
            }
            self._path_history.clear()
    
    def clear_zone_status(self) -> None:
        """Efface tous les statuts de zones"""
        with self._lock:
            self._resolved_zones.clear()
            self._blocked_zones.clear()
            self._critical_zones.clear()
