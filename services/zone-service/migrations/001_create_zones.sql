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

CREATE TABLE IF NOT EXISTS parking_lots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    operator TEXT NOT NULL,
    zone_id TEXT NOT NULL REFERENCES zones(id),
    location GEOMETRY(POINT, 4326) NOT NULL,
    total_capacity INTEGER NOT NULL,
    pricing_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_park_and_ride BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT parking_lots_capacity_positive
        CHECK (total_capacity > 0)
);

CREATE INDEX IF NOT EXISTS idx_parking_lots_zone
    ON parking_lots (zone_id);

CREATE INDEX IF NOT EXISTS idx_parking_lots_location
    ON parking_lots
    USING GIST (location);

CREATE TABLE IF NOT EXISTS user_reports (
    id TEXT PRIMARY KEY,
    zone_id TEXT NOT NULL REFERENCES zones(id),
    report_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT user_reports_type_valid
        CHECK (report_type IN ('found_spot', 'full_zone'))
);

CREATE INDEX IF NOT EXISTS idx_user_reports_zone_created_at
    ON user_reports (zone_id, created_at DESC);

ALTER TABLE user_reports
    ADD COLUMN IF NOT EXISTS session_id TEXT;

ALTER TABLE user_reports
    DROP CONSTRAINT IF EXISTS user_reports_type_valid;

ALTER TABLE user_reports
    ADD CONSTRAINT user_reports_type_valid
        CHECK (report_type IN ('found_spot', 'full_zone', 'released_spot', 'parking_closed'));

