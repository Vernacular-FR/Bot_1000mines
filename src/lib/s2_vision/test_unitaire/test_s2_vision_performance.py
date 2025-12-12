#!/usr/bin/env python3
"""Tests de performance/fiabilité pour le CenterTemplateMatcher sur un set de screenshots."""

from __future__ import annotations

import sys
import time
from pathlib import Path
import unittest

from PIL import Image

# S'assurer que src/ est dans le PYTHONPATH lorsque les tests sont lancés depuis tests/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_SIZE, CELL_BORDER  # noqa  # pylint: disable=wrong-import-position
from src.lib.s2_vision.api import (  # noqa  # pylint: disable=wrong-import-position
    VisionAPI,
    VisionControllerConfig,
)

SCREENSET_DIR = PROJECT_ROOT / "temp" / "set_screeshot"


class VisionPerformanceTest(unittest.TestCase):
    def test_center_template_matcher_accuracy_and_speed(self) -> None:
        images = sorted(SCREENSET_DIR.glob("*.png"))
        if not images:
            self.skipTest(f"Aucun screenshot trouvé dans {SCREENSET_DIR}")

        api = VisionAPI(
            VisionControllerConfig(
                overlay_output_dir=SCREENSET_DIR / "overlays",
            )
        )

        total_cells = 0
        unknown_cells = 0
        start = time.perf_counter()

        for image_path in images:
            image = Image.open(image_path).convert("RGB")
            stride_px = CELL_SIZE + CELL_BORDER
            cols = image.width // stride_px
            rows = image.height // stride_px
            results = api.analyze_screenshot(
                screenshot_path=image_path,
                grid_top_left=(0, 0),
                grid_size=(cols, rows),
                stride=stride_px,
                overlay=True,
            )
            total_cells += len(results)
            unknown_cells += sum(1 for res in results.values() if res.symbol == "unknown")

        duration = time.perf_counter() - start
        avg_time = duration / max(len(images), 1)
        unknown_ratio = unknown_cells / max(total_cells, 1)

        self.assertLess(
            avg_time,
            0.6,
            f"Temps moyen par screenshot trop élevé ({avg_time:.3f}s)",
        )
        self.assertLess(
            unknown_ratio,
            0.2,
            f"Trop de cellules non classées ({unknown_ratio:.2%})",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
