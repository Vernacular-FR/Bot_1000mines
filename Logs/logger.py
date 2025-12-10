"""
Module de logging centralisé pour le bot 1000mines.com
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class GameLogger:
    """Classe centralisée pour gérer les logs de débogage et d'extraction"""
    
    def __init__(self, logs_dir: str = "Logs"):
        self.logs_dir = logs_dir
        self._ensure_logs_dir()
    
    def _ensure_logs_dir(self):
        """Crée le dossier Logs s'il n'existe pas"""
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
    
    def save_extraction_log(self, 
                          debug_info: Dict[str, Any], 
                          game_state: Optional[Dict] = None,
                          extraction_type: str = "game_state",
                          url: str = "https://www.1000mines.com/") -> str:
        """
        Sauvegarde les logs d'extraction dans un fichier JSON
        
        Args:
            debug_info: Informations de débogage
            game_state: État du jeu trouvé (si succès)
            extraction_type: Type d'extraction (game_state, canvas, etc.)
            url: URL de la page
            
        Returns:
            str: Chemin du fichier de log créé
        """
        try:
            # Nom de fichier avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.logs_dir, f"{extraction_type}_{timestamp}.json")
            
            # Préparer les données à sauvegarder
            log_data = {
                "timestamp": timestamp,
                "extraction_type": extraction_type,
                "url": url,
                "success": game_state is not None,
                "debug_info": debug_info,
                "game_state": game_state if game_state else None
            }
            
            # Sauvegarder en JSON
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            print(f"\nLogs de debogage sauvegardes dans: {log_file}")
            return log_file
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des logs: {e}")
            return ""
    
    def save_bot_log(self, 
                    action: str, 
                    details: Dict[str, Any],
                    success: bool = True) -> str:
        """
        Sauvegarde les logs d'actions du bot
        
        Args:
            action: Action effectuée (ex: "click_cell", "move_view", etc.)
            details: Détails de l'action
            success: Si l'action a réussi
            
        Returns:
            str: Chemin du fichier de log créé
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = os.path.join(self.logs_dir, f"bot_action_{timestamp}.json")
            
            log_data = {
                "timestamp": timestamp,
                "action": action,
                "success": success,
                "details": details
            }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            return log_file
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du log bot: {e}")
            return ""
    
    def get_latest_log(self, extraction_type: str = "game_state") -> Optional[str]:
        """
        Récupère le fichier de log le plus récent pour un type donné
        
        Args:
            extraction_type: Type d'extraction
            
        Returns:
            str: Chemin du fichier de log le plus récent ou None
        """
        try:
            files = [f for f in os.listdir(self.logs_dir) 
                    if f.startswith(f"{extraction_type}_") and f.endswith(".json")]
            
            if not files:
                return None
            
            # Trier par timestamp (nom de fichier)
            files.sort(reverse=True)
            return os.path.join(self.logs_dir, files[0])
            
        except Exception as e:
            print(f"Erreur lors de la récupération du dernier log: {e}")
            return None


# Instance globale du logger
_game_logger = None


def get_logger() -> GameLogger:
    """Retourne l'instance globale du logger"""
    global _game_logger
    if _game_logger is None:
        _game_logger = GameLogger()
    return _game_logger


def save_extraction_log(debug_info: Dict[str, Any], 
                       game_state: Optional[Dict] = None,
                       extraction_type: str = "game_state",
                       url: str = "https://www.1000mines.com/") -> str:
    """
    Fonction pratique pour sauvegarder les logs d'extraction
    """
    return get_logger().save_extraction_log(debug_info, game_state, extraction_type, url)


def save_bot_log(action: str, 
                details: Dict[str, Any],
                success: bool = True) -> str:
    """
    Fonction pratique pour sauvegarder les logs du bot
    """
    return get_logger().save_bot_log(action, details, success)
