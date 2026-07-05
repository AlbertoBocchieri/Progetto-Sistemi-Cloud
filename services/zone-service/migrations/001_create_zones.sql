CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS zones (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    zone_type TEXT NOT NULL,
    baseline_capacity_estimate INTEGER,
    polygon GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT zones_capacity_non_negative
        CHECK (
            baseline_capacity_estimate IS NULL
            OR baseline_capacity_estimate >= 0
        )
);

CREATE INDEX IF NOT EXISTS idx_zones_polygon
    ON zones
    USING GIST (polygon);

INSERT INTO zones (
    id,
    name,
    city,
    zone_type,
    baseline_capacity_estimate,
    polygon
)
VALUES (
    'ct-via-etnea-stesicoro',
    'Via Etnea / Stesicoro',
    'Catania',
    'central',
    350,
    ST_GeomFromText(
        'POLYGON((
            15.079 37.504,
            15.087 37.504,
            15.087 37.512,
            15.079 37.512,
            15.079 37.504
        ))',
        4326
    )
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    city = EXCLUDED.city,
    zone_type = EXCLUDED.zone_type,
    baseline_capacity_estimate = EXCLUDED.baseline_capacity_estimate,
    polygon = EXCLUDED.polygon;