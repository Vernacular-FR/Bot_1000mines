#!/usr/bin/env python3
"""
Gestionnaire centralisé de session de jeu
Gère l'identifiant de partie et le numéro d'itération de manière centralisée
"""

import json
import time
import os
import shutil
from typing import Optional, Dict
from datetime import datetime


class SessionState:
    """Gestion de l'identité et des métadonnées de partie."""

    def __init__(self):
        self.game_id: Optional[str] = None
        self.iteration_num: int = 1
        self.session_start_time: Optional[datetime] = None
        self.difficulty: Optional[str] = None

    def spawn_new_game(self, difficulty: Optional[str] = None) -> str:
        """Crée un nouvel ID de partie et réinitialise les compteurs."""
        self.game_id = self._generate_game_id()
        self.iteration_num = 1
        self.session_start_time = datetime.now()
        if difficulty is not None:
            self.difficulty = difficulty
        return self.game_id

    def increment_iteration(self) -> int:
        self.iteration_num += 1
        return self.iteration_num

    def reset(self):
        self.game_id = None
        self.iteration_num = 1
        self.session_start_time = None

    @classmethod
    def create_new_session(cls):
        """Crée une nouvelle session complète (state + storage)"""
        state = cls()
        return {
            'state': state,
            'storage': SessionStorage()
        }

    def is_active(self) -> bool:
        return self.game_id is not None and self.session_start_time is not None

    @property
    def session_duration(self) -> Optional[float]:
        """Durée de la session en secondes"""
        return self.get_session_duration()

    def get_session_duration(self) -> Optional[float]:
        if self.session_start_time is None:
            return None
        return (datetime.now() - self.session_start_time).total_seconds()

    @staticmethod
    def _generate_game_id() -> str:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return timestamp


class SessionStorage:
    """Responsable des chemins et de l'arborescence temp/games."""

    def __init__(self, root_dir: str = "temp/games"):
        self.root_dir = root_dir

    def cleanup_old_games(self, max_games_to_keep: int = 3):
        games_dir = self.root_dir
        if not os.path.exists(games_dir):
            return

        try:
            game_folders = [d for d in os.listdir(games_dir)
                           if os.path.isdir(os.path.join(games_dir, d))]
            game_folders.sort(reverse=True)

            for folder in game_folders[max_games_to_keep:]:
                folder_path = os.path.join(games_dir, folder)
                try:
                    shutil.rmtree(folder_path)
                    print(f"[CLEANUP] Ancienne partie supprimée: {folder}")
                except Exception as e:
                    print(f"[CLEANUP] Erreur suppression {folder}: {e}")
        except Exception as e:
            print(f"[CLEANUP] Erreur nettoyage parties: {e}")

    def get_game_base_path(self, game_id: str) -> str:
        if not game_id:
            raise ValueError("Aucune partie initialisée.")
        return os.path.join(self.root_dir, game_id)

    def build_game_paths(self, game_id: str) -> Dict[str, str]:
        base = self.get_game_base_path(game_id)
        return {
            'raw_canvases': os.path.join(base, "s1_raw_canvases"),
            'vision': os.path.join(base, "s2_vision"),
            'solver': os.path.join(base, "solver),
            'metadata': os.path.join(base, "metadata.json"),
            'grid_state_db': os.path.join(base, "grid_state_db.json")
        }

    def ensure_storage_ready(self, state: SessionState, create_metadata: bool = True) -> Dict[str, Dict[str, str]]:
        if not state.game_id:
            raise ValueError("Aucune partie initialisée.")

        paths = self.build_game_paths(state.game_id)
        base_path = self.get_game_base_path(state.game_id)
        os.makedirs(base_path, exist_ok=True)

        for key, path in paths.items():
            target_dir = path if key not in {"metadata", "grid_state_db"} else os.path.dirname(path)
            os.makedirs(target_dir, exist_ok=True)

        if create_metadata and 'metadata' in paths:
            self._ensure_metadata_file(paths['metadata'], state)

        return {'paths': paths, 'base_path': base_path}

    @staticmethod
    def _ensure_metadata_file(metadata_path: str, state: SessionState):
        if os.path.exists(metadata_path):
            return

        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
        start_time = state.session_start_time or datetime.now()
        
        metadata = {
            "game_id": state.game_id,
            "difficulty": state.difficulty,
            "start_time": start_time.isoformat(),
            "initial_iteration": state.iteration_num,
            "status": "playing"
        }

        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=4)


# Instance globale du gestionnaire de session
# Réinitialisée à chaque import pour éviter la persistance entre exécutions
def get_game_session():
    """Retourne une nouvelle instance de session (SessionState + SessionStorage)"""
    return {
        'state': SessionState(),
        'storage': SessionStorage()
    }