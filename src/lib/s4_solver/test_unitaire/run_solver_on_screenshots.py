#!/usr/bin/env python3
"""Pipeline complet de vision + solver sur les screenshots locaux."""

from __future__ import annotations

import re
import shutil
import sys
import threading
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# Ensure project root (containing the `src` package) is on sys.path when running standalone
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # Go up from test_unitaire -> s4_solver -> lib -> src -> project_root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_BORDER, CELL_SIZE
from src.lib.s2_vision.facade import VisionAPI, VisionControllerConfig
from src.lib.s2_vision.s21_template_matcher import MatchResult
from src.lib.s3_storage.facade import CellState, GridCell, StorageControllerApi, StorageUpsert
from src.lib.s4_solver.controller import SolverController
from src.lib.s4_solver.facade import SolverAction, SolverActionType
from src.lib.s3_storage.controller import StorageController

Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER
BOUNDS_PATTERN = re.compile(r"zone_(?P<sx>-?\d+)_(?P<sy>-?\d+)_(?P<ex>-?\d+)_(?P<ey>-?\d+)\.png$")

ACTIONS_COLORS = {
    SolverActionType.CLICK: (0, 200, 0, 160),
    SolverActionType.FLAG: (255, 0, 0, 160),
    SolverActionType.GUESS: (255, 165, 0, 160),
}

# Local directories for this test
RAW_GRID_DIR = Path(__file__).parent / "00_raw_grid"
VISION_OVERLAYS_DIR = Path(__file__).parent / "vision_overlays"
SEGMENTATION_OVERLAYS_DIR = Path(__file__).parent / "segmentation_overlay"
PATTERN_OVERLAYS_DIR = Path(__file__).parent / "pattern_overlays"
CSP_OVERLAYS_DIR = Path(__file__).parent / "csp_overlays"


def parse_bounds(path: Path) -> Optional[Bounds]:
    """Extrait les coordonnées de grille depuis le nom de fichier."""
    match = BOUNDS_PATTERN.search(path.name)
    if not match:
        return None
    return (
        int(match.group("sx")),
        int(match.group("sy")),
        int(match.group("ex")),
        int(match.group("ey")),
    )


from src.lib.s4_solver.vision_to_storage import matches_to_upsert


def render_segmentation_overlay(screenshot: Path, bounds: Bounds, solver, out_dir: Path) -> None:
    """Génère un overlay visuel avec la segmentation du solver."""
    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 10)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, end_x, end_y = bounds
    
    # Debug: vérifier l'accès au solver stocké
    print(f"[DEBUG SEG] Bounds: {bounds}")
    
    # Obtenir la segmentation depuis le solver stocké
    if hasattr(solver, '_solver') and solver._solver is not None:
        print(f"[DEBUG SEG] Solver has stored _solver")
        segmentation = solver._solver.segmentation
        
        print(f"[DEBUG SEG] Segmentation has {len(segmentation.components)} components")
        print(f"[DEBUG SEG] Segmentation has {len(segmentation.zones)} zones")
        
        # Générer des couleurs pour les composants
        colors = {}
        
        # Dessiner les composants (zones avec même couleur par composant)
        for comp in segmentation.components:
            if comp.id not in colors:
                # Couleur aléatoire distincte par composant
                r = random.randint(50, 200)
                g = random.randint(50, 200)
                b = random.randint(50, 200)
                colors[comp.id] = (r, g, b, 180)  # Alpha 180
            
            color = colors[comp.id]
            
            # Dessiner toutes les zones de ce composant avec la même couleur
            for zone in comp.zones:
                for (x, y) in zone.cells:
                    pixel_x = (x - start_x) * STRIDE
                    pixel_y = (y - start_y) * STRIDE
                    
                    box = [
                        pixel_x, pixel_y,
                        pixel_x + CELL_SIZE, pixel_y + CELL_SIZE
                    ]
                    
                    # Remplir la zone
                    draw.rectangle(box, fill=color)
                    
                # Ajouter ID de zone pour chaque zone
                for (x, y) in zone.cells:
                    pixel_x = (x - start_x) * STRIDE
                    pixel_y = (y - start_y) * STRIDE
                    text_pos = (pixel_x + 2, pixel_y + 2)
                    draw.text(text_pos, f"Z{zone.id}", fill=(255, 255, 255), font=font)

        # Dessiner les contraintes (cellules numérotées)
        constraint_cells = set()
        for zone in segmentation.zones:
            for c in zone.constraints:
                constraint_cells.add(c)
                
        for (cx, cy) in constraint_cells:
            pixel_x = (cx - start_x) * STRIDE
            pixel_y = (cy - start_y) * STRIDE
             
            box = [
                pixel_x, pixel_y,
                pixel_x + CELL_SIZE, pixel_y + CELL_SIZE
            ]
            draw.rectangle(box, outline=(255, 0, 0, 255), width=2)
    else:
        print(f"[DEBUG SEG] Solver has no stored _solver or _solver is None!")

    composed = Image.alpha_composite(image, overlay)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{screenshot.stem}_segmentation_overlay.png"
    composed.save(out_path)
    print(f"[SEGMENTATION] Overlay sauvegardé: {out_path.name}")


