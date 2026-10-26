"""Unit tests for geometry, ROIs, camera health and traffic logic.

Run:  pytest tests   (from the edge_vision folder)
"""
import json
import os
import sys

import numpy as np
import pytest
from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from vision import geometry as g  # noqa: E402
from vision import health, logic, rois  # noqa: E402

PHASES = {"NS": ["N", "S"], "EW": ["E", "W"]}
WEIGHTS = {"car": 1.0, "tricycle": 0.5, "motorcycle": 0.25}
HCFG = {"occluded_brightness_max": 25, "occluded_blur_max": 15, "degraded_blur_min": 60,
        "degraded_conf_min": 0.30, "recover_seconds": 5}


# ---------------------------------------------------------------- geometry
SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_point_in_polygon():
    assert g.point_in_polygon((5, 5), SQUARE)
    assert not g.point_in_polygon((15, 5), SQUARE)


def test_stop_line_crossing_counts_forward_only():
    a, b = (0, 10), (10, 10)                 # horizontal stop line at y = 10
    queue_side = g.side((5, 5), a, b)        # queue is above the line
    assert g.crossed_stop_line((5, 8), (5, 12), a, b, queue_side)        # forward over the line
    assert not g.crossed_stop_line((5, 12), (5, 8), a, b, queue_side)    # reversing
    assert not g.crossed_stop_line((5, 6), (5, 8), a, b, queue_side)     # still waiting
    assert not g.crossed_stop_line((20, 8), (20, 12), a, b, queue_side)  # past the end of the line
    assert not g.crossed_stop_line(None, (5, 12), a, b, queue_side)      # new track


# ---------------------------------------------------------------- ROIs
def test_roiset_converts_and_crops():
    data = {"approaches": {
        n: {"queue": [[0.4, 0.1], [0.5, 0.1], [0.5, 0.4]], "stopline": [[0.4, 0.45], [0.5, 0.45]]}
        for n in rois.APPROACHES}}
    r = rois.RoiSet(data, 1000, 500, crop_margin=0.0)
    n = r.approaches["N"]
    assert n["queue"][0] == (400, 50)
    assert n["queue_side"] == g.side(g.polygon_centroid(n["queue"]), *n["stopline"])
    x1, y1, x2, y2 = r.crop
    assert 0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 500


# ---------------------------------------------------------------- health
def test_health_classify_frames():
    black = np.zeros((360, 640, 3), np.uint8)
    flat = np.full((360, 640, 3), 128, np.uint8)
    rng = np.random.default_rng(0)
    busy = rng.integers(0, 255, (360, 640, 3), dtype=np.uint8)
    assert health.classify(*health.frame_metrics(black), [], HCFG) == health.OCCLUDED
    assert health.classify(*health.frame_metrics(flat), [], HCFG) == health.OCCLUDED
    assert health.classify(*health.frame_metrics(busy), [], HCFG) == health.OK
    assert health.classify(*health.frame_metrics(busy), [0.1, 0.2], HCFG) == health.DEGRADED


def test_health_reports_bad_fast_and_recovers_slowly():
    m = health.HealthMonitor(HCFG)
    assert m.update(health.OCCLUDED, 0) == health.OCCLUDED      # immediately
    assert m.update(health.OK, 1) == health.OCCLUDED            # not yet
    assert m.update(health.OK, 4) == health.OCCLUDED
    assert m.update(health.OK, 6.1) == health.OK                # after 5 s of good frames
    assert m.update(health.DEGRADED, 7) == health.DEGRADED


# ---------------------------------------------------------------- logic
def test_pcu_and_density_schema():
    counts = {a: {"tricycle": 2, "motorcycle": 4, "car": 1} for a in "NESW"}
    d = logic.build_density("2026-10-25T00:00:00+00:00", 1, counts, WEIGHTS, PHASES)
    assert d["approaches"]["N"]["pcu"] == 3.0                    # 2*0.5 + 4*0.25 + 1*1.0
    assert d["phases"]["NS"] == 6.0
    schema = json.load(open(os.path.join(HERE, "..", "..", "docs", "mqtt-contract", "density.schema.json")))
    Draft202012Validator(schema).validate(d)


def test_empty_road_pcu_zero():
    assert logic.pcu_score({"tricycle": 0, "motorcycle": 0, "car": 0}, WEIGHTS) == 0


@pytest.mark.parametrize("state,approach,expected", [
    ({"phase": "NS", "mode": "L1"}, "N", False),        # N has green
    ({"phase": "NS", "mode": "L1"}, "E", True),         # E is red
    ({"phase": "NS", "mode": "L4"}, "E", None),         # flood: don't judge
    ({"phase": "NS", "mode": "L1", "fault": True}, "E", None),
    ({"phase": "NS", "mode": "L1", "amber": True}, "E", None),
    ({}, "E", None),                                    # no controller yet
])
def test_is_red(state, approach, expected):
    if state:
        state = dict(state, _rx=100)
    assert logic.is_red(approach, PHASES, state, now=101, stale_s=5) is expected


def test_is_red_stale_state_ignored():
    assert logic.is_red("E", PHASES, {"phase": "NS", "mode": "L1", "_rx": 100}, now=200, stale_s=5) is None
