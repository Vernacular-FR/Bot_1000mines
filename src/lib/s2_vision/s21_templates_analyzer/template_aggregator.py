#!/usr/bin/env python3
"""
Générateur d'agrégats pour le template matching central.

Objectif :
    - Charger les échantillons par symbole.
    - Extraire la zone centrale stable (marge validée à 8 px).
    - Calculer les templates moyens RGB + écarts-types.
    - Mesurer les distances L2 intra-symbole et suggérer un seuil.
    - Sauvegarder tous les artefacts (npz/png/json) dans template_artifact/.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image


@dataclass
class TemplateStats:
    symbol: str
    image_count: int
    template_shape: Tuple[int, int, int]
    margin: int
    mean_distance: float
    std_distance: float
    max_distance: float
    suggested_threshold: float
    mean_template_file: str
    std_template_file: str
    preview_file: str


class TemplateAggregator:
    """
    Construit les templates RGB centraux et les seuils recommandés.
    """

    def __init__(
        self,
        dataset_dir: str,
        artifacts_dir: str,
        margin: int = 8,
    ):
        self.dataset_dir = Path(dataset_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.margin = margin

        if not self.dataset_dir.exists():
            raise FileNotFoundError(f"Dataset introuvable: {self.dataset_dir}")

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Chargement des données
    # ------------------------------------------------------------------ #

    def load_symbol_dataset(self) -> Dict[str, List[np.ndarray]]:
        dataset: Dict[str, List[np.ndarray]] = {}

        for symbol_dir in sorted(self.dataset_dir.iterdir()):
            if not symbol_dir.is_dir():
                continue

            images: List[np.ndarray] = []
            for img_file in sorted(symbol_dir.glob("*.png")):
                try:
                    img = Image.open(img_file).convert("RGB")
                    images.append(np.array(img, dtype=np.uint8))
                except Exception as exc:  # pragma: no cover - log runtime info
                    print(f"[WARN] Lecture impossible {img_file}: {exc}")

            if images:
                dataset[symbol_dir.name] = images
                print(f"[INFO] {symbol_dir.name:<16} → {len(images):4d} images")

        if not dataset:
            raise ValueError(f"Aucun échantillon dans {self.dataset_dir}")

        return dataset

    # ------------------------------------------------------------------ #
    # Calculs centraux
    # ------------------------------------------------------------------ #

    def _extract_central_zone(self, image: np.ndarray) -> np.ndarray:
        h, w, _ = image.shape
        margin = self.margin

        if 2 * margin >= min(h, w):
            raise ValueError(
                f"Marge {margin}px incompatible avec image {h}x{w}. "
                "Réduire la marge dans TemplateAggregator."
            )

        return image[margin : h - margin, margin : w - margin, :]

    def compute_symbol_template(self, images: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        central_crops = np.stack([self._extract_central_zone(img) for img in images], axis=0)
        mean_template = np.mean(central_crops, axis=0, dtype=np.float32)
        std_template = np.std(central_crops, axis=0, dtype=np.float32)
        return mean_template, std_template

    def compute_distance_stats(
        self,
        images: List[np.ndarray],
        mean_template: np.ndarray,
    ) -> Tuple[float, float, float]:
        mean_flat = mean_template.reshape(-1, mean_template.shape[-1])
        distances: List[float] = []

        for img in images:
            crop = self._extract_central_zone(img).astype(np.float32)
            diff = crop - mean_template
            distances.append(float(np.linalg.norm(diff.reshape(-1, diff.shape[-1]))))

        distances_arr = np.array(distances, dtype=np.float32)
        return (
            float(distances_arr.mean()),
            float(distances_arr.std(ddof=0)),
            float(distances_arr.max()),
        )

    # ------------------------------------------------------------------ #
    # Sauvegardes
    # ------------------------------------------------------------------ #

    def _save_numpy_artifact(self, symbol_dir: Path, filename: str, array: np.ndarray) -> str:
        file_path = symbol_dir / filename
        np.save(file_path, array)
        return str(file_path.relative_to(self.artifacts_dir))

    def _save_preview_png(self, symbol_dir: Path, mean_template: np.ndarray) -> str:
        preview = np.clip(mean_template, 0, 255).astype(np.uint8)
        img = Image.fromarray(preview, mode="RGB")
        file_path = symbol_dir / "preview.png"
        img.save(file_path)
        return str(file_path.relative_to(self.artifacts_dir))

    # ------------------------------------------------------------------ #
    # Pipeline principal
    # ------------------------------------------------------------------ #

    def generate_templates(self) -> Dict[str, TemplateStats]:
        dataset = self.load_symbol_dataset()
        manifest: Dict[str, TemplateStats] = {}

        for symbol_name, images in dataset.items():
            print(f"\n[PROCESS] {symbol_name} ({len(images)} images)")
            symbol_dir = self.artifacts_dir / symbol_name
            symbol_dir.mkdir(parents=True, exist_ok=True)

            mean_template, std_template = self.compute_symbol_template(images)
            mean_dist, std_dist, max_dist = self.compute_distance_stats(images, mean_template)

            # seuil = moyenne + 2 écarts-types (approx. 95%) limité par max
            suggested_threshold = float(min(mean_dist + 2 * std_dist, max_dist))

            mean_file = self._save_numpy_artifact(symbol_dir, "mean_template.npy", mean_template)
            std_file = self._save_numpy_artifact(symbol_dir, "std_template.npy", std_template)
            preview_file = self._save_preview_png(symbol_dir, mean_template)

            stats = TemplateStats(
                symbol=symbol_name,
                image_count=len(images),
                template_shape=mean_template.shape,
                margin=self.margin,
                mean_distance=round(mean_dist, 4),
                std_distance=round(std_dist, 4),
                max_distance=round(max_dist, 4),
                suggested_threshold=round(suggested_threshold, 4),
                mean_template_file=mean_file,
                std_template_file=std_file,
                preview_file=preview_file,
            )
            manifest[symbol_name] = stats

            print(
                "  ↪ seuil suggéré: "
                f"{stats.suggested_threshold:.2f} (μ={stats.mean_distance:.2f}, σ={stats.std_distance:.2f})"
            )

        self._write_manifest(manifest)
        return manifest

    def _write_manifest(self, manifest: Dict[str, TemplateStats]) -> None:
        manifest_path = self.artifacts_dir / "central_templates_manifest.json"

        payload = {
            "margin": self.margin,
            "templates": {name: asdict(stats) for name, stats in manifest.items()},
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] Manifest templates → {manifest_path}")


# ---------------------------------------------------------------------- #
# Script CLI
# ---------------------------------------------------------------------- #

def main() -> int:
    current_dir = Path(__file__).parent
    dataset_dir = current_dir / "data_set"
    artifacts_dir = current_dir / "template_artifact"

    print("=== Générateur d'agrégats Template Matching Central ===")
    print(f"Dataset     : {dataset_dir}")
    print(f"Artefacts   : {artifacts_dir}")

    aggregator = TemplateAggregator(
        dataset_dir=str(dataset_dir),
        artifacts_dir=str(artifacts_dir),
        margin=9,
    )

    manifest = aggregator.generate_templates()

    print("\n=== RÉSUMÉ ===")
    for name, stats in manifest.items():
        print(
            f"  {name:<16} → {stats.image_count:4d} img | "
            f"seuil suggéré {stats.suggested_threshold:.2f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())