INSERT INTO zones (
    id,
    name,
    city,
    zone_type,
    baseline_capacity_estimate,
    polygon
)
VALUES
(
    'ct-via-etnea-stesicoro',
    'Via Etnea / Stesicoro',
    'Catania',
    'central',
    350,
    ST_GeomFromText(
        'POLYGON((
            15.0790 37.5040,
            15.0870 37.5040,
            15.0870 37.5120,
            15.0790 37.5120,
            15.0790 37.5040
        ))',
        4326
    )
),
(
    'ct-piazza-universita',
    'Piazza Universita / Centro storico',
    'Catania',
    'historic',
    220,
    ST_GeomFromText(
        'POLYGON((
            15.0835 37.4990,
            15.0915 37.4990,
            15.0915 37.5060,
            15.0835 37.5060,
            15.0835 37.4990
        ))',
        4326
    )
),
(
    'ct-borgo-cittadella',
    'Borgo / Cittadella Universitaria',
    'Catania',
    'university',
    480,
    ST_GeomFromText(
        'POLYGON((
            15.0640 37.5200,
            15.0770 37.5200,
            15.0770 37.5310,
            15.0640 37.5310,
            15.0640 37.5200
        ))',
        4326
    )
),
(
    'ct-corso-italia',
    'Corso Italia',
    'Catania',
    'business',
    300,
    ST_GeomFromText(
        'POLYGON((
            15.0880 37.5140,
            15.0990 37.5140,
            15.0990 37.5220,
            15.0880 37.5220,
            15.0880 37.5140
        ))',
        4326
    )
),
(
    'ct-sanzio',
    'Sanzio',
    'Catania',
    'residential',
    420,
    ST_GeomFromText(
        'POLYGON((
            15.0780 37.5160,
            15.0880 37.5160,
            15.0880 37.5260,
            15.0780 37.5260,
            15.0780 37.5160
        ))',
        4326
    )
),
(
    'ct-piazza-europa',
    'Piazza Europa',
    'Catania',
    'seafront',
    260,
    ST_GeomFromText(
        'POLYGON((
            15.0990 37.5150,
            15.1100 37.5150,
            15.1100 37.5230,
            15.0990 37.5230,
            15.0990 37.5150
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

INSERT INTO parking_lots (
    id,
    name,
    operator,
    zone_id,
    location,
    total_capacity,
    pricing_info,
    is_park_and_ride
)
VALUES
(
    'park-borsellino',
    'Parcheggio Borsellino',
    'AMTS Catania',
    'ct-piazza-universita',
    ST_SetSRID(ST_MakePoint(15.0879, 37.5007), 4326),
    210,
    '{"type":"paid","note":"strutturato centro storico"}',
    false
),
(
    'park-stesicoro',
    'Autorimessa Stesicoro',
    'Demo operator',
    'ct-via-etnea-stesicoro',
    ST_SetSRID(ST_MakePoint(15.0830, 37.5074), 4326),
    95,
    '{"type":"paid","note":"alta rotazione"}',
    false
),
(
    'park-cittadella',
    'Cittadella Universitaria',
    'Universita di Catania',
    'ct-borgo-cittadella',
    ST_SetSRID(ST_MakePoint(15.0703, 37.5255), 4326),
    320,
    '{"type":"restricted","note":"orari universitari"}',
    false
),
(
    'park-corso-italia',
    'Parcheggio Corso Italia',
    'Demo operator',
    'ct-corso-italia',
    ST_SetSRID(ST_MakePoint(15.0932, 37.5182), 4326),
    140,
    '{"type":"paid","note":"business district"}',
    false
),
(
    'park-sanzio',
    'Parcheggio Sanzio',
    'AMTS Catania',
    'ct-sanzio',
    ST_SetSRID(ST_MakePoint(15.0822, 37.5216), 4326),
    260,
    '{"type":"paid","note":"alternativa al centro"}',
    false
),
(
    'park-europa',
    'Piazza Europa',
    'Demo operator',
    'ct-piazza-europa',
    ST_SetSRID(ST_MakePoint(15.1042, 37.5190), 4326),
    120,
    '{"type":"street","note":"lungomare"}',
    false
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    operator = EXCLUDED.operator,
    zone_id = EXCLUDED.zone_id,
    location = EXCLUDED.location,
    total_capacity = EXCLUDED.total_capacity,
    pricing_info = EXCLUDED.pricing_info,
    is_park_and_ride = EXCLUDED.is_park_and_ride;

CREATE TABLE IF NOT EXISTS parking_segments (
    id TEXT PRIMARY KEY,
    street_name TEXT NOT NULL,
    city TEXT NOT NULL DEFAULT 'Catania',
    parking_type TEXT NOT NULL,
    tariff_zone TEXT,
    price_label TEXT,
    time_rules TEXT,
    source TEXT NOT NULL,
    source_confidence NUMERIC(3, 2) NOT NULL DEFAULT 0.50,
    geometry GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_m NUMERIC(7, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT parking_segments_type_valid
        CHECK (parking_type IN ('blue', 'probable_free', 'restricted', 'unknown')),
    CONSTRAINT parking_segments_confidence_valid
        CHECK (source_confidence >= 0 AND source_confidence <= 1),
    CONSTRAINT parking_segments_length_positive
        CHECK (length_m > 0)
);

CREATE INDEX IF NOT EXISTS idx_parking_segments_geometry
    ON parking_segments
    USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_parking_segments_type
    ON parking_segments (parking_type);

CREATE TABLE IF NOT EXISTS road_nodes (
    id TEXT PRIMARY KEY,
    osm_node_id BIGINT,
    location GEOMETRY(POINT, 4326) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_road_nodes_location
    ON road_nodes
    USING GIST (location);

CREATE TABLE IF NOT EXISTS road_edges (
    id TEXT PRIMARY KEY,
    osm_way_id BIGINT NOT NULL,
    from_node_id TEXT NOT NULL REFERENCES road_nodes(id),
    to_node_id TEXT NOT NULL REFERENCES road_nodes(id),
    street_name TEXT,
    highway TEXT NOT NULL,
    one_way BOOLEAN NOT NULL DEFAULT false,
    geometry GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_m NUMERIC(8, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT road_edges_length_positive
        CHECK (length_m > 0)
);

CREATE INDEX IF NOT EXISTS idx_road_edges_geometry
    ON road_edges
    USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_road_edges_nodes
    ON road_edges (from_node_id, to_node_id);

WITH source_roads (
    road_id,
    street_name,
    parking_type,
    tariff_zone,
    price_label,
    time_rules,
    source,
    source_confidence,
    wkt
) AS (
    VALUES
    (
        'ct-etnea',
        'Via Etnea',
        'blue',
        'A',
        '1,00 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.78,
        'LINESTRING(15.0872 37.5010,15.0841 37.5049,15.0830 37.5074,15.0817 37.5128,15.0796 37.5200,15.0774 37.5258)'
    ),
    (
        'ct-vittorio-emanuele',
        'Via Vittorio Emanuele II',
        'blue',
        'A',
        '1,00 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.74,
        'LINESTRING(15.0802 37.5021,15.0847 37.5024,15.0888 37.5025,15.0930 37.5028)'
    ),
    (
        'ct-garibaldi',
        'Via Giuseppe Garibaldi',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.45,
        'LINESTRING(15.0800 37.5011,15.0856 37.5014,15.0910 37.5018,15.0966 37.5022)'
    ),
    (
        'ct-corso-sicilia',
        'Corso Sicilia',
        'blue',
        'A',
        '1,00 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.72,
        'LINESTRING(15.0804 37.5063,15.0840 37.5064,15.0882 37.5065,15.0920 37.5067)'
    ),
    (
        'ct-umberto',
        'Via Umberto I',
        'blue',
        'B',
        '0,87 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.70,
        'LINESTRING(15.0775 37.5098,15.0826 37.5107,15.0877 37.5118,15.0940 37.5134)'
    ),
    (
        'ct-pacini',
        'Via Pacini',
        'blue',
        'A',
        '1,00 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.70,
        'LINESTRING(15.0794 37.5064,15.0808 37.5090,15.0822 37.5117)'
    ),
    (
        'ct-santeuplio',
        'Via Sant''Euplio',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.48,
        'LINESTRING(15.0790 37.5042,15.0776 37.5084,15.0768 37.5117)'
    ),
    (
        'ct-xx-settembre',
        'Viale XX Settembre',
        'blue',
        'B',
        '0,87 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.70,
        'LINESTRING(15.0780 37.5118,15.0830 37.5142,15.0886 37.5166,15.0940 37.5189)'
    ),
    (
        'ct-giuffrida',
        'Via Vincenzo Giuffrida',
        'blue',
        'B',
        '0,87 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.68,
        'LINESTRING(15.0813 37.5147,15.0832 37.5194,15.0854 37.5243,15.0872 37.5280)'
    ),
    (
        'ct-corso-italia',
        'Corso Italia',
        'blue',
        'B',
        '0,87 EUR/h',
        'Lun-Sab 08:30-13:30 e 15:30-20:00',
        'manual_override',
        0.70,
        'LINESTRING(15.0893 37.5150,15.0942 37.5171,15.0998 37.5193,15.1053 37.5214)'
    ),
    (
        'ct-viale-africa',
        'Viale Africa',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.50,
        'LINESTRING(15.1009 37.5105,15.1025 37.5152,15.1040 37.5201,15.1053 37.5250)'
    ),
    (
        'ct-ruggero-lauria',
        'Viale Ruggero di Lauria',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.48,
        'LINESTRING(15.1036 37.5150,15.1061 37.5180,15.1091 37.5211,15.1120 37.5242)'
    ),
    (
        'ct-caronda',
        'Via Caronda',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.47,
        'LINESTRING(15.0790 37.5119,15.0776 37.5170,15.0758 37.5220,15.0736 37.5280)'
    ),
    (
        'ct-santa-sofia',
        'Via Santa Sofia',
        'restricted',
        NULL,
        NULL,
        'Aree universitarie e accessi regolati: verifica segnaletica',
        'manual_override',
        0.62,
        'LINESTRING(15.0695 37.5200,15.0702 37.5240,15.0711 37.5282,15.0725 37.5321)'
    ),
    (
        'ct-andrea-doria',
        'Viale Andrea Doria',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.50,
        'LINESTRING(15.0648 37.5211,15.0691 37.5220,15.0743 37.5232,15.0796 37.5247)'
    ),
    (
        'ct-plebiscito',
        'Via Plebiscito',
        'probable_free',
        NULL,
        NULL,
        'Verifica segnaletica locale',
        'aggressive_inference',
        0.45,
        'LINESTRING(15.0745 37.5003,15.0804 37.5034,15.0863 37.5065,15.0925 37.5094)'
    )
),
split_segments AS (
    SELECT
        road_id,
        street_name,
        parking_type,
        tariff_zone,
        price_label,
        time_rules,
        source,
        source_confidence,
        ROW_NUMBER() OVER (PARTITION BY road_id ORDER BY dumped.path) AS segment_index,
        ST_Transform(dumped.geom, 4326)::GEOMETRY(LINESTRING, 4326) AS geometry
    FROM source_roads
    CROSS JOIN LATERAL (
        SELECT (ST_DumpSegments(
            ST_Segmentize(
                ST_Transform(ST_GeomFromText(wkt, 4326), 3857),
                120
            )
        )).*
    ) AS dumped
)
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
SELECT
    road_id || '-' || LPAD(segment_index::TEXT, 2, '0') AS id,
    street_name,
    'Catania',
    parking_type,
    tariff_zone,
    price_label,
    time_rules,
    source,
    source_confidence,
    geometry,
    ST_Length(geometry::geography)
FROM split_segments
WHERE ST_Length(geometry::geography) >= 15
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

ALTER TABLE parking_lots
    ADD COLUMN IF NOT EXISTS segment_id TEXT REFERENCES parking_segments(id);

UPDATE parking_lots AS lot
SET segment_id = (
    SELECT segment.id
    FROM parking_segments AS segment
    ORDER BY segment.geometry::geography <-> lot.location::geography
    LIMIT 1
);

CREATE INDEX IF NOT EXISTS idx_parking_lots_segment
    ON parking_lots (segment_id);

CREATE TABLE IF NOT EXISTS segment_reports (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL REFERENCES parking_segments(id),
    report_type TEXT NOT NULL,
    session_id TEXT,
    influence_weight NUMERIC(4, 2) NOT NULL DEFAULT 1.00,
    source_report_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT segment_reports_type_valid
        CHECK (report_type IN ('found_spot', 'full_zone', 'released_spot', 'parking_closed')),
    CONSTRAINT segment_reports_weight_valid
        CHECK (influence_weight > 0 AND influence_weight <= 1)
);

CREATE INDEX IF NOT EXISTS idx_segment_reports_segment_created_at
    ON segment_reports (segment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_segment_reports_source
    ON segment_reports (source_report_id);
