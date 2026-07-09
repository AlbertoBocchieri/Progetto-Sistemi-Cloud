#!/usr/bin/env python3
import apply_parking_overrides


def main() -> None:
    rows = apply_parking_overrides.load_rows(apply_parking_overrides.DEFAULT_CSV)
    sql = apply_parking_overrides.render_sql(rows)

    assert len(rows) >= 150, "expected real Catania override coverage"
    assert any(row["osm_street_name"] == "Via Antonino di Sangiuliano" for row in rows)
    assert any(row["osm_street_name"] == "Corso Italia" for row in rows)
    assert "parking_type = 'blue'" in sql
    assert "amts_piano_generale_sosta" in sql
    print("Parking override checks OK")


if __name__ == "__main__":
    main()
