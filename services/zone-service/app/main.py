import hashlib
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pika
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.schemas import (
    HeatmapResponse,
    HeatmapZoneResponse,
    NearbyZoneResponse,
    NearbySegmentResponse,
    LiveSessionResponse,
    LocationUpdateRequest,
    LocationUpdateResponse,
    ParkingSegmentResponse,
    PredictionResponse,
    ReportRequest,
    ReportResponse,
    RoadEdgeResponse,
    RoadNetworkResponse,
    RoadNodeResponse,
    SegmentHeatmapItemResponse,
    SegmentHeatmapResponse,
    SegmentReportRequest,
    ZoneResponse,
)


app = FastAPI(
    title="ParcheggIA Demo API",
    description="Demo locale geospaziale per il radar del parcheggio.",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL",
    "amqp://parcheggia:parcheggia@localhost:5672/%2F",
)
EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "parcheggia.events")
EVENT_QUEUE = os.getenv("EVENT_QUEUE", "zone-service.events")
REDIS = Redis.from_url(REDIS_URL, decode_responses=True)
LAST_EVENT_AT: str | None = None
REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}
REPORT_TYPES = {"found_spot", "full_zone", "released_spot", "parking_closed"}
LOCAL_RADIUS_M = 500
ROAD_NETWORK_RADIUS_M = 700
ROAD_BACKED_SEGMENT_SQL = (
    "(\n"
    "    parking_segments.id LIKE 'ct-osm-%'\n"
    "    OR (\n"
    "        parking_segments.id LIKE 'ct-%'\n"
    "        AND NOT EXISTS (\n"
    "            SELECT 1\n"
    "            FROM parking_segments AS osm_segments\n"
    "            WHERE osm_segments.id LIKE 'ct-osm-%'\n"
    "        )\n"
    "    )\n"
    ")"
)
SEGMENT_HEATMAP_CACHE_VERSION = "road-backed-osm-auto-v1"

ZONE_COLUMNS = """
    id,
    name,
    city,
    zone_type,
    baseline_capacity_estimate,
    ST_AsGeoJSON(polygon)::json AS geometry,
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'id', parking_lots.id,
                    'name', parking_lots.name,
                    'operator', parking_lots.operator,
                    'total_capacity', parking_lots.total_capacity,
                    'is_park_and_ride', parking_lots.is_park_and_ride,
                    'location', ST_AsGeoJSON(parking_lots.location)::json,
                    'pricing_info', parking_lots.pricing_info
                )
                ORDER BY parking_lots.name
            )
            FROM parking_lots
            WHERE parking_lots.zone_id = zones.id
        ),
        '[]'::json
    ) AS parking_lots
"""

SEGMENT_COLUMNS = """
    parking_segments.id,
    parking_segments.street_name,
    parking_segments.city,
    parking_segments.parking_type,
    parking_segments.tariff_zone,
    parking_segments.price_label,
    parking_segments.time_rules,
    parking_segments.source,
    parking_segments.source_confidence::float AS source_confidence,
    ROUND(parking_segments.length_m)::int AS length_m,
    ST_AsGeoJSON(parking_segments.geometry)::json AS geometry,
    COALESCE(
        (
            SELECT json_agg(
                json_build_object(
                    'id', parking_lots.id,
                    'name', parking_lots.name,
                    'operator', parking_lots.operator,
                    'total_capacity', parking_lots.total_capacity,
                    'is_park_and_ride', parking_lots.is_park_and_ride,
                    'location', ST_AsGeoJSON(parking_lots.location)::json,
                    'pricing_info', parking_lots.pricing_info
                )
                ORDER BY parking_lots.name
            )
            FROM parking_lots
            WHERE parking_lots.segment_id = parking_segments.id
        ),
        '[]'::json
    ) AS parking_lots
"""


def segment_where(extra: str = "") -> str:
    return f"WHERE {ROAD_BACKED_SEGMENT_SQL}{f' AND {extra}' if extra else ''}"

# ponytail: deterministic demo predictions; split into prediction-service when ingestion exists.
DEMO_PREDICTIONS = {
    "ct-via-etnea-stesicoro": {
        "percent": 28,
        "trend": "worse",
        "confidence": 0.72,
        "search_time": 22,
        "recommendation": "Zona difficile: prova le laterali a nord se non hai fretta.",
    },
    "ct-piazza-universita": {
        "percent": 18,
        "trend": "stable",
        "confidence": 0.68,
        "search_time": 29,
        "recommendation": "Centro storico molto saturo: meglio puntare a Sanzio o Corso Italia.",
    },
    "ct-borgo-cittadella": {
        "percent": 34,
        "trend": "stable",
        "confidence": 0.69,
        "search_time": 18,
        "recommendation": "Disponibilita bassa vicino all'universita: cerca prima nelle traverse.",
    },
    "ct-corso-italia": {
        "percent": 57,
        "trend": "better",
        "confidence": 0.74,
        "search_time": 12,
        "recommendation": "Possibilita media: gira su assi paralleli prima di entrare nel centro.",
    },
    "ct-sanzio": {
        "percent": 64,
        "trend": "better",
        "confidence": 0.77,
        "search_time": 9,
        "recommendation": "Buona alternativa: resta su Sanzio se il centro peggiora.",
    },
    "ct-piazza-europa": {
        "percent": 44,
        "trend": "stable",
        "confidence": 0.71,
        "search_time": 15,
        "recommendation": "Situazione incerta: controlla prima le strade verso il lungomare.",
    },
}

SEGMENT_BASELINES = {
    "blue": {
        "percent": 42,
        "confidence": 0.70,
        "search_time": 16,
        "recommendation": "Strisce blu: buona rotazione, controlla tariffa e orari sul posto.",
    },
    "probable_free": {
        "percent": 48,
        "confidence": 0.52,
        "search_time": 18,
        "recommendation": "Probabile libero: stima inferita, verifica sempre la segnaletica.",
    },
    "restricted": {
        "percent": 14,
        "confidence": 0.66,
        "search_time": 30,
        "recommendation": "Sosta probabilmente regolata o limitata: cerca alternative vicine.",
    },
    "unknown": {
        "percent": 42,
        "confidence": 0.42,
        "search_time": 22,
        "recommendation": "Dati limitati: usa la stima come indicazione e verifica sul posto.",
    },
}

