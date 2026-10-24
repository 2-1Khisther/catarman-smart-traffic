"""Step 4 - Contract tests: the mock payloads must pass the committed JSON Schemas.

Run:  pytest tests   (from the edge_vision folder)
"""
import json
import os
import sys

import pytest
from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
SCHEMAS = os.path.join(HERE, "..", "..", "docs", "mqtt-contract")

import mock_publisher as mp  # noqa: E402


def load(name):
    with open(os.path.join(SCHEMAS, f"{name}.schema.json"), encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


def test_density_valid():
    load("density").validate(mp.density(1))


def test_density_phase_sums_match_approaches():
    d = mp.density(1)
    for phase, members in mp.CFG["phases"].items():
        assert d["phases"][phase] == pytest.approx(sum(d["approaches"][a]["pcu"] for a in members))


def test_pcu_empty_approach_is_zero():
    counts = {"tricycle": 0, "motorcycle": 0, "car": 0}
    assert sum(mp.PCU[c] * n for c, n in counts.items()) == 0


def test_pcu_one_car_equals_two_tricycles():
    assert mp.PCU["car"] == pytest.approx(2 * mp.PCU["tricycle"])


def test_heartbeat_valid_and_rejects_bad_status():
    v = load("heartbeat")
    good = {"ts": mp.now(), "seq": 1, "fps": 17.2, "conf_avg": 0.8, "status": "OK"}
    v.validate(good)
    assert not v.is_valid(dict(good, status="BROKEN"))


def test_violation_rejects_unknown_class():
    v = load("violation")
    good = {"event_id": "abcd1234", "ts": mp.now(), "approach": "N", "cls": "car",
            "centroid": [10, 20], "bbox": [1, 2, 3, 4], "crop_file": "crops/x.jpg"}
    v.validate(good)
    assert not v.is_valid(dict(good, cls="van"))
