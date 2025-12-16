from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionContext:
    game_id: Optional[str] = None
    iteration: Optional[int] = None
    export_root: Optional[str] = None
    overlay_enabled: bool = False
    capture_saved_path: Optional[str] = None
    capture_bounds: Optional[tuple[int, int, int, int]] = None
    capture_stride: Optional[int] = None


_SESSION_CONTEXT = SessionContext()


def set_session_context(
    game_id: str,
    iteration: int,
    export_root: str,
    overlay_enabled: bool = False,
) -> None:
    """Initialise le contexte de partie (identifiants, chemins, flags)."""
    _SESSION_CONTEXT.game_id = game_id
    _SESSION_CONTEXT.iteration = iteration
    _SESSION_CONTEXT.export_root = export_root
    _SESSION_CONTEXT.overlay_enabled = overlay_enabled


def update_capture_path(saved_path: str) -> None:
    """Enregistre le chemin de capture persistée (exposé par la capture)."""
    _SESSION_CONTEXT.capture_saved_path = saved_path


def update_capture_metadata(saved_path: str, bounds: tuple[int, int, int, int], stride: int) -> None:
    """Enregistre le chemin de capture + bounds + stride pour les overlays."""
    _SESSION_CONTEXT.capture_saved_path = saved_path
    _SESSION_CONTEXT.capture_bounds = bounds
    _SESSION_CONTEXT.capture_stride = stride


def get_session_context() -> SessionContext:
    """Retourne le contexte courant (lecture seule)."""
    return _SESSION_CONTEXT