DEMO_SEGMENT_PERCENTS = {
    "ct-vittorio-emanuele": 10,
    "ct-santa-sofia": 8,
    "ct-plebiscito": 24,
    "ct-etnea": 28,
    "ct-garibaldi": 25,
    "ct-caronda": 42,
    "ct-corso-sicilia": 45,
    "ct-umberto": 52,
    "ct-pacini": 57,
    "ct-santeuplio": 61,
    "ct-xx-settembre": 65,
    "ct-ruggero-lauria": 66,
    "ct-giuffrida": 70,
    "ct-andrea-doria": 72,
    "ct-corso-italia": 75,
    "ct-viale-africa": 80,
}

LIVE_SESSIONS: dict[str, dict[str, Any]] = {}


def iso_z(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def row_to_zone(row: Any) -> ZoneResponse:
    return ZoneResponse(**dict(row))


def parking_label(segment: dict[str, Any]) -> str:
    parking_type = segment.get("parking_type")
    if parking_type == "blue":
        zone = segment.get("tariff_zone")
        return f"Strisce blu · Zona {zone}" if zone else "Strisce blu"
    if parking_type == "probable_free":
        return "Probabile libero"
    if parking_type == "restricted":
        return "Limitato"
    return "Da verificare"


def row_to_segment(row: Any) -> ParkingSegmentResponse:
    data = dict(row)
    data["parking_label"] = parking_label(data)
    return ParkingSegmentResponse(**data)


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def redis_json_get(key: str) -> dict[str, Any] | list[Any] | None:
    try:
        value = REDIS.get(key)
    except RedisError as error:
        print(f"Redis get failed for {key}: {error}")
        return None

    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def redis_json_set(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        REDIS.setex(key, ttl_seconds, json.dumps(value))
    except RedisError as error:
        print(f"Redis set failed for {key}: {error}")


def redis_delete_pattern(pattern: str) -> None:
    try:
        keys = list(REDIS.scan_iter(pattern))
        if keys:
            REDIS.delete(*keys)
    except RedisError as error:
        print(f"Redis delete failed for {pattern}: {error}")


def status_from_percent(percent: int) -> str:
    if percent < 20:
        return "very_difficult"
    if percent < 40:
        return "difficult"
    if percent < 60:
        return "uncertain"
    if percent < 80:
        return "good"
    return "favorable"


def demo_segment_percent(segment_id: str, fallback: int) -> int:
    road_id = segment_id.rsplit("-", 1)[0]
    return DEMO_SEGMENT_PERCENTS.get(road_id, fallback)


SIMULATED_PERCENT_RANGES = {
    "blue": (28, 72),
    "probable_free": (22, 78),
    "restricted": (5, 24),
    "unknown": (24, 62),
}


def simulated_segment_percent(segment: dict[str, Any], fallback: int) -> int:
    segment_id = segment["id"]
    if not segment_id.startswith("ct-osm-"):
        return demo_segment_percent(segment_id, fallback)

    low, high = SIMULATED_PERCENT_RANGES.get(
        segment.get("parking_type"),
        SIMULATED_PERCENT_RANGES["unknown"],
    )
    street_key = f"{segment.get('street_name', '')}:{segment.get('parking_type', '')}"
    base_unit = int(hashlib.sha1(street_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    base = low + round(base_unit * (high - low))
    noise = int(hashlib.sha1(segment_id.encode()).hexdigest()[:2], 16) % 11 - 5
    return max(low, min(high, base + noise))


def report_adjustment(found_spot: Any, full_zone: Any, released_spot: Any = 0, parking_closed: Any = 0) -> int:
    found = float(found_spot or 0)
    full = float(full_zone or 0)
    released = float(released_spot or 0)
    closed = float(parking_closed or 0)
    return round(max(-15, min(15, found * 5 + released * 6 - full * 7 - closed * 8)))


def load_zone_signals(zone_id: str) -> dict[str, Any]:
    try:
        return dict(REDIS.hgetall(f"zone:signals:{zone_id}"))
    except RedisError as error:
        print(f"Redis signals load failed for {zone_id}: {error}")
        return {}


def load_segment_signals(segment_id: str) -> dict[str, Any]:
    try:
        return dict(REDIS.hgetall(f"segment:signals:{segment_id}"))
    except RedisError as error:
        print(f"Redis signals load failed for {segment_id}: {error}")
        return {}


def signal_adjustment(signals: dict[str, Any]) -> int:
    if not signals:
        return 0

    traffic_pressure = clamp01(signals.get("traffic_pressure"))
    parking_availability = clamp01(signals.get("parking_lot_availability"), 0.5)
    event_pressure = clamp01(signals.get("event_pressure"))

    adjustment = round(
        (parking_availability - 0.5) * 35
        - traffic_pressure * 22
        - event_pressure * 18
    )
    return max(-35, min(20, adjustment))


def build_prediction(
    zone_id: str,
    adjustment: int = 0,
    signals: dict[str, Any] | None = None,
) -> PredictionResponse:
    demo = DEMO_PREDICTIONS.get(
        zone_id,
        {
            "percent": 50,
            "trend": "stable",
            "confidence": 0.60,
            "search_time": 15,
            "recommendation": "Dati limitati: usa la stima come indicazione.",
        },
    )
    signals = signals or {}
    signal_delta = signal_adjustment(signals)
    total_adjustment = adjustment + signal_delta
    percent = max(5, min(95, int(demo["percent"]) + total_adjustment))
    search_time = max(3, min(35, int(demo["search_time"]) - round(total_adjustment / 3)))
    trend = str(demo["trend"])
    confidence = float(demo["confidence"])
    recommendation = str(demo["recommendation"])

    if signal_delta <= -6:
        trend = "worse"
        confidence = min(0.90, confidence + 0.08)
    elif signal_delta >= 6:
        trend = "better"
        confidence = min(0.90, confidence + 0.08)

    scenario_label = signals.get("scenario_label")
    if scenario_label:
        recommendation = f"Scenario demo attivo: {scenario_label}."

    return PredictionResponse(
        segment_id=zone_id,
        parkability_score=round(percent / 100, 2),
        parkability_percent=percent,
        status=status_from_percent(percent),
        trend=trend,
        confidence=confidence,
        estimated_search_time_min=search_time,
        recommendation=recommendation,
    )


def time_adjustment() -> int:
    now = datetime.now()
    if now.weekday() >= 5:
        return 3
    if 8 <= now.hour <= 10 or 17 <= now.hour <= 20:
        return -7
    if 0 <= now.hour <= 6:
        return 6
    return 0


def segment_prediction_from_row(
    row: Any,
    report_delta: int = 0,
) -> PredictionResponse:
    segment = dict(row)
    segment_id = segment["id"]
    baseline = SEGMENT_BASELINES.get(segment["parking_type"], SEGMENT_BASELINES["unknown"])
    signals = load_segment_signals(segment_id)
    signature = json.dumps(
        {
            "parking_type": segment["parking_type"],
            "report_delta": report_delta,
            "signals": signals,
            "hour": datetime.now().hour,
            "weekday": datetime.now().weekday(),
        },
        sort_keys=True,
    )
    cache_key = f"segment-prediction:{segment_id}:{hashlib.sha1(signature.encode()).hexdigest()}"
    cached = redis_json_get(cache_key)
    if isinstance(cached, dict):
        return PredictionResponse(**cached)

    signal_delta = signal_adjustment(signals)
    total_delta = report_delta + signal_delta + time_adjustment()
    base_percent = simulated_segment_percent(segment, int(baseline["percent"]))
    percent = max(4, min(92, base_percent + total_delta))
    search_time = max(3, min(38, int(baseline["search_time"]) - round(total_delta / 3)))
    trend = "stable"
    confidence = min(0.92, float(baseline["confidence"]) + float(segment["source_confidence"]) * 0.12)
    recommendation = f"{segment['street_name']}: {baseline['recommendation']}"

    if signal_delta <= -6 or report_delta <= -6:
        trend = "worse"
        confidence = min(0.92, confidence + 0.08)
    elif signal_delta >= 6 or report_delta >= 6:
        trend = "better"
        confidence = min(0.92, confidence + 0.08)

    if signals.get("scenario_label"):
        recommendation = f"{segment['street_name']}: scenario demo attivo, {signals['scenario_label']}."

    prediction = PredictionResponse(
        segment_id=segment_id,
        parkability_score=round(percent / 100, 2),
        parkability_percent=percent,
        status=status_from_percent(percent),
        trend=trend,
        confidence=round(confidence, 2),
        estimated_search_time_min=search_time,
        recommendation=recommendation,
        parking_type=segment["parking_type"],
        parking_label=parking_label(segment),
    )
    redis_json_set(cache_key, prediction.model_dump(), 30)
    return prediction


def load_prediction(zone_id: str, report_delta: int = 0) -> PredictionResponse:
    signals = load_zone_signals(zone_id)
    signature = json.dumps(
        {"report_delta": report_delta, "signals": signals},
        sort_keys=True,
    )
    cache_key = f"prediction:{zone_id}:{hashlib.sha1(signature.encode()).hexdigest()}"
    cached = redis_json_get(cache_key)
    if isinstance(cached, dict):
        return PredictionResponse(**cached)

    prediction = build_prediction(zone_id, report_delta, signals)
    redis_json_set(cache_key, prediction.model_dump(), 30)
    return prediction


def require_live_session(session_id: str) -> dict[str, Any]:
    session = None
    try:
        raw_session = REDIS.get(f"live_session:{session_id}")
        session = json.loads(raw_session) if raw_session else None
    except (RedisError, json.JSONDecodeError) as error:
        print(f"Redis session load failed for {session_id}: {error}")

    session = session or LIVE_SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session not found",
        )
    return session


def save_live_session(session: dict[str, Any]) -> None:
    LIVE_SESSIONS[session["session_id"]] = session
    try:
        REDIS.setex(
            f"live_session:{session['session_id']}",
            3600,
            json.dumps(session),
        )
    except RedisError as error:
        print(f"Redis session save failed: {error}")


def live_session_response(session: dict[str, Any]) -> LiveSessionResponse:
    return LiveSessionResponse(
        session_id=session["session_id"],
        status=session["status"],
        started_at=session["started_at"],
        ended_at=session.get("ended_at"),
    )


def load_recent_report_adjustments(connection: Any) -> dict[str, int]:
    rows = connection.execute(
        text(
            """
                SELECT
                    zone_id,
                    COUNT(*) FILTER (WHERE report_type = 'found_spot') AS found_spot,
                    COUNT(*) FILTER (WHERE report_type = 'full_zone') AS full_zone,
                    COUNT(*) FILTER (WHERE report_type = 'released_spot') AS released_spot,
                    COUNT(*) FILTER (WHERE report_type = 'parking_closed') AS parking_closed
                FROM user_reports
                WHERE created_at >= NOW() - INTERVAL '30 minutes'
                GROUP BY zone_id
            """
        )
    ).mappings()

    return {
        row["zone_id"]: report_adjustment(
            row["found_spot"],
            row["full_zone"],
            row["released_spot"],
            row["parking_closed"],
        )
        for row in rows
    }


def load_recent_segment_report_adjustments(connection: Any) -> dict[str, int]:
    rows = connection.execute(
        text(
            """
                SELECT
                    segment_id,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'found_spot'), 0) AS found_spot,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'full_zone'), 0) AS full_zone,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'released_spot'), 0) AS released_spot,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'parking_closed'), 0) AS parking_closed
                FROM segment_reports
                WHERE created_at >= NOW() - INTERVAL '30 minutes'
                GROUP BY segment_id
            """
        )
    ).mappings()

    return {
        row["segment_id"]: report_adjustment(
            row["found_spot"],
            row["full_zone"],
            row["released_spot"],
            row["parking_closed"],
        )
        for row in rows
    }


def invalidate_zone_cache(zone_id: str | None = None) -> None:
    redis_delete_pattern("heatmap:*")
    if zone_id is None:
        redis_delete_pattern("prediction:*")
    else:
        redis_delete_pattern(f"prediction:{zone_id}:*")


def invalidate_segment_cache(segment_id: str | None = None) -> None:
    redis_delete_pattern("segment-heatmap:*")
    if segment_id is None:
        redis_delete_pattern("segment-prediction:*")
    else:
        redis_delete_pattern(f"segment-prediction:{segment_id}:*")


def event_signal_update(event: dict[str, Any]) -> tuple[str, float] | None:
    event_type = event.get("event_type")
    payload = event.get("payload") or {}

    if event_type == "traffic.snapshot.received":
        if "traffic_pressure" in payload:
            return "traffic_pressure", clamp01(payload.get("traffic_pressure"))

        current_speed = clamp01(payload.get("current_speed"), 0.0)
        free_flow_speed = clamp01(payload.get("free_flow_speed"), 1.0)
        if free_flow_speed <= 0:
            return "traffic_pressure", 1.0
        return "traffic_pressure", 1 - min(1.0, current_speed / free_flow_speed)

    if event_type == "parkinglot.availability.updated":
        return "parking_lot_availability", clamp01(
            payload.get("parking_lot_availability")
        )

    if event_type == "city.event.created":
        return "event_pressure", clamp01(payload.get("event_pressure"))

    return None


def store_raw_event(event: dict[str, Any]) -> None:
    try:
        REDIS.lpush("raw_events", json.dumps(event))
        REDIS.ltrim("raw_events", 0, 99)
    except RedisError as error:
        print(f"Redis raw event save failed: {error}")


def publish_event(event: dict[str, Any]) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EVENT_EXCHANGE, exchange_type="fanout", durable=True)
        channel.basic_publish(
            exchange=EVENT_EXCHANGE,
            routing_key="",
            body=json.dumps(event).encode("utf-8"),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        connection.close()


def event_segment_targets(event: dict[str, Any]) -> list[tuple[str, float]]:
    segment_id = event.get("segment_id")
    if segment_id:
        return [(str(segment_id), 1.0)]

    zone_id = event.get("zone_id")
    if zone_id:
        try:
            with engine.connect() as connection:
                return [
                    (row["id"], 1.0)
                    for row in connection.execute(
                        text(
                            f"""
                            SELECT parking_segments.id
                            FROM parking_segments
                            JOIN zones ON ST_Intersects(parking_segments.geometry, zones.polygon)
                            WHERE zones.id = :zone_id
                              AND {ROAD_BACKED_SEGMENT_SQL}
                            """
                        ),
                        {"zone_id": zone_id},
                    ).mappings()
                ]
        except SQLAlchemyError as error:
            print(f"Unable to map event zone to segments: {error}")
            return []

    lat = event.get("lat")
    lon = event.get("lon")
    radius_m = event.get("radius_m") or (event.get("payload") or {}).get("radius_m") or LOCAL_RADIUS_M
    if lat is None or lon is None:
        return []

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    WITH anchor AS (
                        SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
                    )
                    SELECT
                        parking_segments.id,
                        GREATEST(
                            0.20,
                            1 - ST_Distance(
                                parking_segments.geometry::geography,
                                anchor.geom::geography
                            ) / :radius_m
                        )::float AS influence_weight
                    FROM parking_segments, anchor
                    WHERE ST_DWithin(
                        parking_segments.geometry::geography,
                        anchor.geom::geography,
                        :radius_m
                    )
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    ORDER BY influence_weight DESC, parking_segments.id
                    """
                ),
                {"lat": float(lat), "lon": float(lon), "radius_m": float(radius_m)},
            ).mappings().all()
            return [(row["id"], float(row["influence_weight"])) for row in rows]
    except (TypeError, ValueError, SQLAlchemyError) as error:
        print(f"Unable to map event coordinates to segments: {error}")
        return []


def event_segment_ids(event: dict[str, Any]) -> list[str]:
    return [segment_id for segment_id, _ in event_segment_targets(event)]


def weighted_signal_value(value: float, weight: float) -> float:
    return round(max(0.0, min(1.0, value * weight)), 3)


def apply_event(event: dict[str, Any]) -> None:
    global LAST_EVENT_AT

    update = event_signal_update(event)
    if update is None:
        store_raw_event(event)
        return

    targets = event_segment_targets(event)
    if not targets:
        store_raw_event(event)
        return

    field, value = update
    now = iso_z(datetime.now(UTC))

    for segment_id, weight in targets:
        key = f"segment:signals:{segment_id}"
        try:
            REDIS.hset(
                key,
                mapping={
                    field: weighted_signal_value(value, weight),
                    "updated_at": now,
                    "scenario_id": event.get("scenario_id", ""),
                    "scenario_label": event.get("scenario_label", ""),
                },
            )
            REDIS.expire(key, 1800)
        except RedisError as error:
            print(f"Redis signal update failed for {segment_id}: {error}")

    LAST_EVENT_AT = now
    store_raw_event(event)
    invalidate_segment_cache()


def consume_events() -> None:
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.exchange_declare(
                exchange=EVENT_EXCHANGE,
                exchange_type="fanout",
                durable=True,
            )
            channel.queue_declare(queue=EVENT_QUEUE, durable=True)
            channel.queue_bind(exchange=EVENT_EXCHANGE, queue=EVENT_QUEUE)
            channel.basic_qos(prefetch_count=10)

            def on_message(channel: Any, method: Any, _: Any, body: bytes) -> None:
                try:
                    apply_event(json.loads(body))
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as error:
                    print(f"RabbitMQ event handling failed: {error}")
                    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=EVENT_QUEUE, on_message_callback=on_message)
            channel.start_consuming()
        except Exception as error:
            print(f"RabbitMQ consumer retrying after failure: {error}")
            time.sleep(5)


@app.on_event("startup")
def start_event_consumer() -> None:
    thread = threading.Thread(target=consume_events, daemon=True)
    thread.start()


@app.middleware("http")
async def count_requests(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    started = time.perf_counter()
    status_code = 500
    response = None
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        status_code = response.status_code
        return response
    finally:
        key = (request.method, request.url.path, status_code)
        REQUEST_COUNTS[key] = REQUEST_COUNTS.get(key, 0) + 1
        print(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "service": "zone-service",
                }
            )
        )


def parse_bbox(bbox: str | None) -> tuple[str, dict[str, float]]:
    if bbox is None:
        return "", {}

    try:
        min_lon, min_lat, max_lon, max_lat = [float(part) for part in bbox.split(",")]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox must be minLon,minLat,maxLon,maxLat",
        ) from error

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox min values must be smaller than max values",
        )

    return (
        """
        WHERE ST_Intersects(
            polygon,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
        )
        """,
        {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
        },
    )


def parse_segment_bbox(bbox: str | None) -> tuple[str, dict[str, float]]:
    if bbox is None:
        return segment_where(), {}

    try:
        min_lon, min_lat, max_lon, max_lat = [float(part) for part in bbox.split(",")]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox must be minLon,minLat,maxLon,maxLat",
        ) from error

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bbox min values must be smaller than max values",
        )

    return (
        f"""
        WHERE {ROAD_BACKED_SEGMENT_SQL}
          AND ST_Intersects(
            parking_segments.geometry,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
        )
        """,
        {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat,
        },
    )


@app.get("/api/v1/health", include_in_schema=False)
@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "up",
        "service": "demo-api",
    }


@app.get("/api/v1/ready", include_in_schema=False)
@app.get("/ready")
def readiness_check() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            postgis_version = connection.execute(
                text("SELECT PostGIS_Version()")
            ).scalar_one()
            zone_count = connection.execute(text("SELECT COUNT(*) FROM zones")).scalar_one()
            segment_count = connection.execute(text("SELECT COUNT(*) FROM parking_segments")).scalar_one()
        REDIS.ping()

        return {
            "status": "ready",
            "database": "up",
            "redis": "up",
            "postgis_version": postgis_version,
            "zone_count": zone_count,
            "segment_count": segment_count,
            "last_event_at": LAST_EVENT_AT,
        }

    except (SQLAlchemyError, RedisError) as error:
        print(f"Readiness check failed: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required dependency is not available",
        ) from error


@app.get("/api/v1/metrics", response_class=PlainTextResponse, include_in_schema=False)
@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = [
        "# HELP parcheggia_http_requests_total HTTP requests by method, path and status.",
        "# TYPE parcheggia_http_requests_total counter",
    ]

    for (method, path, status_code), count in sorted(REQUEST_COUNTS.items()):
        lines.append(
            "parcheggia_http_requests_total"
            f'{{method="{method}",path="{path}",status="{status_code}"}} {count}'
        )

    if LAST_EVENT_AT:
        event_time = datetime.fromisoformat(LAST_EVENT_AT.replace("Z", "+00:00"))
        lines.extend(
            [
                "# HELP parcheggia_last_event_timestamp_seconds Last consumed event time.",
                "# TYPE parcheggia_last_event_timestamp_seconds gauge",
                f"parcheggia_last_event_timestamp_seconds {int(event_time.timestamp())}",
            ]
        )

    return "\n".join(lines) + "\n"


@app.post("/api/v1/live-sessions/start", response_model=LiveSessionResponse, include_in_schema=False)
@app.post("/live-sessions/start", response_model=LiveSessionResponse)
def start_live_session() -> LiveSessionResponse:
    now = iso_z(datetime.now(UTC))
    session_id = str(uuid4())
    session = {
        "session_id": session_id,
        "status": "active",
        "started_at": now,
        "ended_at": None,
        "last_lat": None,
        "last_lon": None,
    }
    save_live_session(session)
    return live_session_response(session)


@app.post(
    "/api/v1/live-sessions/{session_id}/location",
    response_model=LocationUpdateResponse,
    include_in_schema=False,
)
@app.post("/live-sessions/{session_id}/location", response_model=LocationUpdateResponse)
def update_live_session_location(
    session_id: str,
    location: LocationUpdateRequest,
) -> LocationUpdateResponse:
    session = require_live_session(session_id)
    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live session is not active",
        )

    current_segment = None
    prediction = None

    try:
        current_segment = get_current_segment(location.lat, location.lon)
        prediction = get_segment_prediction(current_segment.id)
    except HTTPException as error:
        if error.status_code != status.HTTP_404_NOT_FOUND:
            raise

    nearby_segments = get_nearby_segments(location.lat, location.lon, LOCAL_RADIUS_M, 8)
    session["last_lat"] = location.lat
    session["last_lon"] = location.lon
    save_live_session(session)

    return LocationUpdateResponse(
        session_id=session_id,
        status=session["status"],
        current_segment=current_segment,
        prediction=prediction,
        nearby_segments=nearby_segments,
    )


@app.get(
    "/api/v1/live-sessions/{session_id}/nearby-segments",
    response_model=list[NearbySegmentResponse],
    include_in_schema=False,
)
@app.get("/live-sessions/{session_id}/nearby-segments", response_model=list[NearbySegmentResponse])
def get_live_session_nearby_segments(session_id: str) -> list[NearbySegmentResponse]:
    session = require_live_session(session_id)
    if session["last_lat"] is None or session["last_lon"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live session has no location yet",
        )
    return get_nearby_segments(session["last_lat"], session["last_lon"], LOCAL_RADIUS_M, 8)


@app.post("/api/v1/live-sessions/{session_id}/stop", response_model=LiveSessionResponse, include_in_schema=False)
@app.post("/live-sessions/{session_id}/stop", response_model=LiveSessionResponse)
def stop_live_session(session_id: str) -> LiveSessionResponse:
    session = require_live_session(session_id)
    session["status"] = "stopped"
    session["ended_at"] = iso_z(datetime.now(UTC))
    save_live_session(session)
    return live_session_response(session)


@app.get("/api/v1/segments", response_model=list[ParkingSegmentResponse], include_in_schema=False)
@app.get("/segments", response_model=list[ParkingSegmentResponse])
def get_segments() -> list[ParkingSegmentResponse]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT {SEGMENT_COLUMNS}
                    FROM parking_segments
                    WHERE {ROAD_BACKED_SEGMENT_SQL}
                    ORDER BY street_name, id
                    """
                )
            ).mappings().all()

        return [row_to_segment(row) for row in rows]

    except SQLAlchemyError as error:
        print(f"Unable to load segments: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load segments",
        ) from error


@app.get("/api/v1/segments/nearby", response_model=list[NearbySegmentResponse], include_in_schema=False)
@app.get("/segments/nearby", response_model=list[NearbySegmentResponse])
def get_nearby_segments(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(LOCAL_RADIUS_M, ge=50, le=3000),
    limit: int = Query(20, ge=1, le=60),
) -> list[NearbySegmentResponse]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    WITH point AS (
                        SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
                    )
                    SELECT
                        {SEGMENT_COLUMNS},
                        ROUND(
                            ST_Distance(parking_segments.geometry::geography, point.geom::geography)
                        )::int AS distance_m
                    FROM parking_segments, point
                    WHERE ST_DWithin(
                        parking_segments.geometry::geography,
                        point.geom::geography,
                        :radius_m
                    )
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    ORDER BY distance_m, street_name, id
                    LIMIT :limit
                    """
                ),
                {
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "limit": limit,
                },
            ).mappings().all()
            adjustments = load_recent_segment_report_adjustments(connection)

        return [
            NearbySegmentResponse(
                **row_to_segment(row).model_dump(),
                distance_m=row["distance_m"],
                prediction=segment_prediction_from_row(row, adjustments.get(row["id"], 0)),
            )
            for row in rows
        ]

    except SQLAlchemyError as error:
        print(f"Unable to load nearby segments: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load nearby segments",
        ) from error


@app.get("/api/v1/road-network", response_model=RoadNetworkResponse, include_in_schema=False)
@app.get("/road-network", response_model=RoadNetworkResponse)
def get_road_network(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(ROAD_NETWORK_RADIUS_M, ge=100, le=2000),
) -> RoadNetworkResponse:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    WITH point AS (
                        SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
                    )
                    SELECT
                        road_edges.id,
                        road_edges.from_node_id,
                        road_edges.to_node_id,
                        road_edges.street_name,
                        road_edges.highway,
                        road_edges.one_way,
                        ROUND(road_edges.length_m)::int AS length_m,
                        ST_AsGeoJSON(road_edges.geometry)::json AS geometry
                    FROM road_edges, point
                    WHERE ST_DWithin(
                        road_edges.geometry::geography,
                        point.geom::geography,
                        :radius_m
                    )
                    ORDER BY ST_Distance(road_edges.geometry::geography, point.geom::geography), road_edges.id
                    LIMIT 700
                    """
                ),
                {"lat": lat, "lon": lon, "radius_m": radius_m},
            ).mappings().all()

        nodes: dict[str, RoadNodeResponse] = {}
        edges = []
        for row in rows:
            geometry = row["geometry"]
            coordinates = geometry.get("coordinates") or []
            if len(coordinates) >= 2:
                nodes.setdefault(
                    row["from_node_id"],
                    RoadNodeResponse(id=row["from_node_id"], location={"type": "Point", "coordinates": coordinates[0]}),
                )
                nodes.setdefault(
                    row["to_node_id"],
                    RoadNodeResponse(id=row["to_node_id"], location={"type": "Point", "coordinates": coordinates[-1]}),
                )
            edges.append(RoadEdgeResponse(**dict(row)))

        return RoadNetworkResponse(
            generated_at=iso_z(datetime.now(UTC)),
            radius_m=radius_m,
            nodes=list(nodes.values()),
            edges=edges,
        )

    except SQLAlchemyError as error:
        print(f"Unable to load road network: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load road network",
        ) from error


