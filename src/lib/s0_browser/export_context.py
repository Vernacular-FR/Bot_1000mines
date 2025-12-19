"""
Contexte d'export pour les overlays et artefacts de debug.

Gère game_id, iteration, export_root et fournit les chemins standardisés
pour tous les modules qui génèrent des overlays (vision, solver, etc.).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime


@dataclass
class ExportContext:
    """Contexte partagé pour l'export des overlays et artefacts."""
    
    game_id: str
    export_root: Path
    iteration: int = 0
    overlay_enabled: bool = False
    
    # Métadonnées de capture (remplies par s1_capture)
    capture_path: Optional[Path] = None
    capture_bounds: Optional[tuple[int, int, int, int]] = None
    capture_stride: Optional[int] = None
    
    # Métriques accumulées
    _overlay_count: int = field(default=0, repr=False)
    
    @classmethod
    def create(
        cls,
        game_id: Optional[str] = None,
        base_dir: Optional[Path] = None,
        overlay_enabled: bool = True,
    ) -> "ExportContext":
        """Crée un nouveau contexte d'export avec un game_id unique.

        Chemins alignés sur l'archi : temp/games/<game_id>/...
        """
        if game_id is None:
            game_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Racine par défaut : temp/games/<game_id>
        if base_dir is None:
            base_dir = Path("temp") / "games"
        
        export_root = base_dir / game_id
        export_root.mkdir(parents=True, exist_ok=True)
        
        return cls(
            game_id=game_id,
            export_root=export_root,
            overlay_enabled=overlay_enabled,
        )
    
    def next_iteration(self) -> int:
        """Incrémente et retourne le numéro d'itération."""
        self.iteration += 1
        return self.iteration
    
    def update_capture_metadata(
        self,
        capture_path: Path,
        bounds: tuple[int, int, int, int],
        stride: int,
    ) -> None:
        """Met à jour les métadonnées de capture pour les overlays."""
        self.capture_path = capture_path
        self.capture_bounds = bounds
        self.capture_stride = stride
    
    # --- Chemins standardisés ---
    
    def get_vision_overlay_dir(self) -> Path:
        """Répertoire pour les overlays vision."""
        path = self.export_root / "s2_vision" 
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_solver_overlay_dir(self, overlay_type: str | None = None) -> Path:
        """Répertoire pour les overlays solver, organisé par sous-modules (s4a/s4b/s4c)."""
        base = self.export_root 
        # Organisation par sous-dossier pour les overlays solver
        if overlay_type:
            path = base / overlay_type
        else:
            path = base
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_capture_dir(self) -> Path:
        """Répertoire pour les captures."""
        path = self.export_root / "s1_capture"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_json_dir(self, module: str) -> Path:
        """Répertoire JSON pour un module donné."""
        path = self.export_root / module / "json"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    # --- Noms de fichiers ---
    
    def vision_overlay_filename(self, suffix: str = "") -> str:
        """Génère un nom de fichier pour overlay vision."""
        base = f"vision_iter_{self.iteration:04d}"
        return f"{base}_{suffix}.png" if suffix else f"{base}.png"
    
    def solver_overlay_filename(self, overlay_type: str = "combined") -> str:
        """Génère un nom de fichier pour overlay solver."""
        return f"solver_iter_{self.iteration:04d}_{overlay_type}.png"
    
    def json_filename(self, module: str, suffix: str = "") -> str:
        """Génère un nom de fichier JSON."""
        module_safe = module.replace("/", "_")
        base = f"{module_safe}_iter_{self.iteration:04d}"
        return f"{base}_{suffix}.json" if suffix else f"{base}.json"
    
    # --- Chemins complets ---
    
    def vision_overlay_path(self, suffix: str = "") -> Path:
        """Chemin complet pour un overlay vision."""
        return self.get_vision_overlay_dir() / self.vision_overlay_filename(suffix)
    
    def solver_overlay_path(self, overlay_type: str = "combined") -> Path:
        """Chemin complet pour un overlay solver (organisé par sous-dossier)."""
        return self.get_solver_overlay_dir(overlay_type) / self.solver_overlay_filename(overlay_type)
    
    def json_path(self, module: str, suffix: str = "") -> Path:
        """Chemin complet pour un fichier JSON."""
        return self.get_json_dir(module) / self.json_filename(module, suffix)


# Contexte global (optionnel, pour compatibilité legacy)
_EXPORT_CONTEXT: Optional[ExportContext] = None


def set_export_context(ctx: ExportContext) -> None:
    """Définit le contexte d'export global."""
    global _EXPORT_CONTEXT
    _EXPORT_CONTEXT = ctx


def get_export_context() -> Optional[ExportContext]:
    """Retourne le contexte d'export global (ou None)."""
    return _EXPORT_CONTEXT


def clear_export_context() -> None:
    """Efface le contexte d'export global."""
    global _EXPORT_CONTEXT
    _EXPORT_CONTEXT = None
