#!/usr/bin/env python3
import argparse
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


MAX_SEGMENT_M = 120
CATANIA_BBOX = (15.02, 37.47, 15.16, 37.56)
DEFAULT_OSM_JSON = Path("data/osm/catania-overpass.json")
DEFAULT_SQL = Path("data/osm/catania_segments.sql")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DRIVABLE_HIGHWAYS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
    "living_street",
    "service",
    "road",
}
EXCLUDED_SERVICE = {"driveway", "parking_aisle", "drive-through", "emergency_access"}
EXCLUDED_ACCESS = {"private", "no"}


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


def overpass_query() -> str:
    highways = "|".join(sorted(DRIVABLE_HIGHWAYS))
    return f"""
[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="8"]["name"="Catania"]->.searchArea;
(
  way["highway"~"^({highways})$"]["name"](area.searchArea);
);
(._;>;);
out body;
"""


def fetch_overpass(output: Path, overpass_url: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    body = urllib.parse.urlencode({"data": overpass_query()}).encode("utf-8")
    request = urllib.request.Request(
        overpass_url,
        data=body,
        headers={"User-Agent": "ParcheggIA OSM segment importer"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        output.write_bytes(response.read())


def is_candidate_way(tags: dict[str, str]) -> bool:
    if not is_drivable_way(tags):
        return False
    return bool(tags.get("name"))


def is_drivable_way(tags: dict[str, str]) -> bool:
    highway = tags.get("highway")
    if highway not in DRIVABLE_HIGHWAYS:
        return False
    if tags.get("access") in EXCLUDED_ACCESS or tags.get("motor_vehicle") in EXCLUDED_ACCESS:
        return False
    if highway == "service" and tags.get("service") in EXCLUDED_SERVICE:
        return False
    return tags.get("area") != "yes"


def is_one_way(tags: dict[str, str]) -> bool:
    return tags.get("oneway") in {"yes", "1", "true"}


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


def road_node_id(osm_node_id: int) -> str:
    return f"osm-node-{osm_node_id}"


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
    return build_import(path, max_len_m)[0]


def build_import(path: Path, max_len_m: int) -> tuple[list[str], list[str], list[str]]:
    nodes, ways = load_overpass(path)
    parking_rows: list[str] = []
    road_node_ids: set[int] = set()
    road_edge_rows: list[str] = []
    for way in sorted(ways, key=lambda item: int(item["id"])):
        tags = {str(key): str(value) for key, value in way.get("tags", {}).items()}
        points = [nodes[node_id] for node_id in way.get("nodes", []) if node_id in nodes]
        if len(points) < 2:
            continue
        if is_drivable_way(tags):
            way_nodes = [int(node_id) for node_id in way.get("nodes", []) if int(node_id) in nodes]
            one_way = is_one_way(tags)
            for index, (from_node, to_node) in enumerate(zip(way_nodes, way_nodes[1:]), start=1):
                start = nodes[from_node]
                end = nodes[to_node]
                length = distance_m(start, end)
                if length < 3:
                    continue
                if tags.get("oneway") == "-1":
                    from_node, to_node = to_node, from_node
                    start, end = end, start
                    one_way = True
                road_node_ids.add(from_node)
                road_node_ids.add(to_node)
                road_edge_rows.append(
                    "("
                    f"{sql_quote(f'osm-road-{int(way['id'])}-{index:04d}')}, "
                    f"{int(way['id'])}, "
                    f"{sql_quote(road_node_id(from_node))}, "
                    f"{sql_quote(road_node_id(to_node))}, "
                    f"{sql_quote(tags.get('name'))}, "
                    f"{sql_quote(tags.get('highway'))}, "
                    f"{'true' if one_way else 'false'}, "
                    f"ST_GeomFromText({sql_quote(wkt_line([start, end]))}, 4326), "
                    f"{length:.2f}"
                    ")"
                )

        if not is_candidate_way(tags):
            continue
        street_name = tags["name"]
        parking_type, tariff_zone, price_label, time_rules, source, confidence = infer_parking(tags)
        for index, segment in enumerate(split_line(points, max_len_m), start=1):
            segment_id = f"ct-osm-{slug(street_name)}-{int(way['id'])}-{index:03d}"
            parking_rows.append(
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
    road_node_rows = [
        "("
        f"{sql_quote(road_node_id(node_id))}, "
        f"{node_id}, "
        f"ST_SetSRID(ST_MakePoint({nodes[node_id][0]:.8f}, {nodes[node_id][1]:.8f}), 4326)"
        ")"
        for node_id in sorted(road_node_ids)
    ]
    return parking_rows, road_node_rows, road_edge_rows


def render_sql(rows: list[str], road_node_rows: list[str] | None = None, road_edge_rows: list[str] | None = None) -> str:
    road_node_rows = road_node_rows or []
    road_edge_rows = road_edge_rows or []
    lines = [
        "-- Example Overpass bbox: " + ",".join(str(value) for value in CATANIA_BBOX),
        "BEGIN;",
        "DELETE FROM road_edges WHERE id LIKE 'osm-road-%';",
        "DELETE FROM road_nodes WHERE id LIKE 'osm-node-%';",
        "DELETE FROM segment_reports WHERE segment_id LIKE 'ct-osm-%';",
        "UPDATE parking_lots SET segment_id = NULL WHERE segment_id LIKE 'ct-osm-%';",
        "DELETE FROM parking_segments WHERE id LIKE 'ct-osm-%';",
    ]
    if road_node_rows:
        lines.append(
            """
INSERT INTO road_nodes (
    id,
    osm_node_id,
    location
)
VALUES
""".strip()
        )
        lines.append(",\n".join(road_node_rows))
        lines.append(
            """
ON CONFLICT (id) DO UPDATE SET
    osm_node_id = EXCLUDED.osm_node_id,
    location = EXCLUDED.location;
""".strip()
        )
    if road_edge_rows:
        lines.append(
            """
INSERT INTO road_edges (
    id,
    osm_way_id,
    from_node_id,
    to_node_id,
    street_name,
    highway,
    one_way,
    geometry,
    length_m
)
VALUES
""".strip()
        )
        lines.append(",\n".join(road_edge_rows))
        lines.append(
            """
ON CONFLICT (id) DO UPDATE SET
    osm_way_id = EXCLUDED.osm_way_id,
    from_node_id = EXCLUDED.from_node_id,
    to_node_id = EXCLUDED.to_node_id,
    street_name = EXCLUDED.street_name,
    highway = EXCLUDED.highway,
    one_way = EXCLUDED.one_way,
    geometry = EXCLUDED.geometry,
    length_m = EXCLUDED.length_m;
""".strip()
        )
    if rows:
        lines.append(
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
""".strip()
        )
        lines.append(",\n".join(rows))
        lines.append(
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
""".strip()
        )
    lines.append(
        """
UPDATE parking_lots AS lot
SET segment_id = (
    SELECT segment.id
    FROM parking_segments AS segment
    ORDER BY segment.geometry::geography <-> lot.location::geography
    LIMIT 1
)
WHERE EXISTS (SELECT 1 FROM parking_segments);
""".strip()
    )
    lines.append("COMMIT;")
    lines.append(f"-- generated_segments={len(rows)}")
    lines.append(f"-- generated_road_nodes={len(road_node_rows)}")
    lines.append(f"-- generated_road_edges={len(road_edge_rows)}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download or convert Overpass JSON to parking_segments SQL."
    )
    parser.add_argument("osm_json", type=Path, nargs="?")
    parser.add_argument("--fetch", action="store_true", help="Download Catania roads from Overpass before generating SQL.")
    parser.add_argument("--max-segment-m", type=int, default=MAX_SEGMENT_M)
    parser.add_argument("--overpass-url", default=OVERPASS_URL)
    parser.add_argument("--output", type=Path, help="Write SQL to this file instead of stdout.")
    args = parser.parse_args()

    osm_json = args.osm_json or DEFAULT_OSM_JSON
    if args.fetch:
        fetch_overpass(osm_json, args.overpass_url)
    if not osm_json.exists():
        parser.error(f"{osm_json} does not exist; pass --fetch or provide an Overpass JSON export")

    rows, road_node_rows, road_edge_rows = build_import(osm_json, args.max_segment_m)
    sql = render_sql(rows, road_node_rows, road_edge_rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(sql, encoding="utf-8")
    else:
        print(sql, end="")


if __name__ == "__main__":
    main()
