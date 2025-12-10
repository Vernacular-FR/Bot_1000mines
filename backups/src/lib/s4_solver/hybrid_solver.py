"""
HybridSolver - Orchestrateur hybride CSP/Monte Carlo/Neural (S4)

Coordonne les différents moteurs de résolution:
- CSP exact pour zones simples
- Monte Carlo pour zones complexes
- Neural Assist pour zones très difficiles
- Interface unifiée avec TensorGrid et HintCache
"""

import numpy as np
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time
import threading

from .tensor_frontier import TensorFrontier, FrontierZone, FrontierZoneType, SolverContext
from .csp.csp_engine import CSPEngine, CSPResult, CSPSolution
from ..s3_tensor.tensor_grid import TensorGrid, GridBounds, CellSymbol
from ..s3_tensor.hint_cache import HintCache, HintType


class SolverStrategy(Enum):
    """Stratégies de résolution"""
    CSP_ONLY = "csp_only"
    HYBRID_CSP_MC = "hybrid_csp_mc"
    HYBRID_FULL = "hybrid_full"
    FAST_MODE = "fast_mode"


@dataclass
class SolverAction:
    """Action générée par le solver"""
    action_type: str  # 'reveal', 'flag', 'guess'
    coordinates: Tuple[int, int]
    confidence: float
    reasoning: str
    solver_engine: str
    metadata: Dict[str, Any]
    
    def __hash__(self):
        return hash((self.action_type, self.coordinates))
    
    def __eq__(self, other):
        return (self.action_type == other.action_type and 
                self.coordinates == other.coordinates)


@dataclass
class SolverResult:
    """Résultat complet du solveur hybride"""
    success: bool
    actions: List[SolverAction]
    safe_cells: Set[Tuple[int, int]]
    mine_cells: Set[Tuple[int, int]]
    guess_cells: Set[Tuple[int, int]]
    processing_time: float
    strategy_used: SolverStrategy
    engine_stats: Dict[str, Any]
    metadata: Dict[str, Any]