def render_actions_overlay(
    screenshot: Path, bounds: Bounds, actions: List[SolverAction], out_dir: Path
) -> None:
    """Génère un overlay visuel avec les actions du solver."""
    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, end_x, end_y = bounds
    
    for i, action in enumerate(actions):
        try:
            # Vérifier que l'action a les bons attributs
            if not hasattr(action, 'cell') or not hasattr(action, 'type'):
                print(f"[WARNING] Action {i} manque des attributs requis: {action}")
                continue
                
            # Vérifier que cell est un tuple
            if not isinstance(action.cell, (tuple, list)) or len(action.cell) != 2:
                print(f"[WARNING] Action {i} cell invalide: {action.cell}")
                continue
                
            cell_x, cell_y = action.cell
            x = (cell_x - start_x) * STRIDE
            y = (cell_y - start_y) * STRIDE
            
            color = ACTIONS_COLORS.get(action.type, (128, 128, 128, 160))
            
            # Dessiner le rectangle de l'action
            draw.rectangle(
                [(x, y), (x + CELL_SIZE, y + CELL_SIZE)],
                fill=color,
                outline=(255, 255, 255, 255),
                width=2,
            )
            
            # Ajouter le label
            if action.type == SolverActionType.CLICK:
                label = "SAFE"
            elif action.type == SolverActionType.FLAG:
                label = "FLAG"
            else:
                label = "GUESS"
                
            draw.text((x + 3, y + 3), label, font=font, fill=(255, 255, 255, 255))
            
        except Exception as e:
            print(f"[ERROR] Impossible de dessiner l'action {i}: {e}")
            continue

    composed = Image.alpha_composite(image, overlay)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{screenshot.stem}_solver_overlay.png"
    composed.save(out_path)


def render_phase_overlay(
    screenshot: Path,
    bounds: Bounds,
    safe_cells: List[Coord],
    flag_cells: List[Coord],
    out_dir: Path,
    suffix: str,
) -> None:
    """Rendu générique pour les phases 0 et 1 (avant CSP)."""
    if not safe_cells and not flag_cells:
        return

    actions: List[SolverAction] = []
    for cell in safe_cells:
        actions.append(
            SolverAction(cell=cell, type=SolverActionType.CLICK, confidence=1.0, reasoning=suffix)
        )
    for cell in flag_cells:
        actions.append(
            SolverAction(cell=cell, type=SolverActionType.FLAG, confidence=1.0, reasoning=suffix)
        )

    image = Image.open(screenshot).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    start_x, start_y, _, _ = bounds

    for action in actions:
        cell_x, cell_y = action.cell
        x = (cell_x - start_x) * STRIDE
        y = (cell_y - start_y) * STRIDE
        color = ACTIONS_COLORS.get(action.type, (128, 128, 128, 160))
        draw.rectangle(
            [(x, y), (x + CELL_SIZE, y + CELL_SIZE)],
            fill=color,
            outline=(255, 255, 255, 255),
            width=2,
        )
        label = "SAFE" if action.type == SolverActionType.CLICK else "FLAG"
        draw.text((x + 3, y + 3), f"{label}-{suffix}", font=font, fill=(255, 255, 255, 255))

    composed = Image.alpha_composite(image, overlay)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{screenshot.stem}_{suffix}_overlay.png"
    composed.save(out_path)


