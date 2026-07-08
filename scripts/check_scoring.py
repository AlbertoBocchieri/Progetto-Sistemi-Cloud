#!/usr/bin/env python3
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORING = ROOT / "services/prediction-service/app/scoring.py"


def load_scoring():
    spec = importlib.util.spec_from_file_location("parcheggia_scoring", SCORING)
    if spec is None or spec.loader is None:
        raise AssertionError("Cannot load scoring module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    scoring = load_scoring()

    assert scoring.clamp01(-1) == 0
    assert scoring.clamp01(2) == 1
    assert scoring.clamp01("bad", 0.5) == 0.5

    expected_statuses = {
        0: "very_difficult",
        19: "very_difficult",
        20: "difficult",
        39: "difficult",
        40: "uncertain",
        59: "uncertain",
        60: "good",
        79: "good",
        80: "favorable",
        100: "favorable",
    }
    for percent, status in expected_statuses.items():
        assert scoring.status_from_percent(percent) == status

    assert scoring.report_adjustment(10, 0) == 15
    assert scoring.report_adjustment(0, 10) == -15
    assert scoring.report_adjustment(1, 1, 1, 1) == -4

    assert scoring.signal_delta({}) == 0
    assert scoring.signal_delta({"traffic_pressure": 1, "parking_lot_availability": 0, "event_pressure": 1}) == -35
    assert scoring.signal_delta({"traffic_pressure": 0, "parking_lot_availability": 1, "event_pressure": 0}) == 18

    print("Scoring checks OK")


if __name__ == "__main__":
    main()
