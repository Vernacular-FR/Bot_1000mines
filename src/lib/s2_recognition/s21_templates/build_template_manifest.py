#!/usr/bin/env python3
"""
Génère un manifeste JSON pour les templates de s21_templates/symbols.
Le manifeste contient des statistiques utiles (moyenne, écart-type),
une empreinte rapide et les dimensions pour chaque symbole.
"""

import json
from pathlib import Path
from typing import Dict, Any

import numpy as np
from PIL import Image

# Garder le même mapping que template_matching_fixed pour synchroniser les noms
TEMPLATE_MAPPING = {
    "1.png": "number_1",
    "2.png": "number_2",
    "3.png": "number_3",
    "4.png": "number_4",
    "5.png": "number_5",
    "6.png": "number_6",
    "7.png": "number_7",
    "Flag.png": "flag",
    "inactive.png": "unrevealed",
    "vide.png": "empty",
}

SYMBOLS_DIR = Path(__file__).parent / "symbols"
OUTPUT_PATH = Path(__file__).parent / "template_manifest.json"


def compute_template_stats(image_path: Path) -> Dict[str, Any]:
    image = Image.open(image_path).convert("L")
    arr = np.array(image, dtype=np.float32)
    mean_value = float(arr.mean())
    std_value = float(arr.std())
    min_value = float(arr.min())
    max_value = float(arr.max())
    # Empreinte simple: moyenne par bloc 4x4
    block_size = 4
    resized = image.resize((block_size, block_size), Image.BICUBIC)
    fingerprint = np.array(resized, dtype=np.float32)
    fingerprint = fingerprint / 255.0
    fingerprint = fingerprint.round(3).tolist()
    return {
        "mean": mean_value,
        "std": std_value,
        "min": min_value,
        "max": max_value,
        "width": image.width,
        "height": image.height,
        "fingerprint_4x4": fingerprint,
    }


def build_manifest() -> Dict[str, Any]:
    manifest = {
        "templates_dir": str(SYMBOLS_DIR),
        "generated_at": None,
        "templates": {},
    }
    for file in sorted(SYMBOLS_DIR.glob("*.png")):
        symbol_name = TEMPLATE_MAPPING.get(file.name, file.stem.lower())
        stats = compute_template_stats(file)
        manifest["templates"][symbol_name] = stats
    return manifest


def main():
    from datetime import datetime, timezone

    manifest = build_manifest()
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[OK] Manifeste généré: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
