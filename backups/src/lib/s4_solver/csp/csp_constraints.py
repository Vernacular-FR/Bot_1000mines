"""
CSP Constraints - Contraintes pour le moteur CSP

Définit les types de contraintes utilisées dans la résolution du démineur:
- Contraintes de nombre de mines
- Contraintes de distribution
- Contraintes de cohérence
"""

from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ConstraintType(Enum):
    """Types de contraintes CSP"""
    MINE_COUNT = "mine_count"      # Nombre de mines autour d'un nombre
    DISTRIBUTION = "distribution"  # Distribution globale des mines
    COHERENCE = "coherence"        # Cohérence locale
    BOUNDARY = "boundary"          # Contraintes aux frontières


@dataclass
class CSPConstraint:
    """Contrainte CSP pour le problème de démineur"""
    constraint_type: ConstraintType
    variables: List[Tuple[int, int]]  # Coordonnées des variables impliquées
    parameters: Dict[str, Any]        # Paramètres spécifiques à la contrainte
    
    def __post_init__(self):
        """Validations post-initialisation"""
        if not self.variables:
            raise ValueError("Constraint must involve at least one variable")
        
        if self.constraint_type == ConstraintType.MINE_COUNT:
            if 'expected_mines' not in self.parameters:
                raise ValueError("Mine count constraint requires 'expected_mines' parameter")
    
    def involves_variable(self, coords: Tuple[int, int]) -> bool:
        """Vérifie si la contrainte implique une variable spécifique"""
        return coords in self.variables
    
    def get_arity(self) -> int:
        """Retourne l'arité de la contrainte (nombre de variables)"""
        return len(self.variables)
    
    def is_binary(self) -> bool:
        """Vérifie si c'est une contrainte binaire"""
        return self.get_arity() == 2
    
    def is_global(self) -> bool:
        """Vérifie si c'est une contrainte globale (implique beaucoup de variables)"""
        return self.get_arity() > 4
