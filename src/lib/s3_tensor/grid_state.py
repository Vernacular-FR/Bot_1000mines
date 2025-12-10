from typing import Dict, Tuple, List, Optional, Set, Any
from datetime import datetime, timezone
import json
import os
import time
from .cell import Cell, CellSymbol, ProcessingStatus

class GridState:
    """
    Base de données de l'état de la grille.
    Mémorise l'état de chaque cellule identifiée par (x, y).
    """
    
    def __init__(self):
        self.cells: Dict[Tuple[int, int], Cell] = {}
        self.last_update: datetime = datetime.now()
        self.bounds: Tuple[int, int, int, int] = (0, 0, 0, 0) # min_x, min_y, max_x, max_y
        
    def get_cell(self, x: int, y: int) -> Cell:
        """Récupère une cellule, la crée si elle n'existe pas"""
        if (x, y) not in self.cells:
            self.cells[(x, y)] = Cell(x=x, y=y)
            self._update_bounds(x, y)
        return self.cells[(x, y)]
    
    def update_cell(self, x: int, y: int, symbol: CellSymbol, confidence: float = 1.0):
        """
        Met à jour l'état d'une cellule.
        Gère automatiquement le statut de traitement.
        """
        cell = self.get_cell(x, y)
        
        # Si l'état change
        if cell.symbol != symbol:
            cell.symbol = symbol
            cell.confidence = confidence
            cell.last_update = datetime.now()
            
            # Mise à jour du statut de traitement
            # Les chiffres et les cases vides révélées sont à traiter
            if cell.is_number or symbol == CellSymbol.EMPTY:
                cell.processing_status = ProcessingStatus.TO_PROCESS
            else:
                cell.processing_status = ProcessingStatus.NONE
                
        # Si on confirme un état existant avec une meilleure confiance
        elif confidence > cell.confidence:
            cell.confidence = confidence
            cell.last_update = datetime.now()
            
        self.last_update = datetime.now()

    def mark_as_processed(self, x: int, y: int):
        """Marque une cellule comme traitée par le solveur"""
        if (x, y) in self.cells:
            self.cells[(x, y)].processing_status = ProcessingStatus.PROCESSED

    def get_cells_to_process(self) -> List[Cell]:
        """Retourne la liste des cellules en attente de traitement"""
        return [c for c in self.cells.values() if c.processing_status == ProcessingStatus.TO_PROCESS]

    def _update_bounds(self, x: int, y: int):
        """Met à jour les limites connues de la grille"""
        if not self.cells:
            self.bounds = (x, y, x, y)
            return
            
        min_x, min_y, max_x, max_y = self.bounds
        self.bounds = (
            min(min_x, x),
            min(min_y, y),
            max(max_x, x),
            max(max_y, y)
        )

    def get_known_cells_count(self) -> int:
        """Retourne le nombre de cellules connues (non UNKNOWN)"""
        return sum(1 for c in self.cells.values() if c.symbol != CellSymbol.UNKNOWN)
    
    def get_summary(self) -> Dict[str, any]:
        """Retourne un résumé de l'état de la grille"""
        symbol_counts = {}
        for cell in self.cells.values():
            symbol_name = cell.symbol.value
            if symbol_name not in symbol_counts:
                symbol_counts[symbol_name] = 0
            symbol_counts[symbol_name] += 1
        
        processing_counts = {
            'to_process': sum(1 for c in self.cells.values() if c.processing_status == ProcessingStatus.TO_PROCESS),
            'processed': sum(1 for c in self.cells.values() if c.processing_status == ProcessingStatus.PROCESSED),
            'none': sum(1 for c in self.cells.values() if c.processing_status == ProcessingStatus.NONE)
        }
        
        return {
            'total_cells': len(self.cells),
            'known_cells': self.get_known_cells_count(),
            'bounds': self.bounds,
            'symbol_distribution': symbol_counts,
            'processing_status': processing_counts,
            'last_update': self.last_update.isoformat()
        }


