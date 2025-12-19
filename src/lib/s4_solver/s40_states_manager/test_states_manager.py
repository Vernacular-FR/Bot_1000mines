"""
Tests unitaires pour le State Manager
"""

import pytest
from typing import Dict, Tuple
from dataclasses import replace

from s40_states_manager import StateManager
from src.lib.s3_storage.types import GridCell, Coord, SolverStatus, ActiveRelevance, FrontierRelevance
from src.lib.s3_storage.facades import StorageUpsert


def create_test_cell(coord: Coord, status: SolverStatus, focus_active=None, focus_frontier=None) -> GridCell:
    """Crée une cellule de test"""
    return GridCell(
        coord=coord,
        solver_status=status,
        focus_level_active=focus_active,
        focus_level_frontier=focus_frontier,
        value=0,
        is_flagged=False,
        is_revealed=False,
        probability_safe=1.0,
    )


class TestClassifyGrid:
    """Tests pour la méthode classify_grid"""
    
    def test_classify_all_states(self):
        """Test que toutes les classifications fonctionnent"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.JUST_VISUALIZED),
            (0, 1): create_test_cell((0, 1), SolverStatus.JUST_VISUALIZED),
            (1, 0): create_test_cell((1, 0), SolverStatus.JUST_VISUALIZED),
            (2, 2): create_test_cell((2, 2), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),  # Existant
        }
        
        result = StateManager.classify_grid(cells)
        
        # Vérifier que les cellules JUST_VISUALIZED ont été classifiées
        assert (0, 0) in result.cells or (0, 1) in result.cells or (1, 0) in result.cells
        
        # Vérifier les invariants sur les cellules modifiées
        for coord, cell in result.cells.items():
            if cell.solver_status == SolverStatus.ACTIVE:
                assert cell.focus_level_active in (ActiveRelevance.TO_REDUCE,)
                assert cell.focus_level_frontier is None
            elif cell.solver_status == SolverStatus.FRONTIER:
                assert cell.focus_level_frontier in (FrontierRelevance.TO_PROCESS,)
                assert cell.focus_level_active is None
            elif cell.solver_status == SolverStatus.SOLVED:
                assert cell.focus_level_active is None
                assert cell.focus_level_frontier is None


class TestApplySolverResults:
    """Tests pour la méthode apply_solver_results"""
    
    def test_reductions_and_solutions(self):
        """Test l'application des réductions et solutions"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),
            (0, 1): create_test_cell((0, 1), SolverStatus.FRONTIER, FrontierRelevance.TO_PROCESS),
            (1, 0): create_test_cell((1, 0), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),
            (1, 1): create_test_cell((1, 1), SolverStatus.FRONTIER, FrontierRelevance.TO_PROCESS),
        }
        
        result = StateManager.apply_solver_results(
            cells,
            safe={(0, 0)},
            flags={(0, 1)},
            processed_frontier={(1, 1)},
            reduced_active={(1, 0)},
        )
        
        # Vérifier les réductions
        assert result.cells[(1, 0)].focus_level_active == ActiveRelevance.REDUCED
        assert result.cells[(1, 1)].focus_level_frontier == FrontierRelevance.PROCESSED
        
        # Vérifier les solutions (écrasent les réductions)
        assert result.cells[(0, 0)].solver_status == SolverStatus.TO_VISUALIZE
        assert result.cells[(0, 0)].focus_level_active is None
        assert result.cells[(0, 0)].focus_level_frontier is None
        
        assert result.cells[(0, 1)].solver_status == SolverStatus.SOLVED
        assert result.cells[(0, 1)].focus_level_active is None
        assert result.cells[(0, 1)].focus_level_frontier is None
    
    def test_precedence_safe_over_reduced(self):
        """Test que safe prend precedence sur reduced"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),
        }
        
        result = StateManager.apply_solver_results(
            cells,
            safe={(0, 0)},
            flags=set(),
            processed_frontier=set(),
            reduced_active={(0, 0)},  # Même coord dans reduced et safe
        )
        
        # safe doit gagner
        assert result.cells[(0, 0)].solver_status == SolverStatus.TO_VISUALIZE
        assert result.cells[(0, 0)].focus_level_active is None


class TestPromoteNeighbors:
    """Tests pour la méthode promote_neighbors"""
    
    def test_promote_just_visualized(self):
        """Test la promotion des JUST_VISUALIZED"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.JUST_VISUALIZED),
            (0, 1): create_test_cell((0, 1), SolverStatus.JUST_VISUALIZED),
            (1, 0): create_test_cell((1, 0), SolverStatus.JUST_VISUALIZED),
            (1, 1): create_test_cell((1, 1), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),  # Centre
        }
        
        result = StateManager.promote_neighbors(cells, centers={(1, 1)})
        
        # Les voisins du centre doivent être promus
        # (0,0) est diagonale du centre ACTIVE -> doit devenir FRONTIER
        assert result.cells[(0, 0)].solver_status == SolverStatus.FRONTIER
        assert result.cells[(0, 0)].focus_level_frontier == FrontierRelevance.TO_PROCESS
        
        # (0,1) et (1,0) sont adjacents -> doivent devenir ACTIVE
        assert result.cells[(0, 1)].solver_status == SolverStatus.ACTIVE
        assert result.cells[(0, 1)].focus_level_active == ActiveRelevance.TO_REDUCE
        assert result.cells[(1, 0)].solver_status == SolverStatus.ACTIVE
        assert result.cells[(1, 0)].focus_level_active == ActiveRelevance.TO_REDUCE
    
    def test_promote_reduced_to_to_reduce(self):
        """Test la promotion REDUCED -> TO_REDUCE"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.ACTIVE, ActiveRelevance.REDUCED),
            (1, 1): create_test_cell((1, 1), SolverStatus.SOLVED),  # Centre
        }
        
        result = StateManager.promote_neighbors(cells, centers={(1, 1)})
        
        assert result.cells[(0, 0)].focus_level_active == ActiveRelevance.TO_REDUCE
    
    def test_promote_processed_to_to_process(self):
        """Test la promotion PROCESSED -> TO_PROCESS"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.FRONTIER, FrontierRelevance.PROCESSED),
            (1, 1): create_test_cell((1, 1), SolverStatus.SOLVED),  # Centre
        }
        
        result = StateManager.promote_neighbors(cells, centers={(1, 1)})
        
        assert result.cells[(0, 0)].focus_level_frontier == FrontierRelevance.TO_PROCESS


