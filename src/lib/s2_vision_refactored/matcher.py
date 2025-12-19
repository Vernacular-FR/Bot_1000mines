"""Template matcher pour la reconnaissance des cellules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Any

import numpy as np
from PIL import Image

from src.config import CELL_SIZE
from .types import MatchResult


def _default_manifest_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "s2_vision_old"
        / "s21_templates_analyzer"
        / "template_artifact"
        / "central_templates_manifest.json"
    )


@dataclass
class TemplateData:
    """Données d'un template."""
    symbol: str
    mean: np.ndarray
    std: np.ndarray
    threshold: float
    image_count: int
    preview_path: Optional[Path] = None


class CenterTemplateMatcher:
    """Classification par templates centraux."""

    UNIFORM_THRESHOLDS: Dict[str, float] = {
        "unrevealed": 100.0,
        "empty": 20.0,
        "question_mark": 100.0,
    }
    DECOR_SYMBOLS = {"decor"}
    DISTANCE_GUARD: int = 1
    UNREVEALED_WHITE_THRESHOLD: float = 235.0
    SYMBOL_PRIORITY: Tuple[str, ...] = (
        "unrevealed", "exploded", "flag",
        "number_1", "number_2", "number_3", "number_4",
        "number_5", "number_6", "number_7", "number_8",
        "empty", "question_mark",
    )

    def __init__(self, manifest_path: Optional[str | Path] = None):
        self.manifest_path = Path(manifest_path or _default_manifest_path())
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest introuvable: {self.manifest_path}")
        self.margin: int = 7
        self.templates: Dict[str, TemplateData] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        """Charge le manifest des templates."""
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.margin = int(data.get("margin", 7))
        base_dir = self.manifest_path.parent

        for symbol, payload in data.get("templates", {}).items():
            mean = np.load(base_dir / payload["mean_template_file"])
            std = np.load(base_dir / payload["std_template_file"])
            self.templates[symbol] = TemplateData(
                symbol=symbol,
                mean=mean.astype(np.float32),
                std=std.astype(np.float32),
                threshold=float(payload.get("suggested_threshold", 0.0)),
                image_count=int(payload.get("image_count", 0)),
                preview_path=(base_dir / payload["preview_file"]) if "preview_file" in payload else None,
            )

        if not self.templates:
            raise ValueError(f"Manifest {self.manifest_path} ne contient aucun template.")

    def classify_cell(
        self,
        cell_image: Image.Image | np.ndarray,
        allowed_symbols: Optional[Iterable[str]] = None,
    ) -> MatchResult:
        """Classifie une cellule."""
        cell_rgb = self._to_rgb_array(cell_image)
        if cell_rgb.shape[0] != CELL_SIZE or cell_rgb.shape[1] != CELL_SIZE:
            raise ValueError(f"cell_image doit être de taille {CELL_SIZE}x{CELL_SIZE}")

        zone = self._extract_zone(cell_rgb)
        zone_distance = self._distance_window(zone)

        # Heuristique zones uniformes
        uniform_match = self._classify_uniform_zone(zone)
        if uniform_match:
            if uniform_match.symbol == "unrevealed" and not self._is_unrevealed_border_white(cell_rgb):
                exploded_match = self._build_symbol_match("exploded", zone_distance)
                if exploded_match:
                    return exploded_match
            else:
                return uniform_match

        # Classification par templates
        distances: Dict[str, float] = {}
        symbols = tuple(allowed_symbols) if allowed_symbols else tuple(self.templates.keys())
        ordered_symbols = self._ordered_symbols(symbols)

        for symbol in ordered_symbols:
            tpl = self.templates.get(symbol)
            if tpl is None:
                continue
            tpl_mean = self._distance_window(tpl.mean)
            dist = float(np.linalg.norm(zone_distance - tpl_mean))
            distances[symbol] = dist
            threshold = self._effective_threshold(tpl)
            if threshold > 0 and dist < threshold:
                return MatchResult(
                    symbol=symbol,
                    distance=dist,
                    threshold=threshold,
                    distances=distances,
                    margin=self.margin,
                )

        # Fallback decor
        decor_match = self._match_decor(zone_distance, distances, symbols)
        if decor_match:
            return decor_match

        return MatchResult(
            symbol="unknown",
            distance=float("inf"),
            threshold=None,
            distances=distances,
            margin=self.margin,
        )

    def classify_grid(
        self,
        image: Image.Image,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int = CELL_SIZE,
        allowed_symbols: Optional[Iterable[str]] = None,
        known_set: Optional[set] = None,
        bounds_offset: Optional[Tuple[int, int]] = None,
    ) -> Dict[Tuple[int, int], MatchResult]:
        """Classifie une grille complète."""
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        image_np = np.array(image.convert("RGB"))
        results: Dict[Tuple[int, int], MatchResult] = {}

        offset_x, offset_y = bounds_offset if bounds_offset else (0, 0)

        for row in range(rows):
            for col in range(cols):
                abs_x = offset_x + col
                abs_y = offset_y + row
                
                if known_set is not None and (abs_x, abs_y) in known_set:
                    continue
                    
                x0 = start_x + col * stride
                y0 = start_y + row * stride
                cell = image_np[y0:y0 + CELL_SIZE, x0:x0 + CELL_SIZE]
                if cell.shape[0] != CELL_SIZE or cell.shape[1] != CELL_SIZE:
                    continue
                results[(row, col)] = self.classify_cell(cell, allowed_symbols)

        return results

    # === Helpers ===

    def _extract_zone(self, cell_rgb: np.ndarray) -> np.ndarray:
        m = self.margin
        return cell_rgb[m:CELL_SIZE - m, m:CELL_SIZE - m, :].astype(np.float32)

    def _ordered_symbols(self, symbols: Iterable[str]) -> Tuple[str, ...]:
        symbol_set = set(symbols)
        ordered = []
        for symbol in self.SYMBOL_PRIORITY:
            if symbol in symbol_set and symbol in self.templates:
                ordered.append(symbol)
        for symbol in symbols:
            if symbol not in ordered and symbol in self.templates:
                ordered.append(symbol)
        return tuple(ordered)

    def _classify_uniform_zone(self, zone: np.ndarray) -> Optional[MatchResult]:
        std = float(zone.std())
        mean = float(zone.mean())
        if std > 4.0:
            return None
        if mean >= 230.0:
            return self._build_uniform_match("unrevealed", zone)
        if 150.0 <= mean <= 215.0:
            return self._build_uniform_match("empty", zone)
        return None

    def _build_uniform_match(self, symbol: str, zone: np.ndarray) -> Optional[MatchResult]:
        tpl = self.templates.get(symbol)
        if not tpl:
            return None
        zone_distance = self._distance_window(zone)
        tpl_mean = self._distance_window(tpl.mean)
        dist = float(np.linalg.norm(zone_distance - tpl_mean))
        return MatchResult(
            symbol=symbol,
            distance=dist,
            threshold=self._effective_threshold(tpl),
            distances={symbol: dist},
            margin=self.margin,
        )

    def _build_symbol_match(self, symbol: str, zone_distance: np.ndarray) -> Optional[MatchResult]:
        tpl = self.templates.get(symbol)
        if not tpl:
            return None
        tpl_mean = self._distance_window(tpl.mean)
        dist = float(np.linalg.norm(zone_distance - tpl_mean))
        return MatchResult(
            symbol=symbol,
            distance=dist,
            threshold=self._effective_threshold(tpl),
            distances={symbol: dist},
            margin=self.margin,
        )

    def _match_decor(self, zone_distance: np.ndarray, distances: Dict[str, float], symbols: Iterable[str]) -> Optional[MatchResult]:
        for symbol in symbols:
            if symbol not in self.DECOR_SYMBOLS:
                continue
            tpl = self.templates.get(symbol)
            if not tpl:
                continue
            if symbol not in distances:
                tpl_mean = self._distance_window(tpl.mean)
                distances[symbol] = float(np.linalg.norm(zone_distance - tpl_mean))
            threshold = self._effective_threshold(tpl)
            if threshold > 0 and distances[symbol] < threshold:
                return MatchResult(
                    symbol=symbol,
                    distance=distances[symbol],
                    threshold=threshold,
                    distances=distances,
                    margin=self.margin,
                )
        return None

    def _is_unrevealed_border_white(self, cell_rgb: np.ndarray) -> bool:
        coords = ((2, 2), (CELL_SIZE - 3, 2), (2, CELL_SIZE - 3), (CELL_SIZE - 3, CELL_SIZE - 3))
        for y, x in coords:
            if np.all(cell_rgb[y, x] >= self.UNREVEALED_WHITE_THRESHOLD):
                return True
        return False

    def _effective_threshold(self, tpl: TemplateData) -> float:
        if tpl.threshold > 0:
            return tpl.threshold
        return self.UNIFORM_THRESHOLDS.get(tpl.symbol, 150.0)

    def _distance_window(self, arr: np.ndarray) -> np.ndarray:
        guard = self.DISTANCE_GUARD
        if guard <= 0 or guard * 2 >= min(arr.shape[0], arr.shape[1]):
            return arr
        return arr[guard:arr.shape[0] - guard, guard:arr.shape[1] - guard, :]

    @staticmethod
    def _to_rgb_array(cell_image: Image.Image | np.ndarray) -> np.ndarray:
        if isinstance(cell_image, Image.Image):
            return np.array(cell_image.convert("RGB"), dtype=np.float32)
        arr = np.asarray(cell_image, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.repeat(arr[:, :, None], 3, axis=2)
        return arr