@app.get("/api/v1/segments/current", response_model=ParkingSegmentResponse, include_in_schema=False)
@app.get("/segments/current", response_model=ParkingSegmentResponse)
def get_current_segment(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> ParkingSegmentResponse:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    WITH point AS (
                        SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
                    )
                    SELECT
                        {SEGMENT_COLUMNS},
                        ST_Distance(parking_segments.geometry::geography, point.geom::geography) AS distance_m
                    FROM parking_segments, point
                    WHERE ST_DWithin(
                        parking_segments.geometry::geography,
                        point.geom::geography,
                        140
                    )
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    ORDER BY distance_m, street_name, id
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lon": lon},
            ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No segment near the specified coordinates",
            )

        return row_to_segment(row)

    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Unable to determine current segment: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to determine current segment",
        ) from error


@app.get("/api/v1/segments/{segment_id}", response_model=ParkingSegmentResponse, include_in_schema=False)
@app.get("/segments/{segment_id}", response_model=ParkingSegmentResponse)
def get_segment_by_id(segment_id: str) -> ParkingSegmentResponse:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT {SEGMENT_COLUMNS}
                    FROM parking_segments
                    WHERE id = :segment_id
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    """
                ),
                {"segment_id": segment_id},
            ).mappings().first()

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
        return row_to_segment(row)

    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Unable to load segment {segment_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load segment",
        ) from error


@app.get("/api/v1/segments/{segment_id}/prediction", response_model=PredictionResponse, include_in_schema=False)
@app.get("/segments/{segment_id}/prediction", response_model=PredictionResponse)
def get_segment_prediction(segment_id: str) -> PredictionResponse:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT {SEGMENT_COLUMNS}
                    FROM parking_segments
                    WHERE id = :segment_id
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    """
                ),
                {"segment_id": segment_id},
            ).mappings().first()
            adjustments = load_recent_segment_report_adjustments(connection)

        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

        return segment_prediction_from_row(row, adjustments.get(segment_id, 0))

    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Unable to load prediction for {segment_id}: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load segment prediction",
        ) from error