class HybridSolver:
    """
    Orchestrateur hybride pour la résolution de démineur
    
    Fonctionnalités:
    - Coordination automatique des moteurs CSP/Monte Carlo/Neural
    - Stratégies adaptatives basées sur la complexité
    - Interface unifiée avec TensorGrid
    - Optimisation via HintCache
    """
    
    def __init__(self, tensor_grid: TensorGrid, hint_cache: HintCache,
                 strategy: SolverStrategy = SolverStrategy.HYBRID_CSP_MC,
                 timeout_seconds: float = 10.0,
                 enable_neural: bool = False):
        """
        Initialise le solveur hybride
        
        Args:
            tensor_grid: Grille tensorielle pour lecture/écriture
            hint_cache: Cache d'indices pour optimisations
            strategy: Stratégie de résolution par défaut
            timeout_seconds: Timeout global pour la résolution
            enable_neural: Activer l'assistance neurale (placeholder)
        """
        self._lock = threading.RLock()
        
        # Dépendances
        self.tensor_grid = tensor_grid
        self.hint_cache = hint_cache
        
        # Configuration
        self.strategy = strategy
        self.timeout_seconds = timeout_seconds
        self.enable_neural = enable_neural
        
        # Moteurs de résolution
        self.tensor_frontier = TensorFrontier(tensor_grid, hint_cache)
        self.csp_engine = CSPEngine(tensor_grid)
        
        # Placeholder pour Monte Carlo et Neural (à implémenter)
        self._mc_engine = None  # MonteCarloEngine()
        self._neural_engine = None  # NeuralAssistEngine()
        
        # Statistiques
        self._stats = {
            'solves_performed': 0,
            'total_actions_generated': 0,
            'csp_solves': 0,
            'mc_solves': 0,
            'neural_solves': 0,
            'average_solve_time': 0.0,
            'success_rate': 0.0
        }
    
    def solve(self, region_bounds: Optional[GridBounds] = None,
              strategy: Optional[SolverStrategy] = None) -> SolverResult:
        """
        Résout une région avec la stratégie hybride
        
        Args:
            region_bounds: Bornes de la région à résoudre
            strategy: Stratégie à utiliser (None = défaut)
            
        Returns:
            Résultat complet avec actions et métadonnées
        """
        start_time = time.time()
        
        with self._lock:
            # Utiliser la stratégie spécifiée ou celle par défaut
            current_strategy = strategy or self.strategy
            
            try:
                # Extraire le contexte de résolution
                context = self.tensor_frontier.extract_solver_context(region_bounds)
                
                if not context.frontier_zones:
                    return SolverResult(
                        success=False,
                        actions=[],
                        safe_cells=set(),
                        mine_cells=set(),
                        guess_cells=set(),
                        processing_time=time.time() - start_time,
                        strategy_used=current_strategy,
                        engine_stats={},
                        metadata={'reason': 'no_frontier_zones'}
                    )
                
                # Appliquer la stratégie de résolution
                result = self._apply_strategy(context, current_strategy, start_time)
                
                # Mettre à jour les statistiques
                self._update_stats(result, time.time() - start_time)
                
                # Publier les hints pour les prochaines itérations
                self._publish_solver_hints(result, context)
                
                return result
                
            except Exception as e:
                return SolverResult(
                    success=False,
                    actions=[],
                    safe_cells=set(),
                    mine_cells=set(),
                    guess_cells=set(),
                    processing_time=time.time() - start_time,
                    strategy_used=current_strategy,
                    engine_stats={},
                    metadata={'error': str(e)}
                )
                
    # ------------------------------------------------------------------ #
    # API compacte attendue par les couches supérieures
    # ------------------------------------------------------------------ #
    def solve_grid(
        self,
        region_bounds: Optional[GridBounds] = None,
        timeout: Optional[float] = None,
        strategy: Optional[SolverStrategy] = None,
    ) -> SolverResult:
        """
        Enveloppe de `solve` compatible avec l'orchestrateur.

        Args:
            region_bounds: Bornes à résoudre (None = toute la grille)
            timeout: Timeout spécifique (secondes)
            strategy: Stratégie de résolution
        """
        previous_timeout = self.timeout_seconds
        if timeout is not None:
            self.timeout_seconds = timeout

        try:
            return self.solve(region_bounds=region_bounds, strategy=strategy)
        finally:
            self.timeout_seconds = previous_timeout

    def _apply_strategy(self, context: SolverContext, strategy: SolverStrategy,
                       start_time: float) -> SolverResult:
        """Applique la stratégie de résolution spécifiée"""
        if strategy == SolverStrategy.CSP_ONLY:
            return self._solve_csp_only(context, start_time)
        elif strategy == SolverStrategy.HYBRID_CSP_MC:
            return self._solve_hybrid_csp_mc(context, start_time)
        elif strategy == SolverStrategy.HYBRID_FULL:
            return self._solve_hybrid_full(context, start_time)
        elif strategy == SolverStrategy.FAST_MODE:
            return self._solve_fast_mode(context, start_time)
        else:
            return self._solve_hybrid_csp_mc(context, start_time)
    
    def _solve_csp_only(self, context: SolverContext, start_time: float) -> SolverResult:
        """Stratégie CSP uniquement"""
        all_actions = []
        all_safe = set()
        all_mines = set()
        
        csp_zones = self.tensor_frontier.get_zones_by_type(FrontierZoneType.CSP_SOLVABLE)
        
        for zone in csp_zones:
            if time.time() - start_time > self.timeout_seconds:
                break
            
            csp_solution = self.csp_engine.solve_zone(zone)
            
            if csp_solution.result in [CSPResult.SOLVED, CSPResult.PARTIAL]:
                # Convertir les solutions en actions
                actions = self._convert_csp_to_actions(csp_solution)
                all_actions.extend(actions)
                all_safe.update(csp_solution.safe_cells)
                all_mines.update(csp_solution.mine_cells)
        
        return SolverResult(
            success=len(all_actions) > 0,
            actions=all_actions,
            safe_cells=all_safe,
            mine_cells=all_mines,
            guess_cells=set(),
            processing_time=time.time() - start_time,
            strategy_used=SolverStrategy.CSP_ONLY,
            engine_stats={'csp_zones_processed': len(csp_zones)},
            metadata={'solver_engine': 'csp_only'}
        )
    
    def _solve_hybrid_csp_mc(self, context: SolverContext, start_time: float) -> SolverResult:
        """Stratégie hybride CSP + Monte Carlo"""
        all_actions = []
        all_safe = set()
        all_mines = set()
        all_guesses = set()
        
        engine_stats = {'csp_zones': 0, 'mc_zones': 0, 'neural_zones': 0}
        
        # Traiter les zones par ordre de priorité
        zones = context.frontier_zones
        
        for zone in zones:
            if time.time() - start_time > self.timeout_seconds:
                break
            
            if zone.zone_type == FrontierZoneType.CSP_SOLVABLE:
                # Utiliser CSP pour les zones simples
                csp_solution = self.csp_engine.solve_zone(zone)
                engine_stats['csp_zones'] += 1
                
                if csp_solution.result in [CSPResult.SOLVED, CSPResult.PARTIAL]:
                    actions = self._convert_csp_to_actions(csp_solution)
                    all_actions.extend(actions)
                    all_safe.update(csp_solution.safe_cells)
                    all_mines.update(csp_solution.mine_cells)
            
            elif zone.zone_type == FrontierZoneType.MONTE_CARLO:
                # Utiliser Monte Carlo pour les zones complexes
                mc_actions = self._solve_monte_carlo(zone)
                engine_stats['mc_zones'] += 1
                all_actions.extend(mc_actions)
                
                # Extraire les guesses des actions MC
                for action in mc_actions:
                    if action.action_type == 'guess':
                        all_guesses.add(action.coordinates)
            
            elif zone.zone_type == FrontierZoneType.NEURAL_ASSIST and self.enable_neural:
                # Utiliser Neural Assist pour les zones très difficiles
                neural_actions = self._solve_neural_assist(zone)
                engine_stats['neural_zones'] += 1
                all_actions.extend(neural_actions)
                
                for action in neural_actions:
                    if action.action_type == 'guess':
                        all_guesses.add(action.coordinates)
        
        return SolverResult(
            success=len(all_actions) > 0,
            actions=all_actions,
            safe_cells=all_safe,
            mine_cells=all_mines,
            guess_cells=all_guesses,
            processing_time=time.time() - start_time,
            strategy_used=SolverStrategy.HYBRID_CSP_MC,
            engine_stats=engine_stats,
            metadata={'solver_engine': 'hybrid_csp_mc'}
        )
    
    def _solve_hybrid_full(self, context: SolverContext, start_time: float) -> SolverResult:
        """Stratégie hybride complète avec tous les moteurs"""
        # Similaire à hybrid_csp_mc mais avec plus d'optimisations
        return self._solve_hybrid_csp_mc(context, start_time)
    
    def _solve_fast_mode(self, context: SolverContext, start_time: float) -> SolverResult:
        """Stratégie rapide pour les temps réels"""
        all_actions = []
        all_safe = set()
        all_mines = set()
        
        # Traiter uniquement les zones CSP les plus prioritaires
        high_priority_zones = self.tensor_frontier.get_high_priority_zones(min_priority=0.7)
        csp_zones = [z for z in high_priority_zones if z.zone_type == FrontierZoneType.CSP_SOLVABLE]
        
        # Limiter à 3 zones maximum pour la rapidité
        csp_zones = csp_zones[:3]
        
        for zone in csp_zones:
            if time.time() - start_time > 2.0:  # Timeout très court
                break
            
            csp_solution = self.csp_engine.solve_zone(zone)
            
            if csp_solution.result in [CSPResult.SOLVED, CSPResult.PARTIAL]:
                actions = self._convert_csp_to_actions(csp_solution)
                all_actions.extend(actions)
                all_safe.update(csp_solution.safe_cells)
                all_mines.update(csp_solution.mine_cells)
        
        return SolverResult(
            success=len(all_actions) > 0,
            actions=all_actions,
            safe_cells=all_safe,
            mine_cells=all_mines,
            guess_cells=set(),
            processing_time=time.time() - start_time,
            strategy_used=SolverStrategy.FAST_MODE,
            engine_stats={'csp_zones_processed': len(csp_zones)},
            metadata={'solver_engine': 'fast_mode'}
        )
    
    def _solve_monte_carlo(self, zone: FrontierZone) -> List[SolverAction]:
        """
        Résout une zone avec Monte Carlo (placeholder)
        
        TODO: Implémenter le vrai moteur Monte Carlo
        """
        # Placeholder: retourner des guesses aléatoires avec faible confiance
        actions = []
        
        for x, y in zone.unknown_cells:
            if len(actions) >= 5:  # Limiter pour éviter trop de guesses
                break
            
            action = SolverAction(
                action_type='guess',
                coordinates=(x, y),
                confidence=0.3,
                reasoning='monte_carlo_placeholder',
                solver_engine='monte_carlo',
                metadata={'zone_id': zone.zone_id, 'complexity': zone.complexity_score}
            )
            actions.append(action)
        
        return actions
    
    def _solve_neural_assist(self, zone: FrontierZone) -> List[SolverAction]:
        """
        Résout une zone avec Neural Assist (placeholder)
        
        TODO: Implémenter le vrai moteur Neural Assist
        """
        # Placeholder: utiliser une heuristique simple
        actions = []
        
        # Préférer les cellules avec moins de contraintes
        sorted_cells = sorted(zone.unknown_cells, key=lambda coord: len([
            (nx, ny) for nx, ny in zone.number_cells.keys()
            if abs(nx - coord[0]) <= 1 and abs(ny - coord[1]) <= 1
        ]))
        
        for x, y in sorted_cells[:3]:  # Limiter à 3 actions
            action = SolverAction(
                action_type='guess',
                coordinates=(x, y),
                confidence=0.4,
                reasoning='neural_assist_placeholder',
                solver_engine='neural_assist',
                metadata={'zone_id': zone.zone_id, 'complexity': zone.complexity_score}
            )
            actions.append(action)
        
        return actions
    
    def _convert_csp_to_actions(self, csp_solution: CSPSolution) -> List[SolverAction]:
        """Convertit une solution CSP en actions"""
        actions = []
        
        # Actions pour les cellules sûres (révéler)
        for x, y in csp_solution.safe_cells:
            action = SolverAction(
                action_type='reveal',
                coordinates=(x, y),
                confidence=1.0,
                reasoning='csp_exact_solution',
                solver_engine='csp',
                metadata={'csp_result': csp_solution.result.value}
            )
            actions.append(action)
        
        # Actions pour les mines (flag)
        for x, y in csp_solution.mine_cells:
            action = SolverAction(
                action_type='flag',
                coordinates=(x, y),
                confidence=1.0,
                reasoning='csp_exact_solution',
                solver_engine='csp',
                metadata={'csp_result': csp_solution.result.value}
            )
            actions.append(action)
        
        return actions
    
    def _publish_solver_hints(self, result: SolverResult, context: SolverContext) -> None:
        """Publie des hints basés sur les résultats du solveur"""
        if not result.success:
            return
        
        # Marquer les régions traitées comme résolues
        for zone in context.frontier_zones:
            zone_bounds = zone.bounds
            
            # Vérifier si des actions ont été générées pour cette zone
            zone_actions = [a for a in result.actions if 
                           zone_bounds.x_min <= a.coordinates[0] <= zone_bounds.x_max and
                           zone_bounds.y_min <= a.coordinates[1] <= zone_bounds.y_max]
            
            if zone_actions:
                # Feedback positif pour le hint cache
                self.hint_cache.solver_feedback(
                    solved_bounds=zone_bounds,
                    success_rate=1.0,
                    metadata={
                        'actions_count': len(zone_actions),
                        'solver_strategy': result.strategy_used.value
                    }
                )
    
    def _update_stats(self, result: SolverResult, processing_time: float) -> None:
        """Met à jour les statistiques du solveur"""
        self._stats['solves_performed'] += 1
        self._stats['total_actions_generated'] += len(result.actions)
        
        # Comptabiliser les moteurs utilisés
        for action in result.actions:
            if action.solver_engine == 'csp':
                self._stats['csp_solves'] += 1
            elif action.solver_engine == 'monte_carlo':
                self._stats['mc_solves'] += 1
            elif action.solver_engine == 'neural_assist':
                self._stats['neural_solves'] += 1
        
        # Mettre à jour le temps moyen et le taux de succès
        total_solves = self._stats['solves_performed']
        current_avg = self._stats['average_solve_time']
        self._stats['average_solve_time'] = (
            (current_avg * (total_solves - 1) + processing_time) / total_solves
        )
        
        # Taux de succès (moyenne mobile)
        current_success_rate = self._stats['success_rate']
        self._stats['success_rate'] = (
            (current_success_rate * (total_solves - 1) + (1.0 if result.success else 0.0)) / total_solves
        )
    
    def get_next_actions(self, max_actions: int = 10,
                        min_confidence: float = 0.5) -> List[SolverAction]:
        """
        Récupère les prochaines actions à exécuter
        
        Args:
            max_actions: Nombre maximum d'actions
            min_confidence: Confiance minimale requise
            
        Returns:
            Liste des actions filtrées
        """
        # Résoudre avec la stratégie actuelle
        result = self.solve()
        
        # Filtrer les actions
        filtered_actions = [
            action for action in result.actions
            if action.confidence >= min_confidence
        ]
        
        # Trier par confiance décroissante
        filtered_actions.sort(key=lambda a: a.confidence, reverse=True)
        
        return filtered_actions[:max_actions]
    
    def set_strategy(self, strategy: SolverStrategy) -> None:
        """Change la stratégie de résolution"""
        with self._lock:
            self.strategy = strategy
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du solveur"""
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                'tensor_frontier_stats': self.tensor_frontier.get_stats(),
                'csp_engine_stats': self.csp_engine.get_stats(),
                'current_strategy': self.strategy.value,
                'neural_enabled': self.enable_neural
            })
            return stats
    
    def reset_stats(self) -> None:
        """Réinitialise les statistiques"""
        with self._lock:
            self._stats = {
                'solves_performed': 0,
                'total_actions_generated': 0,
                'csp_solves': 0,
                'mc_solves': 0,
                'neural_solves': 0,
                'average_solve_time': 0.0,
                'success_rate': 0.0
            }
            
            self.tensor_frontier.reset_stats()
            self.csp_engine.reset_stats()
    
    def invalidate_cache(self) -> None:
        """Invalide tous les caches"""
        with self._lock:
            self.tensor_frontier.invalidate_cache()
