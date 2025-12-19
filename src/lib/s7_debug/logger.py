"""Logger structuré pour le debug."""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class IterationLog:
    """Log d'une itération."""
    iteration: int
    timestamp: str
    duration: float
    actions_count: int
    safe_count: int
    flag_count: int
    guess_count: int
    success: bool
    metadata: Dict[str, Any]


@dataclass
class ActionLog:
    """Log d'une action."""
    timestamp: str
    coord: tuple
    action_type: str
    confidence: float
    success: bool
    error: Optional[str] = None


class DebugLogger:
    """Logger structuré pour le debug."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.iterations: List[IterationLog] = []
        self.actions: List[ActionLog] = []

    def log_iteration(
        self,
        iteration: int,
        duration: float,
        actions_count: int,
        safe_count: int = 0,
        flag_count: int = 0,
        guess_count: int = 0,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log une itération."""
        log = IterationLog(
            iteration=iteration,
            timestamp=datetime.now().isoformat(),
            duration=duration,
            actions_count=actions_count,
            safe_count=safe_count,
            flag_count=flag_count,
            guess_count=guess_count,
            success=success,
            metadata=metadata or {},
        )
        self.iterations.append(log)
        self._write_log("iterations", asdict(log))

    def log_action(
        self,
        coord: tuple,
        action_type: str,
        confidence: float,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Log une action."""
        log = ActionLog(
            timestamp=datetime.now().isoformat(),
            coord=coord,
            action_type=action_type,
            confidence=confidence,
            success=success,
            error=error,
        )
        self.actions.append(log)
        self._write_log("actions", asdict(log))

    def save_session(self) -> str:
        """Sauvegarde la session complète."""
        session_file = self.log_dir / f"session_{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "total_iterations": len(self.iterations),
            "total_actions": len(self.actions),
            "iterations": [asdict(i) for i in self.iterations],
            "actions": [asdict(a) for a in self.actions],
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(session_file)

    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé de la session."""
        total_safe = sum(i.safe_count for i in self.iterations)
        total_flag = sum(i.flag_count for i in self.iterations)
        total_guess = sum(i.guess_count for i in self.iterations)
        total_duration = sum(i.duration for i in self.iterations)
        
        return {
            "session_id": self.session_id,
            "iterations": len(self.iterations),
            "total_actions": total_safe + total_flag + total_guess,
            "safe_actions": total_safe,
            "flag_actions": total_flag,
            "guess_actions": total_guess,
            "total_duration": total_duration,
            "success_rate": sum(1 for i in self.iterations if i.success) / max(1, len(self.iterations)),
        }

    def _write_log(self, log_type: str, data: Dict[str, Any]) -> None:
        """Écrit un log dans un fichier."""
        log_file = self.log_dir / f"{log_type}_{self.session_id}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")


# === API fonctionnelle ===

_logger: Optional[DebugLogger] = None


def _get_logger() -> DebugLogger:
    global _logger
    if _logger is None:
        _logger = DebugLogger()
    return _logger


def log_iteration(
    iteration: int,
    duration: float,
    actions_count: int,
    **kwargs,
) -> None:
    """Log une itération."""
    _get_logger().log_iteration(iteration, duration, actions_count, **kwargs)


def log_action(
    coord: tuple,
    action_type: str,
    confidence: float,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Log une action."""
    _get_logger().log_action(coord, action_type, confidence, success, error)
