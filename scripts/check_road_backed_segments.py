#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(path: str, needles: list[str]) -> None:
    source = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{path} missing road-backed segment guard: {', '.join(missing)}")


def main() -> None:
    needles = [
        "ROAD_BACKED_SEGMENT_SQL",
        "parking_segments.id LIKE 'ct-osm-%'",
        "SEGMENT_HEATMAP_CACHE_VERSION",
        "road-backed-ct-osm-v1",
    ]
    require("services/zone-service/app/main.py", needles)
    require("services/prediction-service/app/main.py", needles)
    print("Road-backed segment checks OK")


if __name__ == "__main__":
    main()
