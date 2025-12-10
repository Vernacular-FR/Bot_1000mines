import os
import tempfile

import numpy as np

from src.lib.s3_tensor.tensor_grid import TensorGrid
from src.lib.s3_tensor.hint_cache import HintCache
from src.lib.s3_tensor.trace_recorder import TraceRecorder


def test_tensor_grid_update_and_view():
    grid = TensorGrid(width=4, height=4)
    bounds = (0, 0, 1, 1)
    codes = np.array([[1, 2], [3, 4]], dtype=np.int8)
    confidences = np.array([[0.5, 0.6], [0.7, 0.8]], dtype=np.float32)
    frontier = np.array([[True, False], [False, True]])
    dirty = np.array([[True, True], [False, True]])

    grid.update_region(bounds, codes, confidences, frontier_mask=frontier, dirty_mask=dirty, tick_id=1)

    view = grid.get_solver_view(bounds)
    assert np.array_equal(view["values"], codes)
    assert np.array_equal(view["confidence"], confidences)
    assert np.array_equal(view["frontier_mask"], frontier)
    assert np.array_equal(view["dirty_mask"], dirty)

    stats = grid.stats()
    assert stats["known_ratio"] > 0
    dirty_sets = grid.publish_dirty_sets()
    assert len(dirty_sets) == 1
    assert dirty_sets[0].bounds == bounds
    assert dirty_sets[0].tick_id == 1


def test_hint_cache_publish_and_fetch():
    cache = HintCache()
    cache.publish_dirty_set(bounds=(0, 0, 1, 1), priority=5, tick_id=1)
    cache.publish_solver_request(component_id="zoneA", cells=[(1, 1)], priority=10)
    cache.publish_info("ok")

    events = cache.fetch()
    assert len(events) == 3
    assert events[0].kind == "solver_request"  # priorité la plus haute
    assert cache.stats()["pending_events"] == 0


def test_trace_recorder_capture(tmp_path=None):
    with tempfile.TemporaryDirectory() as tmp_dir:
        recorder = TraceRecorder(base_path=tmp_dir)
        tensor_snapshot = {
            "values": np.zeros((2, 2), dtype=np.int8),
            "confidence": np.zeros((2, 2), dtype=np.float32),
            "age": np.zeros((2, 2), dtype=np.uint32),
            "frontier_mask": np.zeros((2, 2), dtype=bool),
            "dirty_mask": np.zeros((2, 2), dtype=bool),
        }
        solver_state = {"actions": []}

        path = recorder.capture(tick_id=1, tensor_snapshot=tensor_snapshot, solver_state=solver_state)
        assert os.path.exists(path)
        event_path = recorder.mark_event(tick_id=1, message="test")
        assert os.path.exists(event_path)
        stats = recorder.stats()
        assert stats["snapshots_recorded"] == 1
