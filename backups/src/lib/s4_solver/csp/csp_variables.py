"""
CSP Variables - Variables pour le moteur CSP

Définit les variables et domaines utilisés dans la résolution du démineur:
- Variables CSP avec coordonnées et domaines
- Gestion dynamique des domaines
- État d'assignation des variables
"""

from typing import Set, Tuple, Any, List
from dataclasses import dataclass, field

from ...s3_tensor.tensor_grid import CellSymbol


@dataclass
class VariableDomain:
    """Domaine d'une variable CSP"""
    possible_values: Set[CellSymbol]
    original_values: Set[CellSymbol] = field(init=False)
    
    def __post_init__(self):
        """Initialise les valeurs originales"""
        self.original_values = self.possible_values.copy()
    
    def get_values(self) -> List[CellSymbol]:
        """Retourne les valeurs possibles sous forme de liste"""
        return list(self.possible_values)
    
    def size(self) -> int:
        """Retourne la taille du domaine"""
        return len(self.possible_values)
    
    def is_empty(self) -> bool:
        """Vérifie si le domaine est vide"""
        return len(self.possible_values) == 0
    
    def is_singleton(self) -> bool:
        """Vérifie si le domaine ne contient qu'une valeur"""
        return len(self.possible_values) == 1
    
    def contains(self, value: CellSymbol) -> bool:
        """Vérifie si une valeur est dans le domaine"""
        return value in self.possible_values
    
    def remove_value(self, value: CellSymbol) -> bool:
        """
        Retire une valeur du domaine
        
        Returns:
            True si la valeur a été retirée, False si elle n'était pas présente
        """
        if value in self.possible_values:
            self.possible_values.remove(value)
            return True
        return False
    
    def restrict_to(self, values: Set[CellSymbol]) -> None:
        """Restreint le domaine à un ensemble de valeurs"""
        self.possible_values = values.intersection(self.possible_values)
    
    def reset(self) -> None:
        """Réinitialise le domaine à ses valeurs originales"""
        self.possible_values = self.original_values.copy()
    
    def copy(self) -> 'VariableDomain':
        """Crée une copie du domaine"""
        return VariableDomain(self.possible_values.copy())
    
    def intersect(self, other: 'VariableDomain') -> 'VariableDomain':
        """Crée l'intersection avec un autre domaine"""
        return VariableDomain(self.possible_values.intersection(other.possible_values))


@dataclass
class CSPVariable:
    """Variable CSP pour le problème de démineur"""
    coordinates: Tuple[int, int]  # Coordonnées grille (x, y)
    domain: VariableDomain       # Domaine des valeurs possibles
    is_assigned: bool = False    # État d'assignation
    assigned_value: CellSymbol = None  # Valeur assignée si is_assigned=True
    
    def __post_init__(self):
        """Validations post-initialisation"""
        if self.is_assigned and self.assigned_value is None:
            raise ValueError("Assigned variable must have an assigned value")
        
        if not self.is_assigned and self.assigned_value is not None:
            raise ValueError("Unassigned variable should not have an assigned value")
        
        if self.is_assigned and not self.domain.contains(self.assigned_value):
            raise ValueError("Assigned value must be in the domain")
    
    def assign(self, value: CellSymbol) -> bool:
        """
        Assigne une valeur à la variable
        
        Args:
            value: Valeur à assigner
            
        Returns:
            True si l'assignation a réussi, False sinon
        """
        if not self.domain.contains(value):
            return False
        
        self.is_assigned = True
        self.assigned_value = value
        return True
    
    def unassign(self) -> None:
        """Désassigne la variable"""
        self.is_assigned = False
        self.assigned_value = None
    
    def get_domain_size(self) -> int:
        """Retourne la taille du domaine"""
        return self.domain.size()
    
    def is_domain_empty(self) -> bool:
        """Vérifie si le domaine est vide"""
        return self.domain.is_empty()
    
    def is_domain_singleton(self) -> bool:
        """Vérifie si le domaine ne contient qu'une valeur"""
        return self.domain.is_singleton()
    
    def get_possible_values(self) -> List[CellSymbol]:
        """Retourne les valeurs possibles"""
        return self.domain.get_values()
    
    def remove_from_domain(self, value: CellSymbol) -> bool:
        """
        Retire une valeur du domaine
        
        Returns:
            True si la valeur a été retirée, False sinon
        """
        return self.domain.remove_value(value)
    
    def restrict_domain(self, values: Set[CellSymbol]) -> None:
        """Restreint le domaine"""
        self.domain.restrict_to(values)
        
        # Si la variable est assignée et que la valeur n'est plus dans le domaine
        if self.is_assigned and not self.domain.contains(self.assigned_value):
            self.unassign()
    
    def reset_domain(self) -> None:
        """Réinitialise le domaine"""
        self.domain.reset()
        self.unassign()
    
    def copy(self) -> 'CSPVariable':
        """Crée une copie de la variable"""
        new_variable = CSPVariable(
            coordinates=self.coordinates,
            domain=self.domain.copy(),
            is_assigned=self.is_assigned,
            assigned_value=self.assigned_value
        )
        return new_variable
    
    def __str__(self) -> str:
        """Représentation textuelle"""
        if self.is_assigned:
            return f"Var{self.coordinates}={self.assigned_value}"
        else:
            return f"Var{self.coordinates}∈{self.domain.get_values()}"
    
    def __repr__(self) -> str:
        """Représentation formelle"""
        return self.__str__()