class GamePersistence:
    """Gestion centralisée des fichiers temp/games/{game_id} et GridDB."""

    def __init__(self, base_path: str, metadata_path: Optional[str] = None, actions_dir: Optional[str] = None, grid_db_path: Optional[str] = None):
        self.base_path = base_path
        self.metadata_path = metadata_path or os.path.join(base_path, "metadata.json")
        self.actions_dir = actions_dir or os.path.join(base_path, "s4_actions")
        self.grid_db_path = grid_db_path or os.path.join(base_path, "grid_db.json")
        self._grid_db = None

        os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
        os.makedirs(self.actions_dir, exist_ok=True)

    @property
    def grid_db(self):
        """Lazy load GridDB instance."""
        if self._grid_db is None:
            self._grid_db = GridDB(self.grid_db_path)
        return self._grid_db

    def save_actions(self, game_id: str, iteration_num: int, zone_bounds: Tuple[int, int, int, int],
                     game_actions: List, execution_result: Dict[str, any]) -> str:
        """Sauvegarde les actions exécutées dans s4_actions/ et retourne le chemin."""
        start_x, start_y, end_x, end_y = zone_bounds
        filename = f"{game_id}_iter{iteration_num}_actions_{start_x}_{start_y}_{end_x}_{end_y}.json"
        save_path = os.path.join(self.actions_dir, filename)

        actions_payload = [action.to_dict() if hasattr(action, "to_dict") else {
            'action_type': getattr(action, 'action_type', None),
            'grid_x': getattr(action, 'grid_x', None),
            'grid_y': getattr(action, 'grid_y', None),
            'description': getattr(action, 'description', ''),
            'confidence': getattr(action, 'confidence', 0.0)
        } for action in game_actions]

        payload = {
            "timestamp": time.time(),
            "zone_bounds": zone_bounds,
            "actions": actions_payload,
            "execution_result": execution_result
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return save_path

    def load_metadata(self) -> Dict[str, any]:
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def update_metadata(self, updates: Dict[str, any]) -> Dict[str, any]:
        """Met à jour metadata.json avec les champs fournis et retourne le contenu final."""
        metadata = self.load_metadata()
        metadata.update(updates)

        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        return metadata


class GridDB:
    """Interface avec la base de données JSON pour le solver Minesweeper"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.data = self._load_db()
        self._ensure_structure()
    
    def _load_db(self) -> Dict[str, Any]:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"ATTENTION: Erreur chargement DB: {e}")
                return self._create_empty_db()
        else:
            return self._create_empty_db()
    
    def _create_empty_db(self) -> Dict[str, Any]:
        return {
            "metadata": {
                "version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_updated": datetime.now(timezone.utc).isoformat()
            },
            "summary": {
                "total_cells": 0,
                "known_cells": 0,
                "bounds": [0, 0, 0, 0],
                "symbol_distribution": {},
                "processing_status": {"to_process": 0, "processed": 0, "none": 0},
                "last_update": datetime.now(timezone.utc).isoformat()
            },
            "cells": [],
            "actions": [],
            "constraints": []
        }
    
    def _ensure_structure(self):
        required_sections = ["metadata", "summary", "cells", "actions", "constraints"]
        for section in required_sections:
            if section not in self.data:
                self.data[section] = {}
    
    def _save_db(self):
        try:
            self.data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.data["summary"]["last_update"] = datetime.now(timezone.utc).isoformat()
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"ERREUR: Erreur sauvegarde DB: {e}")
    
    def add_cell(self, x: int, y: int, cell_data: Dict[str, Any]):
        cell_key = f"{x},{y}"
        cell_entry = {
            "x": x,
            "y": y,
            "type": cell_data.get("type", "unknown"),
            "confidence": float(cell_data.get("confidence", 0.0)),
            "state": cell_data.get("state", "UNPROCESSED"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "metadata": cell_data.get("metadata", {})
        }
        if "known" in cell_data:
            cell_entry["known"] = bool(cell_data["known"])
        else:
            cell_entry["known"] = cell_entry["type"] not in {"unknown"}
        
        existing_index = None
        for i, cell in enumerate(self.data["cells"]):
            if cell["x"] == x and cell["y"] == y:
                existing_index = i
                break
        
        if existing_index is not None:
            self.data["cells"][existing_index].update(cell_entry)
        else:
            self.data["cells"].append(cell_entry)
        
        self._update_summary()
    
    def get_cell(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        for cell in self.data["cells"]:
            if cell["x"] == x and cell["y"] == y:
                return cell.copy()
        return None
    
    def get_cells_by_type(self, cell_type: str) -> List[Dict[str, Any]]:
        return [cell.copy() for cell in self.data["cells"] if cell["type"] == cell_type]
    
    def get_all_cells(self) -> List[Dict[str, Any]]:
        return [cell.copy() for cell in self.data["cells"]]
    
    def get_number_cells(self) -> List[Dict[str, Any]]:
        return [cell.copy() for cell in self.data["cells"] 
                if cell["type"].startswith("number_")]
    
    def get_unknown_cells(self) -> List[Dict[str, Any]]:
        return [cell.copy() for cell in self.data["cells"] 
                if cell["type"] == "unknown"]
    
    def update_cell_state(self, x: int, y: int, new_state: str):
        for cell in self.data["cells"]:
            if cell["x"] == x and cell["y"] == y:
                cell["state"] = new_state
                cell["last_updated"] = datetime.now(timezone.utc).isoformat()
                break
        self._update_summary()
    
    def add_action(self, action: Dict[str, Any]):
        action_entry = {
            "id": len(self.data["actions"]) + 1,
            "type": action["type"],
            "coordinates": action["coordinates"],
            "reasoning": action.get("reasoning", ""),
            "confidence": action.get("confidence", 0.0),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "executed": False
        }
        self.data["actions"].append(action_entry)
    
    def get_pending_actions(self) -> List[Dict[str, Any]]:
        return [action.copy() for action in self.data["actions"] 
                if not action["executed"]]
    
    def mark_action_executed(self, action_id: int):
        for action in self.data["actions"]:
            if action["id"] == action_id:
                action["executed"] = True
                action["executed_at"] = datetime.now(timezone.utc).isoformat()
                break
    
    def get_bounds(self) -> List[int]:
        return self.data["summary"].get("bounds", [0, 0, 0, 0])
    
    def _update_summary(self):
        total_cells = len(self.data["cells"])
        known_cells = len([c for c in self.data["cells"] if c["type"] != "unknown"])
        
        symbol_distribution = {}
        for cell in self.data["cells"]:
            cell_type = cell["type"]
            symbol_distribution[cell_type] = symbol_distribution.get(cell_type, 0) + 1
        
        processing_status = {"to_process": 0, "processed": 0, "none": 0}
        for cell in self.data["cells"]:
            state = cell["state"]
            if state == "TO_PROCESS":
                processing_status["to_process"] += 1
            elif state in ["PROCESSED", "PENDING_ACTION"]:
                processing_status["processed"] += 1
            else:
                processing_status["none"] += 1
        
        if self.data["cells"]:
            xs = [c["x"] for c in self.data["cells"]]
            ys = [c["y"] for c in self.data["cells"]]
            bounds = [min(xs), min(ys), max(xs), max(ys)]
        else:
            bounds = [0, 0, 0, 0]
        
        self.data["summary"].update({
            "total_cells": total_cells,
            "known_cells": known_cells,
            "bounds": bounds,
            "symbol_distribution": symbol_distribution,
            "processing_status": processing_status,
            "last_update": datetime.now(timezone.utc).isoformat()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        return self.data["summary"].copy()
    
    def flush_to_disk(self):
        self._save_db()
    
    def clear_all(self):
        self.data = self._create_empty_db()
        self._save_db()
    
    def get_cell_count_by_type(self) -> Dict[str, int]:
        counts = {}
        for cell in self.data["cells"]:
            cell_type = cell["type"]
            counts[cell_type] = counts.get(cell_type, 0) + 1
        return counts
