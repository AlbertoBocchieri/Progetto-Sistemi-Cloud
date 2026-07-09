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
    assert tomtom.budget_cap(2500, 0.05) == 125
    assert tomtom.cell_key(37.5070, 15.0830) == tomtom.cell_key(37.5072, 15.0832)

    assert tomtom.incident_pressure([]) == 0
    assert tomtom.incident_pressure([{"properties": {"iconCategory": "RoadClosed"}}]) == 1.0
    assert tomtom.incident_pressure([{"properties": {"iconCategory": "Jam", "delay": 450}}]) >= 0.7
    assert tomtom.incident_pressure([{"properties": {"iconCategory": "RoadWorks", "magnitudeOfDelay": 3}}]) >= 0.75

    bbox = tomtom.bbox_from_radius(37.5, 15.0, 500)
    values = [float(part) for part in bbox.split(",")]
    assert len(values) == 4
    assert values[0] < 15.0 < values[2]
    assert values[1] < 37.5 < values[3]
    assert tomtom.clean_parking_address("Via Test 1, 95131 Catania CT, Italia") == "Via Test 1"
    assert tomtom.clean_parking_address("Via Test 1, Catania") == "Via Test 1"

    pois = tomtom.parse_parking_pois(
        {
            "results": [
                {
                    "id": "garage-1",
                    "dist": 120.4,
                    "poi": {"name": "Garage Centro", "categorySet": [{"id": 7313}]},
                    "position": {"lat": 37.5, "lon": 15.08},
                    "address": {"freeformAddress": "Via Test 1, 95131 Catania CT, Italia"},
                    "dataSources": {"parkingAvailability": {"id": "not-used-in-payg"}},
                },
                {
                    "id": "open-1",
                    "poi": {"name": "Parcheggio scoperto", "categorySet": [{"id": 7369}]},
                    "position": {"lat": 37.51, "lon": 15.09},
                },
            ]
        }
    )
    assert pois[0]["parking_kind"] == "parking_garage"
    assert pois[0]["distance_m"] == 120.4
    assert pois[0]["address"] == "Via Test 1"
    assert pois[1]["parking_kind"] == "open_parking_area"

    print("TomTom checks OK")


if __name__ == "__main__":
    main()
