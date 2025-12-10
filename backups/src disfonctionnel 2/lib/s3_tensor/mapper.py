from .types import CellType as VisionCellType
from .cell import CellSymbol

class VisionToGameMapper:
    """Convertisseur entre les types de la vision et les symboles du jeu"""
    
    @staticmethod
    def map_cell_type(vision_type: VisionCellType) -> CellSymbol:
        """Convertit un CellType (vision) en CellSymbol (jeu)"""
        mapping = {
            VisionCellType.EMPTY: CellSymbol.EMPTY,
            VisionCellType.UNREVEALED: CellSymbol.UNREVEALED,
            VisionCellType.FLAG: CellSymbol.FLAG,
            VisionCellType.MINE: CellSymbol.MINE,
            VisionCellType.NUMBER_1: CellSymbol.NUMBER_1,
            VisionCellType.NUMBER_2: CellSymbol.NUMBER_2,
            VisionCellType.NUMBER_3: CellSymbol.NUMBER_3,
            VisionCellType.NUMBER_4: CellSymbol.NUMBER_4,
            VisionCellType.NUMBER_5: CellSymbol.NUMBER_5,
            VisionCellType.NUMBER_6: CellSymbol.NUMBER_6,
            VisionCellType.NUMBER_7: CellSymbol.NUMBER_7,
            VisionCellType.NUMBER_8: CellSymbol.NUMBER_8,
            VisionCellType.UNKNOWN: CellSymbol.UNKNOWN
        }
        return mapping.get(vision_type, CellSymbol.UNKNOWN)

    @staticmethod
    def map_symbol(game_symbol: CellSymbol) -> VisionCellType:
        """Convertit un CellSymbol (jeu) en CellType (vision)"""
        mapping = {
            CellSymbol.EMPTY: VisionCellType.EMPTY,
            CellSymbol.UNREVEALED: VisionCellType.UNREVEALED,
            CellSymbol.FLAG: VisionCellType.FLAG,
            CellSymbol.MINE: VisionCellType.MINE,
            CellSymbol.NUMBER_1: VisionCellType.NUMBER_1,
            CellSymbol.NUMBER_2: VisionCellType.NUMBER_2,
            CellSymbol.NUMBER_3: VisionCellType.NUMBER_3,
            CellSymbol.NUMBER_4: VisionCellType.NUMBER_4,
            CellSymbol.NUMBER_5: VisionCellType.NUMBER_5,
            CellSymbol.NUMBER_6: VisionCellType.NUMBER_6,
            CellSymbol.NUMBER_7: VisionCellType.NUMBER_7,
            CellSymbol.NUMBER_8: VisionCellType.NUMBER_8,
            CellSymbol.UNKNOWN: VisionCellType.UNKNOWN
        }
        return mapping.get(game_symbol, VisionCellType.UNKNOWN)
