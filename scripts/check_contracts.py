#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as file:
        return json.load(file)


def require_keys(document: dict, keys: list[str], label: str) -> None:
    missing = [key for key in keys if key not in document]
    if missing:
        raise AssertionError(f"{label} missing keys: {', '.join(missing)}")


def main() -> None:
    openapi = load_json("shared/openapi/parcheggia-api.yaml")
    require_keys(openapi, ["openapi", "info", "paths"], "OpenAPI")
    if not str(openapi["openapi"]).startswith("3."):
        raise AssertionError("OpenAPI version must be 3.x")

    required_paths = [
        "/segments",
        "/segments/current",
        "/segments/nearby",
        "/road-network",
        "/segments/{segment_id}/prediction",
        "/predictions",
        "/segment-heatmap",
        "/tomtom/parking-pois",
        "/live-sessions/start",
        "/live-sessions/{session_id}/location",
        "/segment-reports",
        "/admin/events",
    ]
    missing_paths = [path for path in required_paths if path not in openapi["paths"]]
    if missing_paths:
        raise AssertionError(f"OpenAPI missing paths: {', '.join(missing_paths)}")

    event_schema = load_json("shared/schemas/events/parcheggia-event.schema.json")
    required_event_fields = ["event_id", "event_type", "source", "timestamp", "payload"]
    if event_schema.get("required") != required_event_fields:
        raise AssertionError("Event schema required fields changed unexpectedly")

    event_types = set(event_schema["properties"]["event_type"]["enum"])
    for event_type in ["user.location.updated", "user.report.created", "traffic.snapshot.received"]:
        if event_type not in event_types:
            raise AssertionError(f"Event schema missing {event_type}")

    prediction_schema = load_json("shared/schemas/api/prediction.schema.json")
    for field in ["parkability_percent", "status", "trend", "confidence"]:
        if field not in prediction_schema["properties"]:
            raise AssertionError(f"Prediction schema missing {field}")

    print("Contract checks OK")


if __name__ == "__main__":
    main()
