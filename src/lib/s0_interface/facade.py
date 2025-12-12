from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple, Protocol


@dataclass
class ViewportState:
    anchor_position: Tuple[float, float]
    viewport_bounds: Optional[Dict] = None


@dataclass
class CanvasDescriptor:
    id: str
    tile: Tuple[int, int]
    screen_left: float
    screen_top: float
    width: float
    height: float
    relative_left: float
    relative_top: float


@dataclass
class GameStatus:
    difficulty: Optional[str]
    high_score: Optional[int]
    current_score: Optional[int]
    lives: Optional[int]
    lives_display: Optional[str]
    bonus_counter: Optional[int]
    bonus_threshold: Optional[int]
    captured_at: datetime
    raw_snapshot: Dict[str, Optional[str]]


class InterfaceControllerApi(Protocol):
    def refresh_state(self) -> ViewportState: ...

    def ensure_visible(self, grid_bounds: Tuple[int, int, int, int]) -> None: ...

    def locate_canvas_for_point(self, canvas_x: float, canvas_y: float) -> Optional[CanvasDescriptor]: ...

    def get_capture_meta(self, canvas_x: float, canvas_y: float) -> Optional[Dict]: ...

    def scroll(self, dx: float, dy: float) -> None: ...

    def click_canvas_point(self, canvas_x: float, canvas_y: float) -> None: ...

    def click_grid_cell(self, grid_x: int, grid_y: int) -> None: ...
