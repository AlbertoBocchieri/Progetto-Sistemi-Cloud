#!/usr/bin/env python3
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOMTOM = ROOT / "services/ingestion-service/app/tomtom.py"


def load_tomtom():
    spec = importlib.util.spec_from_file_location("parcheggia_tomtom", TOMTOM)
    if spec is None or spec.loader is None:
        raise AssertionError("Cannot load tomtom module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    tomtom = load_tomtom()

    assert tomtom.traffic_pressure_from_flow({"currentSpeed": 20, "freeFlowSpeed": 40}) == 0.5
    assert tomtom.traffic_pressure_from_flow({"currentSpeed": 50, "freeFlowSpeed": 40}) == 0
    assert tomtom.traffic_pressure_from_flow({"roadClosure": True}) == 1.0

    assert tomtom.incident_pressure([]) == 0
    assert tomtom.incident_pressure([{"properties": {"iconCategory": "RoadClosed"}}]) == 1.0
    assert tomtom.incident_pressure([{"properties": {"iconCategory": "Jam", "delay": 450}}]) >= 0.7

    bbox = tomtom.bbox_from_radius(37.5, 15.0, 900)
    values = [float(part) for part in bbox.split(",")]
    assert len(values) == 4
    assert values[0] < 15.0 < values[2]
    assert values[1] < 37.5 < values[3]

    print("TomTom checks OK")


if __name__ == "__main__":
    main()