class TestValidateCells:
    """Tests pour la méthode validate_cells"""
    
    def test_valid_cells(self):
        """Test que des cellules valides ne lèvent pas d'erreur"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.ACTIVE, ActiveRelevance.TO_REDUCE),
            (0, 1): create_test_cell((0, 1), SolverStatus.FRONTIER, FrontierRelevance.TO_PROCESS),
            (1, 0): create_test_cell((1, 0), SolverStatus.TO_VISUALIZE),
            (1, 1): create_test_cell((1, 1), SolverStatus.SOLVED),
            (2, 2): create_test_cell((2, 2), SolverStatus.JUST_VISUALIZED),
        }
        
        # Ne doit pas lever d'exception
        StateManager.validate_cells(cells)
    
    def test_active_without_focus(self):
        """Test qu'une cellule ACTIVE sans focus lève une erreur"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.ACTIVE),  # Pas de focus
        }
        
        with pytest.raises(ValueError, match="ACTIVE doit avoir focus_level_active non nul"):
            StateManager.validate_cells(cells)
    
    def test_frontier_with_wrong_focus(self):
        """Test qu'une cellule FRONTIER avec mauvais focus lève une erreur"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.FRONTIER, focus_frontier=ActiveRelevance.TO_REDUCE),
        }
        
        with pytest.raises(ValueError, match="FRONTIER a un focus_level_frontier invalide"):
            StateManager.validate_cells(cells)
    
    def test_solved_with_focus(self):
        """Test qu'une cellule SOLVED avec focus lève une erreur"""
        cells = {
            (0, 0): create_test_cell((0, 0), SolverStatus.SOLVED, focus_frontier=FrontierRelevance.TO_PROCESS),
        }
        
        with pytest.raises(ValueError, match="SOLVED ne doit pas avoir de focus"):
            StateManager.validate_cells(cells)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