def run_vision_pipeline(screenshot: Path) -> Optional[Dict[Tuple[int, int], MatchResult]]:
    """Exécute le pipeline de vision et génère l'overlay. Renvoie les matches pour réutilisation."""
    print(f"[VISION] Analyse de {screenshot.name}...")
    
    bounds = parse_bounds(screenshot)
    if not bounds:
        print(f"[SKIP] Impossible de parser les bornes: {screenshot.name}")
        return None

    start_x, start_y, end_x, end_y = bounds
    grid_width = end_x - start_x + 1
    grid_height = end_y - start_y + 1

    # Initialiser VisionAPI pour ce test
    vision = VisionAPI(VisionControllerConfig(
        overlay_output_dir=VISION_OVERLAYS_DIR
    ))

    # Analyse avec overlay
    matches = vision.analyze_screenshot(
        screenshot_path=str(screenshot),
        grid_top_left=(0, 0),
        grid_size=(grid_width, grid_height),
        stride=STRIDE,
        overlay=True,
    )
    
    # Déplacer l'overlay généré vers notre répertoire local
    expected_overlay = vision.controller.config.overlay_output_dir / f"{screenshot.stem}_overlay.png"
    vision_overlay_path = VISION_OVERLAYS_DIR / f"{screenshot.stem}_vision_overlay.png"
    
    if expected_overlay.exists():
        if vision_overlay_path.exists():
            vision_overlay_path.unlink()
        shutil.move(str(expected_overlay), str(vision_overlay_path))
        print(f"[VISION] Overlay sauvegardé: {vision_overlay_path.name}")
        return matches
    else:
        print(f"[VISION] Overlay non trouvé")
        return None


def run_solver_thread_func(solver, result_list):
    """Fonction thread avec gestion d'erreurs."""
    try:
        result = solver.solve()
        result_list.append(result)
    except Exception as e:
        import traceback
        print(f"[ERROR] Exception dans solver.solve(): {e}")
        result_list.append(("ERROR", e))


