#!/usr/bin/env python3
"""
Center template matcher basé sur le manifest généré par s21_templates_analyzer.
Charge les templates moyens RGB (zone centrale 10×10) et applique une classification
par distance L2 avec seuils adaptatifs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Any

import numpy as np
from PIL import Image

from src.config import CELL_SIZE


def _default_manifest_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "s21_templates_analyzer"
        / "template_artifact"
        / "central_templates_manifest.json"
    )


@dataclass
class TemplateData:
    symbol: str
    mean: np.ndarray
    std: np.ndarray
    threshold: float
    image_count: int
    preview_path: Optional[Path] = None


@dataclass
class MatchResult:
    symbol: str
    distance: float
    threshold: Optional[float]
    distances: Dict[str, float]
    margin: int

    @property
    def confidence(self) -> float:
        if not self.threshold or self.threshold <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.distance / (self.threshold + 1e-6)))


class CenterTemplateMatcher:
    """Charge les templates centraux et fournit un API de classification."""

    UNIFORM_THRESHOLDS: Dict[str, float] = {
        "unrevealed": 100.0,
        "empty": 20.0,
        "question_mark": 100.0,
    }
    DECOR_SYMBOLS = {"decor"}
    DISTANCE_GUARD: int = 1  # Ignore 1 px sur le bord de la zone centrale (équiv. marge 8)
    UNREVEALED_WHITE_THRESHOLD: float = 235.0
    UNREVEALED_WHITE_RATIO: float = 0.75
    SYMBOL_PRIORITY: Tuple[str, ...] = (
        "unrevealed",
        "exploded",
        "flag",
        "number_1",
        "number_2",
        "number_3",
        "number_4",
        "number_5",
        "number_6",
        "number_7",
        "number_8",
        "empty",
        "question_mark",
    )
    TEMPLATE_SKIP_SYMBOLS = {"unrevealed", "exploded"}

    def __init__(self, manifest_path: Optional[str | Path] = None):
        self.manifest_path = Path(manifest_path or _default_manifest_path())
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest introuvable: {self.manifest_path}")
        self.margin: int = 7
        self.templates: Dict[str, TemplateData] = {}
        self._load_manifest()

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------
    def _load_manifest(self) -> None:
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
                preview_path=(base_dir / payload["preview_file"])
                if "preview_file" in payload
                else None,
            )

        if not self.templates:
            raise ValueError(f"Manifest {self.manifest_path} ne contient aucun template.")

    # ------------------------------------------------------------------
    # Classification cellule
    # ------------------------------------------------------------------
    def classify_cell(
        self,
        cell_image: Image.Image | np.ndarray,
        allowed_symbols: Optional[Iterable[str]] = None,
    ) -> MatchResult:
        cell_rgb = self._to_rgb_array(cell_image)
        if cell_rgb.shape[0] != CELL_SIZE or cell_rgb.shape[1] != CELL_SIZE:
            raise ValueError(f"cell_image doit être de taille {CELL_SIZE}x{CELL_SIZE}")

        zone = self._extract_zone(cell_rgb)
        zone_distance = self._distance_window(zone)

        uniform_match = self._classify_uniform_zone(zone)
        if uniform_match:
            if uniform_match.symbol == "unrevealed" and not self._is_unrevealed_border_white(cell_rgb):
                exploded_match = self._build_symbol_match("exploded", zone_distance)
                if exploded_match:
                    return exploded_match
                uniform_match = None
            else:
                return uniform_match

        distances: Dict[str, float] = {}

        symbols = tuple(allowed_symbols) if allowed_symbols else tuple(self.templates.keys())
        ordered_symbols = self._ordered_symbols(symbols)
        for symbol in ordered_symbols:
            tpl = self.templates.get(symbol)
            if tpl is None:
                continue
            tpl_mean = self._distance_window(tpl.mean)
            diff = zone_distance - tpl_mean
            dist = float(np.linalg.norm(diff))
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

    # ------------------------------------------------------------------
    # Classification grille
    # ------------------------------------------------------------------
    def classify_grid(
        self,
        image: Image.Image,
        grid_top_left: Tuple[int, int],
        grid_size: Tuple[int, int],
        stride: int = CELL_SIZE,
        allowed_symbols: Optional[Iterable[str]] = None,
        known_set: Optional[set[Tuple[int, int]]] = None,
        bounds_offset: Optional[Tuple[int, int]] = None,
    ) -> Dict[Tuple[int, int], MatchResult]:
        start_x, start_y = grid_top_left
        cols, rows = grid_size
        image_np = np.array(image.convert("RGB"))
        results: Dict[Tuple[int, int], MatchResult] = {}

        # Use bounds_offset for coordinate conversion if provided (for known_set filtering)
        offset_x, offset_y = bounds_offset if bounds_offset else (start_x, start_y)

        # Skip cells already known if known_set is provided
        for row in range(rows):
            for col in range(cols):
                # Convert to absolute grid coordinates for known_set checking
                abs_x = offset_x + col
                abs_y = offset_y + row
                
                # Skip if cell is already known
                if known_set is not None and (abs_x, abs_y) in known_set:
                    continue
                    
                x0 = start_x + col * stride
                y0 = start_y + row * stride
                cell = image_np[y0 : y0 + CELL_SIZE, x0 : x0 + CELL_SIZE]
                if cell.shape[0] != CELL_SIZE or cell.shape[1] != CELL_SIZE:
                    continue
                result = self.classify_cell(cell, allowed_symbols)
                results[(row, col)] = result

        return results

    # ------------------------------------------------------------------
    # Debug / overlay helpers
    # ------------------------------------------------------------------
    def as_debug_dict(self) -> Dict[str, Any]:
        return {
            "manifest": str(self.manifest_path),
            "margin": self.margin,
            "templates": {
                name: {
                    "threshold": tpl.threshold,
                    "image_count": tpl.image_count,
                    "preview": str(tpl.preview_path) if tpl.preview_path else None,
                }
                for name, tpl in self.templates.items()
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_zone(self, cell_rgb: np.ndarray) -> np.ndarray:
        m = self.margin
        return cell_rgb[m : CELL_SIZE - m, m : CELL_SIZE - m, :].astype(np.float32)

    def _ordered_symbols(self, symbols: Iterable[str]) -> Tuple[str, ...]:
        symbol_set = tuple(symbols)
        ordered: list[str] = []
        seen: set[str] = set()
        for symbol in self.SYMBOL_PRIORITY:
            if symbol in self.DECOR_SYMBOLS:
                continue
            if symbol in symbol_set and symbol in self.templates:
                ordered.append(symbol)
                seen.add(symbol)
        for symbol in symbol_set:
            if symbol in seen or symbol in self.DECOR_SYMBOLS:
                continue
            if symbol in self.templates:
                ordered.append(symbol)
                seen.add(symbol)
        return tuple(ordered)

    def _match_decor(
        self,
        zone_distance: np.ndarray,
        distances: Dict[str, float],
        symbols: Iterable[str],
    ) -> Optional[MatchResult]:
        for symbol in symbols:
            if symbol not in self.DECOR_SYMBOLS:
                continue
            tpl = self.templates.get(symbol)
            if not tpl:
                continue
            if symbol in distances:
                dist = distances[symbol]
            else:
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
        return None

    def _is_unrevealed_border_white(self, cell_rgb: np.ndarray) -> bool:
        """Vérifie un pixel discriminant sur la périphérie pour confirmer unrevealed."""
        # On échantillonne un petit losange sur la bordure proche pour éviter le centre.
        coords = (
            (2, 2),
            (CELL_SIZE - 3, 2),
            (2, CELL_SIZE - 3),
            (CELL_SIZE - 3, CELL_SIZE - 3),
        )
        for y, x in coords:
            pixel = cell_rgb[y, x]
            if np.all(pixel >= self.UNREVEALED_WHITE_THRESHOLD):
                return True
        return False

    def _build_symbol_match(self, symbol: str, zone_distance: np.ndarray) -> Optional[MatchResult]:
        tpl = self.templates.get(symbol)
        if not tpl:
            return None
        tpl_mean = self._distance_window(tpl.mean)
        dist = float(np.linalg.norm(zone_distance - tpl_mean))
        threshold = self._effective_threshold(tpl)
        return MatchResult(
            symbol=symbol,
            distance=dist,
            threshold=threshold,
            distances={symbol: dist},
            margin=self.margin,
        )

    @staticmethod
    def _to_rgb_array(cell_image: Image.Image | np.ndarray) -> np.ndarray:
        if isinstance(cell_image, Image.Image):
            arr = np.array(cell_image.convert("RGB"), dtype=np.float32)
        else:
            arr = np.asarray(cell_image, dtype=np.float32)
            if arr.ndim == 2:
                arr = np.repeat(arr[:, :, None], 3, axis=2)
            if arr.shape[-1] != 3:
                raise ValueError("cell_image doit contenir 3 canaux RGB")
        return arr

    # ------------------------------------------------------------------
    # Uniform heuristics & thresholds
    # ------------------------------------------------------------------
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
        threshold = self._effective_threshold(tpl)
        return MatchResult(
            symbol=symbol,
            distance=dist,
            threshold=threshold,
            distances={symbol: dist},
            margin=self.margin,
        )

    def _effective_threshold(self, tpl: TemplateData) -> float:
        if tpl.threshold > 0:
            return tpl.threshold
        return self.UNIFORM_THRESHOLDS.get(tpl.symbol, 150.0)

    def _distance_window(self, arr: np.ndarray) -> np.ndarray:
        guard = self.DISTANCE_GUARD
        if guard <= 0:
            return arr
        if guard * 2 >= arr.shape[0] or guard * 2 >= arr.shape[1]:
            return arr
        return arr[guard : arr.shape[0] - guard, guard : arr.shape[1] - guard, :]