@app.get("/api/v1/segment-heatmap", response_model=SegmentHeatmapResponse, include_in_schema=False)
@app.get("/segment-heatmap", response_model=SegmentHeatmapResponse)
def get_segment_heatmap(
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat"),
    zoom: int = Query(15, ge=1, le=20),
) -> SegmentHeatmapResponse:
    cache_source = f"{SEGMENT_HEATMAP_CACHE_VERSION}:{bbox or 'all'}:{zoom}"
    cache_key = f"segment-heatmap:{hashlib.sha1(cache_source.encode()).hexdigest()}"
    cached = redis_json_get(cache_key)
    if isinstance(cached, dict):
        return SegmentHeatmapResponse(**cached)

    where_sql, params = parse_segment_bbox(bbox)
    now = datetime.now(UTC)

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        {SEGMENT_COLUMNS},
                        ST_AsGeoJSON(ST_LineInterpolatePoint(parking_segments.geometry, 0.5))::json AS midpoint
                    FROM parking_segments
                    {where_sql}
                    ORDER BY street_name, id
                    """
                ),
                params,
            ).mappings().all()
            adjustments = load_recent_segment_report_adjustments(connection)

        segments = []
        for row in rows:
            prediction = segment_prediction_from_row(row, adjustments.get(row["id"], 0))
            segment = row_to_segment(row)
            segments.append(
                SegmentHeatmapItemResponse(
                    segment_id=row["id"],
                    street_name=row["street_name"],
                    line=row["geometry"],
                    point=row["midpoint"],
                    parking_type=row["parking_type"],
                    parking_label=segment.parking_label,
                    parkability_percent=prediction.parkability_percent,
                    status=prediction.status,
                    heatmap_intensity=round(1 - prediction.parkability_score, 2),
                )
            )

        response = SegmentHeatmapResponse(
            generated_at=iso_z(now),
            expires_at=iso_z(now + timedelta(seconds=30)),
            segments=segments,
        )
        redis_json_set(cache_key, response.model_dump(), 30)
        return response

    except SQLAlchemyError as error:
        print(f"Unable to load segment heatmap: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load segment heatmap",
        ) from error


@app.post("/api/v1/segment-reports", response_model=ReportResponse, include_in_schema=False)
@app.post("/segment-reports", response_model=ReportResponse)
def create_segment_report(report: SegmentReportRequest) -> ReportResponse:
    if report.report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid report_type",
        )

    if report.session_id:
        rate_key = f"rate_limit:segment-report:{report.session_id}"
        try:
            if REDIS.get(rate_key):
                raise HTTPException(status_code=429, detail="Too many reports for this session")
            REDIS.setex(rate_key, 30, "1")
        except RedisError as error:
            print(f"Redis report rate limit failed: {error}")

    report_id = str(uuid4())

    try:
        with engine.begin() as connection:
            impacted = connection.execute(
                text(
                    f"""
                    WITH anchor AS (
                        SELECT geometry
                        FROM parking_segments
                        WHERE id = :segment_id
                          AND {ROAD_BACKED_SEGMENT_SQL}
                    )
                    SELECT
                        parking_segments.id,
                        GREATEST(
                            0.25,
                            1 - ST_Distance(
                                parking_segments.geometry::geography,
                                anchor.geometry::geography
                            ) / 150.0
                        )::numeric(4, 2) AS influence_weight
                    FROM parking_segments, anchor
                    WHERE ST_DWithin(
                        parking_segments.geometry::geography,
                        anchor.geometry::geography,
                        150
                    )
                      AND {ROAD_BACKED_SEGMENT_SQL}
                    ORDER BY influence_weight DESC
                    """
                ),
                {"segment_id": report.segment_id},
            ).mappings().all()

            if not impacted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

            for index, row in enumerate(impacted):
                connection.execute(
                    text(
                        """
                        INSERT INTO segment_reports (
                            id,
                            segment_id,
                            report_type,
                            session_id,
                            influence_weight,
                            source_report_id
                        )
                        VALUES (
                            :id,
                            :segment_id,
                            :report_type,
                            :session_id,
                            :influence_weight,
                            :source_report_id
                        )
                        """
                    ),
                    {
                        "id": report_id if index == 0 else str(uuid4()),
                        "segment_id": row["id"],
                        "report_type": report.report_type,
                        "session_id": report.session_id,
                        "influence_weight": row["influence_weight"],
                        "source_report_id": report_id,
                    },
                )

            invalidate_segment_cache()

        event = {
            "event_id": str(uuid4()),
            "event_type": "user.report.created",
            "source": "zone-service",
            "segment_id": report.segment_id,
            "timestamp": iso_z(datetime.now(UTC)),
            "payload": {
                "report_id": report_id,
                "report_type": report.report_type,
                "session_id": report.session_id,
                "affected_segments": [row["id"] for row in impacted],
            },
        }
        try:
            publish_event(event)
        except Exception as error:
            print(f"RabbitMQ report publish failed: {error}")
            store_raw_event(event)

        return ReportResponse(
            id=report_id,
            segment_id=report.segment_id,
            report_type=report.report_type,
            status="accepted",
        )

    except HTTPException:
        raise
    except SQLAlchemyError as error:
        print(f"Unable to save segment report: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save segment report",
        ) from error


@app.get("/api/v1/zones", response_model=list[ZoneResponse], include_in_schema=False)
@app.get("/zones", response_model=list[ZoneResponse])
def get_zones() -> list[ZoneResponse]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT {ZONE_COLUMNS}
                    FROM zones
                    ORDER BY name
                    """
                )
            ).mappings().all()

        return [row_to_zone(row) for row in rows]

    except SQLAlchemyError as error:
        print(f"Unable to load zones: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load zones",
        ) from error