def run_solver_pipeline(
    screenshot: Path, cached_matches: Optional[Dict[Tuple[int, int], MatchResult]] = None
) -> bool:
    """Exécute le pipeline solver et génère l'overlay."""
    print(f"[SOLVER] Traitement de {screenshot.name}...")
    
    bounds = parse_bounds(screenshot)
    if not bounds:
        return False

    start_x, start_y, end_x, end_y = bounds
    grid_width = end_x - start_x + 1
    grid_height = end_y - start_y + 1

    if cached_matches is None:
        # Analyse vision pour le solver (fallback)
        vision = VisionAPI(VisionControllerConfig())
        matches = vision.analyze_screenshot(
            screenshot_path=str(screenshot),
            grid_top_left=(0, 0),
            grid_size=(grid_width, grid_height),
            stride=STRIDE,
            overlay=False,
        )
    else:
        matches = cached_matches
    
    # Conversion vers storage
    storage = StorageController()
    upsert = matches_to_upsert(bounds, matches)
    storage.upsert(upsert)

    # Exécution du solver avec timeout
    solver = SolverController(storage)
    
    try:
        class SolverTimeout:
            def __init__(self, timeout_seconds):
                self.timeout = timeout_seconds
                
        timeout = SolverTimeout(15)
        result_list = []
        
        solver_thread = threading.Thread(target=run_solver_thread_func, args=(solver, result_list))
        solver_thread.daemon = True
        solver_thread.start()
        solver_thread.join(timeout.timeout)
        
        if solver_thread.is_alive():
            print(f"[SOLVER] Timeout après 15s")
            return False
            
        if result_list and result_list[0] != "ERROR":
            actions = result_list[0]
            print(f"[SOLVER] {screenshot.name}: {len(actions)} actions trouvées")

            # Overlays phases 00/01
            hybrid = getattr(solver, "_solver", None)
            if hybrid is not None:
                phase00_safe = sorted(hybrid.constraint_safe_cells)
                phase00_flags = sorted(hybrid.constraint_flag_cells)
                render_phase_overlay(
                    screenshot,
                    bounds,
                    phase00_safe,
                    phase00_flags,
                    PATTERN_OVERLAYS_DIR,
                    "phase00",
                )

                phase01_safe = sorted(
                    set(hybrid.constraint_safe_cells) | set(hybrid.pattern_safe_cells)
                )
                phase01_flags = sorted(
                    set(hybrid.constraint_flag_cells) | set(hybrid.pattern_flag_cells)
                )
                render_phase_overlay(
                    screenshot,
                    bounds,
                    phase01_safe,
                    phase01_flags,
                    CSP_OVERLAYS_DIR,
                    "phase01",
                )

            # Générer l'overlay de segmentation
            render_segmentation_overlay(screenshot, bounds, solver, SEGMENTATION_OVERLAYS_DIR)
            
            # Générer l'overlay solver
            render_actions_overlay(screenshot, bounds, actions, SOLVER_OVERLAYS_DIR)
            print(f"[SOLVER] Overlay sauvegardé dans {SOLVER_OVERLAYS_DIR.name}")
            return True
        else:
            print(f"[SOLVER] Erreur: {result_list[0][1] if result_list else 'Unknown'}")
            return False
            
    except Exception as e:
        print(f"[SOLVER] Exception: {e}")
        return False


def main() -> None:
    """Pipeline principal de traitement."""
    print("=" * 60)
    print("PIPELINE VISION + SOLVER SUR SCREENSHOTS LOCAUX")
    print("=" * 60)
    
    # Créer les répertoires de sortie
    VISION_OVERLAYS_DIR.mkdir(exist_ok=True)
    SEGMENTATION_OVERLAYS_DIR.mkdir(exist_ok=True)
    SOLVER_OVERLAYS_DIR.mkdir(exist_ok=True)
    PATTERN_OVERLAYS_DIR.mkdir(exist_ok=True)
    CSP_OVERLAYS_DIR.mkdir(exist_ok=True)
    
    # Lister les screenshots disponibles
    screenshots = sorted(RAW_GRID_DIR.glob("*.png"))
    if not screenshots:
        print(f"[ERROR] Aucun screenshot trouvé dans {RAW_GRID_DIR}")
        return
        
    print(f"[INFO] {len(screenshots)} screenshots trouvés dans {RAW_GRID_DIR.name}")
    
    # Traiter chaque screenshot
    success_count = 0
    for i, screenshot in enumerate(screenshots, 1):
        print(f"\n[{i}/{len(screenshots)}] Traitement de {screenshot.name}")
        print("-" * 50)
        
        try:
            # Étape 1: Pipeline vision
            matches = run_vision_pipeline(screenshot)
            if not matches:
                continue
                
            # Étape 2: Pipeline solver
            solver_ok = run_solver_pipeline(screenshot, cached_matches=matches)
            if solver_ok:
                success_count += 1
                print(f"[SUCCESS] {screenshot.name} traité complètement")
            else:
                print(f"[PARTIAL] {screenshot.name}: vision OK, solver échoué")
                
        except Exception as e:
            print(f"[ERROR] {screenshot.name}: {e}")
            continue
    
    print("\n" + "=" * 60)
    print(f"RÉSUMÉ: {success_count}/{len(screenshots)} screenshots traités avec succès")
    print(f"Vision overlays: {VISION_OVERLAYS_DIR}")
    print(f"Solver overlays: {SOLVER_OVERLAYS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
