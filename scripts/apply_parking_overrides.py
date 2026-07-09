#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path("data/parking_overrides/catania_blue_zones.csv")
DEFAULT_SQL = Path("data/osm/catania_blue_overrides.sql")


def sql_quote(value: Any) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "official_name",
        "osm_street_name",
        "match_key",
        "zone_numbers",
        "tariff_zone",
        "price_label",
        "time_rules",
        "stall_count",
        "source",
        "source_confidence",
    }
    missing = required - set(rows[0] if rows else [])
    if missing:
        raise SystemExit(f"{path} missing columns: {', '.join(sorted(missing))}")
    for row in rows:
        if row["match_key"] != normalize_key(row["osm_street_name"]):
            raise SystemExit(f"match_key mismatch for {row['osm_street_name']}")
    return rows


def render_sql(rows: list[dict[str, str]]) -> str:
    values = []
    for row in rows:
        values.append(
            "("
            f"{sql_quote(row['match_key'])}, "
            f"{sql_quote(row['tariff_zone'])}, "
            f"{sql_quote(row['price_label'])}, "
            f"{sql_quote(row['time_rules'])}, "
            f"{sql_quote(row['source'])}, "
            f"{float(row['source_confidence']):.2f}, "
            f"{sql_quote(row['official_name'])}, "
            f"{sql_quote(row['zone_numbers'])}, "
            f"{int(row['stall_count'])}"
            ")"
        )
    sql = [
        "BEGIN;",
        """
CREATE TEMP TABLE parking_blue_override (
    match_key TEXT PRIMARY KEY,
    tariff_zone TEXT,
    price_label TEXT,
    time_rules TEXT,
    source TEXT,
    source_confidence NUMERIC(3, 2),
    official_name TEXT,
    zone_numbers TEXT,
    stall_count INTEGER
);
""".strip(),
    ]
    if values:
        sql.extend(
            [
                "INSERT INTO parking_blue_override VALUES",
                ",\n".join(values) + ";",
                """
UPDATE parking_segments AS segment
SET
    parking_type = 'blue',
    tariff_zone = override.tariff_zone,
    price_label = override.price_label,
    time_rules = override.time_rules,
    source = override.source,
    source_confidence = override.source_confidence
FROM parking_blue_override AS override
WHERE lower(regexp_replace(segment.street_name, '[^a-zA-Z0-9]+', '', 'g')) = override.match_key;
""".strip(),
            ]
        )
    sql.append("COMMIT;")
    sql.append(f"-- override_streets={len(rows)}")
    return "\n".join(sql) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SQL for Catania blue-stripe parking overrides.")
    parser.add_argument("csv_path", type=Path, nargs="?", default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_SQL)
    args = parser.parse_args()

    rows = load_rows(args.csv_path)
    sql = render_sql(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sql, encoding="utf-8")
    print(f"Wrote {args.output} for {len(rows)} override streets")


if __name__ == "__main__":
    main()