@app.get("/api/v1/zones/nearby", response_model=list[NearbyZoneResponse], include_in_schema=False)
@app.get("/zones/nearby", response_model=list[NearbyZoneResponse])
def get_nearby_zones(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(1200, ge=100, le=5000),
    limit: int = Query(5, ge=1, le=20),
) -> list[NearbyZoneResponse]:
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    WITH point AS (
                        SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) AS geom
                    )
                    SELECT
                        {ZONE_COLUMNS},
                        ROUND(
                            ST_Distance(zones.polygon::geography, point.geom::geography)
                        )::int AS distance_m
                    FROM zones, point
                    WHERE ST_DWithin(
                        zones.polygon::geography,
                        point.geom::geography,
                        :radius_m
                    )
                    ORDER BY distance_m, name
                    LIMIT :limit
                    """
                ),
                {
                    "lat": lat,
                    "lon": lon,
                    "radius_m": radius_m,
                    "limit": limit,
                },
            ).mappings().all()
            adjustments = load_recent_report_adjustments(connection)

        return [
            NearbyZoneResponse(
                **dict(row),
                prediction=load_prediction(row["id"], adjustments.get(row["id"], 0)),
            )
            for row in rows
        ]

    except SQLAlchemyError as error:
        print(f"Unable to load nearby zones: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load nearby zones",
        ) from error


@app.get("/api/v1/zones/current", response_model=ZoneResponse, include_in_schema=False)
@app.get("/zones/current", response_model=ZoneResponse)
def get_current_zone(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> ZoneResponse:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT {ZONE_COLUMNS}
                    FROM zones
                    WHERE ST_Covers(
                        polygon,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    )
                    ORDER BY ST_Area(polygon) ASC
                    LIMIT 1
                    """
                ),
                {
                    "lat": lat,
                    "lon": lon,
                },
            ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No zone contains the specified coordinates",
            )

        return row_to_zone(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to determine current zone: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to determine current zone",
        ) from error


