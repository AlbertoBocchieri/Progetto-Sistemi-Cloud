#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

import import_osm_segments


def main() -> None:
    fixture = {
        "elements": [
            {"type": "node", "id": 1, "lat": 37.5000, "lon": 15.0800},
            {"type": "node", "id": 2, "lat": 37.5020, "lon": 15.0800},
            {"type": "node", "id": 3, "lat": 37.5000, "lon": 15.0810},
            {"type": "node", "id": 4, "lat": 37.5005, "lon": 15.0810},
            {
                "type": "way",
                "id": 100,
                "nodes": [1, 2],
                "tags": {"highway": "residential", "name": "Via Test"},
            },
            {
                "type": "way",
                "id": 101,
                "nodes": [3, 4],
                "tags": {"highway": "service", "service": "driveway", "name": "Accesso privato"},
            },
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "overpass.json"
        path.write_text(json.dumps(fixture), encoding="utf-8")
        rows, road_node_rows, road_edge_rows = import_osm_segments.build_import(path, 120)
        sql = import_osm_segments.render_sql(rows, road_node_rows, road_edge_rows)

    assert rows, "expected generated rows"
    assert road_node_rows, "expected generated road nodes"
    assert road_edge_rows, "expected generated road edges"
    assert "ct-osm-via-test-100-" in sql
    assert "osm-road-100-" in sql
    assert "Accesso privato" not in sql
    assert "UPDATE parking_lots SET segment_id = NULL" in sql
    assert "UPDATE parking_lots AS lot" in sql
    assert "DELETE FROM parking_segments WHERE id LIKE 'ct-osm-%'" in sql
    assert "DELETE FROM road_edges WHERE id LIKE 'osm-road-%'" in sql
    print("OSM import checks OK")


if __name__ == "__main__":
    main()
