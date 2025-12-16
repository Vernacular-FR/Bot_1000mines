#!/usr/bin/env python3
"""Compare les performances pipelines Propagator vs CSP et génère un rapport."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CELL_BORDER, CELL_SIZE  # noqa: E402
from src.lib.s2_vision.facade import VisionAPI, VisionControllerConfig  # noqa: E402
from src.lib.s2_vision.s21_template_matcher import MatchResult  # noqa: E402
from src.lib.s2_vision.s23_vision_to_storage import matches_to_upsert  # noqa: E402
from src.lib.s3_storage.facade import GridCell  # noqa: E402
from src.lib.s4_solver.s40_states_analyzer.grid_classifier import FrontierClassifier  # noqa: E402
from src.lib.s4_solver.s40_states_analyzer.grid_extractor import SolverFrontierView  # noqa: E402
from src.lib.s4_solver.s41_propagator_solver.s410_propagator_pipeline import (  # noqa: E402
    PropagatorPipeline,
    PropagatorPipelineResult,
)
from src.lib.s4_solver.s42_csp_solver.s420_csp_manager import CspManager  # noqa: E402


Coord = Tuple[int, int]
Bounds = Tuple[int, int, int, int]

STRIDE = CELL_SIZE + CELL_BORDER
RAW_GRIDS_DIR = Path(__file__).parent / "00_raw_grids"
OUTPUT_DIR = Path(__file__).parent / "03_solver_comparison"
BOUNDS_PATTERN = re.compile(r"zone_(?P<sx>-?\d+)_(?P<sy>-?\d+)_(?P<ex>-?\d+)_(?P<ey>-?\d+)")


def parse_bounds(path: Path) -> Optional[Bounds]:
    match = BOUNDS_PATTERN.search(path.stem)
    if not match:
        return None
    return (
        int(match.group("sx")),
        int(match.group("sy")),
        int(match.group("ex")),
        int(match.group("ey")),
    )


def analyze_screenshot(screenshot: Path) -> Tuple[Bounds, Dict[Tuple[int, int], MatchResult]]:
    bounds = parse_bounds(screenshot)
    if not bounds:
        raise ValueError(f"Impossible de parser les bornes pour {screenshot.name}")

    start_x, start_y, end_x, end_y = bounds
    grid_width = end_x - start_x + 1
    grid_height = end_y - start_y + 1

    vision = VisionAPI(VisionControllerConfig(overlay_output_dir=None))
    matches = vision.analyze_screenshot(
        screenshot_path=str(screenshot),
        grid_top_left=(0, 0),
        grid_size=(grid_width, grid_height),
        stride=STRIDE,
        overlay=False,
    )
    return bounds, matches


def clone_cells(cells: Dict[Coord, GridCell]) -> Dict[Coord, GridCell]:
    return dict(cells)


def run_propagator_pipeline(cells: Dict[Coord, GridCell]) -> Tuple[PropagatorPipelineResult, float]:
    pipeline = PropagatorPipeline(cells)
    start = time.perf_counter()
    result = pipeline.run()
    duration = time.perf_counter() - start
    return result, duration


def run_csp_pipeline(cells: Dict[Coord, GridCell]) -> Tuple[CspManager, float]:
    classifier = FrontierClassifier(cells)
    zones = classifier.classify()
    view = SolverFrontierView(cells, set(zones.frontier))
    manager = CspManager(view, cells)
    start = time.perf_counter()
    manager.run_with_frontier_reducer()
    duration = time.perf_counter() - start
    return manager, duration


def summarize_propagator(result: PropagatorPipelineResult, duration: float) -> Dict[str, object]:
    return {
        "duration_sec": duration,
        "safe_total": len(result.safe_cells),
        "flag_total": len(result.flag_cells),
        "phase1": {
            "safe": len(result.iterative.safe_cells),
            "flags": len(result.iterative.flag_cells),
            "iterations": result.iterative.iterations,
        },
        "subset": {
            "safe": len(result.subset.safe_cells),
            "flags": len(result.subset.flag_cells),
            "iterations": result.subset.iterations,
        },
        "advanced": {
            "safe": len(result.advanced.safe_cells),
            "flags": len(result.advanced.flag_cells),
            "iterations": result.advanced.iterations,
        },
        "iterative_refresh": {
            "safe": len(result.iterative_refresh.safe_cells),
            "flags": len(result.iterative_refresh.flag_cells),
            "iterations": result.iterative_refresh.iterations,
        },
    }


def summarize_csp(manager: CspManager, duration: float) -> Dict[str, object]:
    reducer_safe_set = manager.reducer_result.safe_cells if manager.reducer_result else set()
    reducer_flag_set = manager.reducer_result.flag_cells if manager.reducer_result else set()
    reducer_safe = len(reducer_safe_set)
    reducer_flags = len(reducer_flag_set)
    csp_safe_set = set(manager.safe_cells)
    csp_flag_set = set(manager.flag_cells)
    total_safe = reducer_safe + len(csp_safe_set)
    total_flags = reducer_flags + len(csp_flag_set)
    segmentation_count = len(manager.segmentation.zones) if manager.segmentation else 0
    eligible_components = len(manager.solutions_by_component)
    return {
        "duration_sec": duration,
        "total_safe": total_safe,
        "total_flags": total_flags,
        "reducer_safe": reducer_safe,
        "reducer_flags": reducer_flags,
        "csp_safe_only": len(csp_safe_set),
        "csp_flags_only": len(csp_flag_set),
        "zones": segmentation_count,
        "eligible_components": eligible_components,
    }


def compare_results(
    propagator: PropagatorPipelineResult,
    csp_manager: CspManager,
) -> Dict[str, object]:
    reducer_safe = csp_manager.reducer_result.safe_cells if csp_manager.reducer_result else set()
    reducer_flags = csp_manager.reducer_result.flag_cells if csp_manager.reducer_result else set()
    propagator_safe = propagator.safe_cells
    propagator_flags = propagator.flag_cells
    csp_only_safe = set(csp_manager.safe_cells)
    csp_only_flags = set(csp_manager.flag_cells)
    csp_total_safe = reducer_safe | csp_only_safe
    csp_total_flags = reducer_flags | csp_only_flags

    return {
        "safe_only_propagator": sorted(propagator_safe - csp_total_safe),
        "safe_only_csp": sorted(csp_total_safe - propagator_safe),
        "flags_only_propagator": sorted(propagator_flags - csp_total_flags),
        "flags_only_csp": sorted(csp_total_flags - propagator_flags),
        "reducer_vs_propagator_safe_diff": sorted(propagator_safe - reducer_safe),
        "reducer_vs_propagator_flag_diff": sorted(propagator_flags - reducer_flags),
    }


def process_screenshot(screenshot: Path) -> Dict[str, object]:
    bounds, matches = analyze_screenshot(screenshot)
    upsert = matches_to_upsert(bounds, matches)

    propagator_cells = clone_cells(upsert.cells)
    csp_cells = clone_cells(upsert.cells)

    propagator_result, propagator_time = run_propagator_pipeline(propagator_cells)
    csp_manager, csp_time = run_csp_pipeline(csp_cells)

    report_entry = {
        "screenshot": screenshot.name,
        "bounds": bounds,
        "propagator": summarize_propagator(propagator_result, propagator_time),
        "csp": summarize_csp(csp_manager, csp_time),
    }
    report_entry["comparison"] = compare_results(propagator_result, csp_manager)
    return report_entry


def main() -> None:
    screenshots: List[Path] = sorted(RAW_GRIDS_DIR.glob("*.png"))
    if not screenshots:
        print(f"[ERROR] Aucun screenshot trouvé dans {RAW_GRIDS_DIR}")
        return

    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    generation_dt = datetime.now()
    timestamp = generation_dt.strftime("%Y%m%d_%H%M%S")
    report_path = OUTPUT_DIR / f"solver_comparison_{timestamp}.json"
    markdown_path = OUTPUT_DIR / f"solver_comparison_{timestamp}.md"

    report: List[Dict[str, object]] = []
    for screenshot in screenshots:
        try:
            entry = process_screenshot(screenshot)
            report.append(entry)
            print(
                f"[COMPARE] {screenshot.name}: "
                f"prop_safe={entry['propagator']['safe_total']} "
                f"csp_safe={entry['csp']['total_safe']} "
                f"prop_time={entry['propagator']['duration_sec']:.3f}s "
                f"csp_time={entry['csp']['duration_sec']:.3f}s"
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[ERROR] {screenshot.name}: {exc}")

    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    md_lines = [
        "# Comparaison Propagator vs CSP",
        "",
        f"- Généré le {generation_dt.isoformat()}",
        f"- Rapport JSON : `{report_path.name}`",
        "",
        "| Screenshot | Prop safe/flags | Prop temps (s) | CSP safe/flags | CSP temps (s) | Diff safe (Prop-CSP) | Diff flags (Prop-CSP) | Δ temps (s) | Ratio temps (Prop/CSP) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    avg_prop_safe = avg_prop_flags = avg_prop_time = 0.0
    avg_csp_safe = avg_csp_flags = avg_csp_time = 0.0
    avg_delta_time = avg_ratio = 0.0

    for entry in report:
        screenshot = entry["screenshot"]
        prop = entry["propagator"]
        csp = entry["csp"]
        comparison = entry["comparison"]
        safe_diff = len(comparison["safe_only_propagator"]) - len(comparison["safe_only_csp"])
        flag_diff = len(comparison["flags_only_propagator"]) - len(comparison["flags_only_csp"])
        delta_time = prop["duration_sec"] - csp["duration_sec"]
        ratio_time = prop["duration_sec"] / csp["duration_sec"]
        md_lines.append(
            f"| {screenshot} "
            f"| {prop['safe_total']} / {prop['flag_total']} "
            f"| {prop['duration_sec']:.3f} "
            f"| {csp['total_safe']} / {csp['total_flags']} "
            f"| {csp['duration_sec']:.3f} "
            f"| {safe_diff:+d} "
            f"| {flag_diff:+d} "
            f"| {delta_time:+.3f} "
            f"| {ratio_time:.2f} |"
        )
        avg_prop_safe += prop["safe_total"]
        avg_prop_flags += prop["flag_total"]
        avg_prop_time += prop["duration_sec"]
        avg_csp_safe += csp["total_safe"]
        avg_csp_flags += csp["total_flags"]
        avg_csp_time += csp["duration_sec"]
        avg_delta_time += delta_time
        avg_ratio += ratio_time

    if report:
        count = len(report)
        md_lines.append(
            f"| **Moyenne** "
            f"| **{avg_prop_safe / count:.1f} / {avg_prop_flags / count:.1f}** "
            f"| **{avg_prop_time / count:.3f}** "
            f"| **{avg_csp_safe / count:.1f} / {avg_csp_flags / count:.1f}** "
            f"| **{avg_csp_time / count:.3f}** "
            f"| **—** "
            f"| **—** "
            f"| **{avg_delta_time / count:+.3f}** "
            f"| **{avg_ratio / count:.2f}** |"
        )

    md_lines.append("")
    md_lines.append("## Détails supplémentaires")
    for entry in report:
        screenshot = entry["screenshot"]
        comparison = entry["comparison"]
        md_lines.append(f"### {screenshot}")
        md_lines.append(f"- Safe uniquement Propagator ({len(comparison['safe_only_propagator'])}): {comparison['safe_only_propagator']}")
        md_lines.append(f"- Safe uniquement CSP ({len(comparison['safe_only_csp'])}): {comparison['safe_only_csp']}")
        md_lines.append(f"- Flags uniquement Propagator ({len(comparison['flags_only_propagator'])}): {comparison['flags_only_propagator']}")
        md_lines.append(f"- Flags uniquement CSP ({len(comparison['flags_only_csp'])}): {comparison['flags_only_csp']}")
        md_lines.append("")

    with markdown_path.open("w", encoding="utf-8") as fh_md:
        fh_md.write("\n".join(md_lines))

    print(f"[REPORT] Résultats enregistrés dans {report_path}")
    print(f"[REPORT] Résumé Markdown : {markdown_path}")


if __name__ == "__main__":
    main()