@app.get("/api/v1/zones/{zone_id}/prediction", response_model=PredictionResponse, include_in_schema=False)
@app.get("/zones/{zone_id}/prediction", response_model=PredictionResponse)
def get_zone_prediction(zone_id: str) -> PredictionResponse:
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM zones WHERE id = :zone_id)"),
                {"zone_id": zone_id},
            ).scalar_one()
            adjustments = load_recent_report_adjustments(connection)

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

        return load_prediction(zone_id, adjustments.get(zone_id, 0))

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to load prediction for {zone_id}: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load prediction",
        ) from error


@app.get("/api/v1/heatmap", response_model=HeatmapResponse, include_in_schema=False)
@app.get("/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat"),
    zoom: int = Query(14, ge=1, le=20),
) -> HeatmapResponse:
    cache_source = f"{bbox or 'all'}:{zoom}"
    cache_key = f"heatmap:{hashlib.sha1(cache_source.encode()).hexdigest()}"
    cached = redis_json_get(cache_key)
    if isinstance(cached, dict):
        return HeatmapResponse(**cached)

    where_sql, params = parse_bbox(bbox)
    now = datetime.now(UTC)

    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""
                    SELECT {ZONE_COLUMNS}
                    FROM zones
                    {where_sql}
                    ORDER BY name
                    """
                ),
                params,
            ).mappings().all()
            adjustments = load_recent_report_adjustments(connection)

        zones = []
        for row in rows:
            prediction = load_prediction(row["id"], adjustments.get(row["id"], 0))
            zones.append(
                HeatmapZoneResponse(
                    zone_id=row["id"],
                    name=row["name"],
                    polygon=row["geometry"],
                    parkability_percent=prediction.parkability_percent,
                    status=prediction.status,
                    heatmap_intensity=round(1 - prediction.parkability_score, 2),
                )
            )

        response = HeatmapResponse(
            generated_at=iso_z(now),
            expires_at=iso_z(now + timedelta(seconds=30)),
            zones=zones,
        )
        redis_json_set(cache_key, response.model_dump(), 30)
        return response

    except SQLAlchemyError as error:
        print(f"Unable to load heatmap: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load heatmap",
        ) from error


@app.post("/api/v1/reports", response_model=ReportResponse, include_in_schema=False)
@app.post("/reports", response_model=ReportResponse)
def create_report(report: ReportRequest) -> ReportResponse:
    if report.report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid report_type",
        )

    if report.session_id:
        rate_key = f"rate_limit:report:{report.session_id}"
        try:
            if REDIS.get(rate_key):
                raise HTTPException(status_code=429, detail="Too many reports for this session")
            REDIS.setex(rate_key, 30, "1")
        except RedisError as error:
            print(f"Redis report rate limit failed: {error}")

    report_id = str(uuid4())

    try:
        with engine.begin() as connection:
            exists = connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM zones WHERE id = :zone_id)"),
                {"zone_id": report.zone_id},
            ).scalar_one()

            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Zone not found",
                )

            connection.execute(
                text(
                    """
                    INSERT INTO user_reports (id, zone_id, report_type, session_id)
                    VALUES (:id, :zone_id, :report_type, :session_id)
                    """
                ),
                {
                    "id": report_id,
                    "zone_id": report.zone_id,
                    "report_type": report.report_type,
                    "session_id": report.session_id,
                },
            )

            invalidate_zone_cache(report.zone_id)

        event = {
            "event_id": str(uuid4()),
            "event_type": "user.report.created",
            "source": "zone-service",
            "zone_id": report.zone_id,
            "timestamp": iso_z(datetime.now(UTC)),
            "payload": {
                "report_id": report_id,
                "report_type": report.report_type,
                "session_id": report.session_id,
            },
        }
        try:
            publish_event(event)
        except Exception as error:
            print(f"RabbitMQ report publish failed: {error}")
            store_raw_event(event)

        return ReportResponse(
            id=report_id,
            segment_id=report.zone_id,
            report_type=report.report_type,
            status="accepted",
        )

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to save report: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save report",
        ) from error


@app.get("/api/v1/admin/source-health", include_in_schema=False)
@app.get("/admin/source-health")
def get_source_health() -> dict[str, Any]:
    database = "down"
    redis = "down"
    rabbitmq = "down"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "up"
    except SQLAlchemyError:
        pass

    try:
        REDIS.ping()
        redis = "up"
    except RedisError:
        pass

    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        connection.close()
        rabbitmq = "up"
    except Exception:
        pass

    return {
        "database": database,
        "redis": redis,
        "rabbitmq": rabbitmq,
        "last_event_at": LAST_EVENT_AT,
    }


@app.get("/api/v1/admin/events", include_in_schema=False)
@app.get("/admin/events")
def get_recent_events(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        events = REDIS.lrange("raw_events", 0, limit - 1)
    except RedisError as error:
        print(f"Redis raw event read failed: {error}")
        return []

    parsed = []
    for event in events:
        try:
            parsed.append(json.loads(event))
        except json.JSONDecodeError:
            continue
    return parsed


@app.post("/api/v1/admin/demo-scenarios/reset", include_in_schema=False)
@app.post("/admin/demo-scenarios/reset")
def reset_demo_scenarios() -> dict[str, str]:
    redis_delete_pattern("zone:signals:*")
    redis_delete_pattern("segment:signals:*")
    redis_delete_pattern("prediction:*")
    redis_delete_pattern("heatmap:*")
    redis_delete_pattern("segment-prediction:*")
    redis_delete_pattern("segment-heatmap:*")
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM segment_reports"))
            connection.execute(text("DELETE FROM user_reports"))
    except SQLAlchemyError as error:
        print(f"Demo report reset failed: {error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to reset demo reports",
        ) from error
    try:
        REDIS.delete("raw_events")
    except RedisError as error:
        print(f"Redis raw event reset failed: {error}")
    return {"status": "reset"}


@app.get("/api/v1/zones/{zone_id}", response_model=ZoneResponse, include_in_schema=False)
@app.get("/zones/{zone_id}", response_model=ZoneResponse)
def get_zone_by_id(zone_id: str) -> ZoneResponse:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    f"""
                    SELECT {ZONE_COLUMNS}
                    FROM zones
                    WHERE id = :zone_id
                    """
                ),
                {
                    "zone_id": zone_id,
                },
            ).mappings().first()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

        return row_to_zone(row)

    except HTTPException:
        raise

    except SQLAlchemyError as error:
        print(f"Unable to load zone {zone_id}: {error}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to load zone",
        ) from error
