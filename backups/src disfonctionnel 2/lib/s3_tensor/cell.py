from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime

class CellSymbol(Enum):
    """Symboles possibles d'une case dans le modèle de jeu"""
    UNKNOWN = "unknown"       # État inconnu (jamais vu)
    UNREVEALED = "unrevealed" # Case non révélée (cachée)
    EMPTY = "empty"           # Case vide (0 mines voisines)
    FLAG = "flag"             # Drapeau
    MINE = "mine"             # Mine
    NUMBER_1 = "number_1"
    NUMBER_2 = "number_2"
    NUMBER_3 = "number_3"
    NUMBER_4 = "number_4"
    NUMBER_5 = "number_5"
    NUMBER_6 = "number_6"
    NUMBER_7 = "number_7"
    NUMBER_8 = "number_8"

class ProcessingStatus(Enum):
    """État de traitement d'une case pour le solveur"""
    NONE = "none"             # Ne nécessite pas de traitement (ex: non révélée, drapeau)
    TO_PROCESS = "to_process" # Information nouvelle, à traiter par le solveur
    PROCESSED = "processed"   # Information déjà traitée / intégrée

@dataclass
class Cell:
    """Représentation d'une case dans la grille de jeu"""
    x: int
    y: int
    symbol: CellSymbol = CellSymbol.UNKNOWN
    processing_status: ProcessingStatus = ProcessingStatus.NONE
    last_update: datetime = None
    confidence: float = 0.0  # Confiance de la reconnaissance visuelle
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now()

    @property
    def is_number(self) -> bool:
        """Vérifie si la case contient un chiffre"""
        return self.symbol in [
            CellSymbol.NUMBER_1, CellSymbol.NUMBER_2, CellSymbol.NUMBER_3,
            CellSymbol.NUMBER_4, CellSymbol.NUMBER_5, CellSymbol.NUMBER_6,
            CellSymbol.NUMBER_7, CellSymbol.NUMBER_8
        ]

    @property
    def number_value(self) -> Optional[int]:
        """Retourne la valeur numérique si c'est un chiffre"""
        if self.is_number:
            return int(self.symbol.value.split('_')[1])
        return None
