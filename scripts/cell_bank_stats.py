"""
Analyse rapide du cell_bank pour mesurer l'avancement de la labellisation Phase B.

Usage:
    python scripts/cell_bank_stats.py \
        --root src/lib/s2_recognition/Neural_engine/cell_bank \
        [--output stats.json]
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image

VALID_EXT = {".png", ".jpg", ".jpeg"}


def analyze_label_dir(label_dir: Path) -> Tuple[int, int]:
    """Retourne (valid_count, invalid_count) pour un dossier de label."""
    valid = 0
    invalid = 0
    for image_path in label_dir.iterdir():
        if not image_path.is_file() or image_path.suffix.lower() not in VALID_EXT:
            continue
        try:
            with Image.open(image_path) as img:
                if img.size == (24, 24):
                    valid += 1
                else:
                    invalid += 1
        except Exception:
            invalid += 1
    return valid, invalid


def build_stats(root: Path) -> Dict[str, Dict[str, int]]:
    stats: Dict[str, Dict[str, int]] = {}
    total_valid = 0
    total_invalid = 0
    for label_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        valid, invalid = analyze_label_dir(label_dir)
        stats[label_dir.name] = {"valid": valid, "invalid": invalid}
        total_valid += valid
        total_invalid += invalid
    stats["_summary"] = {
        "total_valid": total_valid,
        "total_invalid": total_invalid,
        "label_count": len(stats),
    }
    return stats


def format_table(stats: Dict[str, Dict[str, int]]) -> str:
    lines = ["Label | Valid | Invalid", "--- | ---: | ---:"]
    for label, data in sorted(stats.items()):
        if label.startswith("_"):
            continue
        lines.append(f"{label} | {data['valid']} | {data['invalid']}")
    summary = stats["_summary"]
    lines.append(
        f"**TOTAL** | **{summary['total_valid']}** | **{summary['total_invalid']}**"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Produit des statistiques sur le cell_bank (Phase B)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("src/lib/s2_recognition/Neural_engine/cell_bank"),
        help="Dossier racine contenant les sous-dossiers par label.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Chemin facultatif pour écrire les stats en JSON.",
    )
    args = parser.parse_args()

    if not args.root.exists():
        raise SystemExit(f"Racine cell_bank introuvable: {args.root}")

    stats = build_stats(args.root)
    print("[CELL_BANK] Statistiques par label\n")
    print(format_table(stats))
    print()
    summary = stats["_summary"]
    print(
        f"[SUMMARY] labels={summary['label_count']} | "
        f"valid={summary['total_valid']} | invalid={summary['total_invalid']}"
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"[OUTPUT] Stats sauvegardées dans {args.output}")


if __name__ == "__main__":
    main()
