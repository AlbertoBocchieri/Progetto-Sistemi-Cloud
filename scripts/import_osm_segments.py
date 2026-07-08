#!/usr/bin/env python3
import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


MAX_SEGMENT_M = 120
CATANIA_BBOX = (15.02, 37.47, 15.16, 37.56)


def slug(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "strada"


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def interpolate(a: tuple[float, float], b: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)


def split_line(points: list[tuple[float, float]], max_len_m: int) -> list[list[tuple[float, float]]]:
    segments: list[list[tuple[float, float]]] = []
    for start, end in zip(points, points[1:]):
        length = distance_m(start, end)
        pieces = max(1, math.ceil(length / max_len_m))
        cursor = start
        for index in range(1, pieces + 1):
            point = interpolate(start, end, index / pieces)
            if distance_m(cursor, point) >= 15:
                segments.append([cursor, point])
            cursor = point
    return segments


def infer_parking(tags: dict[str, str]) -> tuple[str, str | None, str | None, str | None, str, float]:
    values = " ".join(str(value).lower() for value in tags.values())
    if any(token in values for token in ["ticket", "fee", "paid", "disc"]):
        return ("blue", None, None, None, "osm_street_parking", 0.58)
    if any(token in values for token in ["no_parking", "no_stopping", "private", "customers", "disabled"]):
        return ("restricted", None, None, "Verifica segnaletica locale", "osm_street_parking", 0.55)
    return ("probable_free", None, None, "Verifica segnaletica locale", "aggressive_inference", 0.42)


def sql_quote(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def wkt_line(points: list[tuple[float, float]]) -> str:
    coords = ",".join(f"{lon:.8f} {lat:.8f}" for lon, lat in points)
    return f"LINESTRING({coords})"


def load_overpass(path: Path) -> tuple[dict[int, tuple[float, float]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    for element in data.get("elements", []):
        if element.get("type") == "node":
            nodes[int(element["id"])] = (float(element["lon"]), float(element["lat"]))
        elif element.get("type") == "way":
            ways.append(element)
    return nodes, ways


def build_rows(path: Path, max_len_m: int) -> list[str]:
    nodes, ways = load_overpass(path)
    rows: list[str] = []
    seen: dict[str, int] = {}
    for way in ways:
        tags = {str(key): str(value) for key, value in way.get("tags", {}).items()}
        if "highway" not in tags or "name" not in tags:
            continue
        points = [nodes[node_id] for node_id in way.get("nodes", []) if node_id in nodes]
        if len(points) < 2:
            continue
        street_name = tags["name"]
        parking_type, tariff_zone, price_label, time_rules, source, confidence = infer_parking(tags)
        for segment in split_line(points, max_len_m):
            base = f"ct-osm-{slug(street_name)}"
            seen[base] = seen.get(base, 0) + 1
            segment_id = f"{base}-{seen[base]:03d}"
            rows.append(
                "("
                f"{sql_quote(segment_id)}, "
                f"{sql_quote(street_name)}, "
                "'Catania', "
                f"{sql_quote(parking_type)}, "
                f"{sql_quote(tariff_zone)}, "
                f"{sql_quote(price_label)}, "
                f"{sql_quote(time_rules)}, "
                f"{sql_quote(source)}, "
                f"{confidence:.2f}, "
                f"ST_GeomFromText({sql_quote(wkt_line(segment))}, 4326), "
                f"{distance_m(segment[0], segment[1]):.2f}"
                ")"
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an offline Overpass JSON export to parking_segments SQL."
    )
    parser.add_argument("osm_json", type=Path)
    parser.add_argument("--max-segment-m", type=int, default=MAX_SEGMENT_M)
    args = parser.parse_args()

    rows = build_rows(args.osm_json, args.max_segment_m)
    print("-- Example Overpass bbox:", ",".join(str(value) for value in CATANIA_BBOX))
    print("BEGIN;")
    if rows:
        print(
            """
INSERT INTO parking_segments (
    id,
    street_name,
    city,
    parking_type,
    tariff_zone,
    price_label,
    time_rules,
    source,
    source_confidence,
    geometry,
    length_m
)
VALUES
"""
        )
        print(",\n".join(rows))
        print(
            """
ON CONFLICT (id) DO UPDATE SET
    street_name = EXCLUDED.street_name,
    parking_type = EXCLUDED.parking_type,
    tariff_zone = EXCLUDED.tariff_zone,
    price_label = EXCLUDED.price_label,
    time_rules = EXCLUDED.time_rules,
    source = EXCLUDED.source,
    source_confidence = EXCLUDED.source_confidence,
    geometry = EXCLUDED.geometry,
    length_m = EXCLUDED.length_m;
"""
        )
    print("COMMIT;")
    print(f"-- generated_segments={len(rows)}")


if __name__ == "__main__":
    main()
