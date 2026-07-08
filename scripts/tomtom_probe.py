#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/ingestion-service"))

from app.tomtom import TomTomError, estimate_nearby  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe TomTom Traffic APIs without printing the API key.")
    parser.add_argument("--key-file", default="/Users/albertobocchieri/Desktop/tomtom_api_key.txt")
    parser.add_argument("--lat", type=float, default=37.5072)
    parser.add_argument("--lon", type=float, default=15.0832)
    parser.add_argument("--radius-m", type=int, default=900)
    args = parser.parse_args()

    api_key = os.getenv("TOMTOM_API_KEY") or Path(args.key_file).read_text(encoding="utf-8").strip()
    try:
        estimate = estimate_nearby(api_key, args.lat, args.lon, args.radius_m)
    except TomTomError as error:
        print(json.dumps({
            "ok": False,
            "status_code": error.status_code,
            "message": error.message,
        }, indent=2))
        return 2

    print(json.dumps({
        "ok": True,
        "traffic_pressure": estimate["traffic_pressure"],
        "event_pressure": estimate["event_pressure"],
        "current_speed": estimate["current_speed"],
        "free_flow_speed": estimate["free_flow_speed"],
        "confidence": estimate["confidence"],
        "flow_samples": estimate["flow_samples"],
        "incidents_count": estimate["incidents_count"],
        "incidents_sample": estimate["incidents_sample"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
