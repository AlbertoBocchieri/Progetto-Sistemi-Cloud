import hashlib
import json
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.scoring import report_adjustment, signal_delta, status_from_percent


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://parcheggia:parcheggia@localhost:5432/parcheggia",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
redis = Redis.from_url(REDIS_URL, decode_responses=True)
REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}
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
SEGMENT_HEATMAP_CACHE_VERSION = "road-backed-ct-osm-v1"

app = FastAPI(
    title="ParcheggIA Prediction Service",
    description="Calcolo parkability, heatmap e cache Redis.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_requests(request: Request, call_next: Any) -> Any:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    key = (request.method, request.url.path, response.status_code)
    REQUEST_COUNTS[key] = REQUEST_COUNTS.get(key, 0) + 1
    print(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "service": "prediction-service",
            }
        )
    )
    return response


class PredictionRequest(BaseModel):
    segment_id: str


class PredictionResponse(BaseModel):
    prediction_id: str | None = None
    segment_id: str
    parkability_score: float
    parkability_percent: int
    status: str
    trend: str
    confidence: float
    estimated_search_time_min: int
    recommendation: str
    parking_type: str | None = None
    parking_label: str | None = None


class SegmentHeatmapItemResponse(BaseModel):
    segment_id: str
    street_name: str
    line: dict[str, Any]
    point: dict[str, Any]
    parking_type: str
    parking_label: str
    parkability_percent: int
    status: str
    heatmap_intensity: float


class SegmentHeatmapResponse(BaseModel):
    generated_at: str
    expires_at: str
    segments: list[SegmentHeatmapItemResponse]


SEGMENT_BASELINES = {
    "blue": (42, 0.70, 16, "Strisce blu: buona rotazione, controlla tariffa e orari sul posto."),
    "probable_free": (48, 0.52, 18, "Probabile libero: stima inferita, verifica sempre la segnaletica."),
    "restricted": (14, 0.66, 30, "Sosta probabilmente regolata o limitata: cerca alternative vicine."),
    "unknown": (42, 0.42, 22, "Dati limitati: usa la stima come indicazione e verifica sul posto."),
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


def demo_segment_percent(segment_id: str, fallback: int) -> int:
    road_id = segment_id.rsplit("-", 1)[0]
    return DEMO_SEGMENT_PERCENTS.get(road_id, fallback)


def iso_z(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def redis_json_get(key: str) -> dict[str, Any] | None:
    try:
        value = redis.get(key)
    except RedisError as error:
        print(f"Redis get failed for {key}: {error}")
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def redis_json_set(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        redis.setex(key, ttl_seconds, json.dumps(value))
    except RedisError as error:
        print(f"Redis set failed for {key}: {error}")


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


def load_report_delta(segment_id: str) -> int:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'found_spot'), 0) AS found_spot,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'full_zone'), 0) AS full_zone,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'released_spot'), 0) AS released_spot,
                    COALESCE(SUM(influence_weight) FILTER (WHERE report_type = 'parking_closed'), 0) AS parking_closed
                FROM segment_reports
                WHERE segment_id = :segment_id
                  AND created_at >= NOW() - INTERVAL '30 minutes'
                """
            ),
            {"segment_id": segment_id},
        ).mappings().one()
    return report_adjustment(
        row["found_spot"],
        row["full_zone"],
        row["released_spot"],
        row["parking_closed"],
    )


def load_segment_signals(segment_id: str) -> dict[str, Any]:
    try:
        return dict(redis.hgetall(f"segment:signals:{segment_id}"))
    except RedisError as error:
        print(f"Redis signals load failed for {segment_id}: {error}")
        return {}


def load_segment(segment_id: str) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT
                    id,
                    street_name,
                    parking_type,
                    tariff_zone,
                    source_confidence::float AS source_confidence
                FROM parking_segments
                WHERE id = :segment_id
                  AND {ROAD_BACKED_SEGMENT_SQL}
                """
            ),
            {"segment_id": segment_id},
        ).mappings().first()
    return dict(row) if row else None


def time_adjustment() -> int:
    now = datetime.now()
    if now.weekday() >= 5:
        return 3
    if 8 <= now.hour <= 10 or 17 <= now.hour <= 20:
        return -7
    if 0 <= now.hour <= 6:
        return 6
    return 0


def build_prediction(segment_id: str) -> PredictionResponse:
    segment = load_segment(segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    report_delta = load_report_delta(segment_id)
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
    if cached:
        return PredictionResponse(**cached)

    base_percent, base_confidence, base_time, base_recommendation = SEGMENT_BASELINES.get(
        segment["parking_type"],
        SEGMENT_BASELINES["unknown"],
    )
    base_percent = demo_segment_percent(segment["id"], base_percent)
    total_delta = report_delta + signal_delta(signals) + time_adjustment()
    percent = max(5, min(95, base_percent + total_delta))
    search_time = max(3, min(35, base_time - round(total_delta / 3)))
    trend = "stable"
    confidence = min(0.92, base_confidence + float(segment["source_confidence"]) * 0.12)
    recommendation = f"{segment['street_name']}: {base_recommendation}"

    if total_delta <= -6:
        trend = "worse"
        confidence = min(0.90, confidence + 0.08)
    elif total_delta >= 6:
        trend = "better"
        confidence = min(0.90, confidence + 0.08)

    if signals.get("scenario_label"):
        recommendation = f"{segment['street_name']}: scenario demo attivo, {signals['scenario_label']}."

    prediction = PredictionResponse(
        prediction_id=str(uuid4()),
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


def parse_bbox(bbox: str | None) -> tuple[str, dict[str, float]]:
    if bbox is None:
        return f"WHERE {ROAD_BACKED_SEGMENT_SQL}", {}

    try:
        min_lon, min_lat, max_lon, max_lat = [float(part) for part in bbox.split(",")]
    except ValueError as error:
        raise HTTPException(status_code=400, detail="bbox must be minLon,minLat,maxLon,maxLat") from error

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="bbox min values must be smaller than max values")

    return (
        f"""
        WHERE {ROAD_BACKED_SEGMENT_SQL}
          AND ST_Intersects(
            parking_segments.geometry,
            ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)
        )
        """,
        {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat},
    )


@app.get("/api/v1/health", include_in_schema=False)
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "prediction-service"}


@app.get("/api/v1/ready", include_in_schema=False)
@app.get("/ready")
def readiness_check() -> dict[str, str]:
    try:
        redis.ping()
        with engine.connect() as connection:
            connection.execute(text("SELECT COUNT(*) FROM parking_segments"))
    except (RedisError, SQLAlchemyError) as error:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from error
    return {"status": "ready", "database": "up", "redis": "up"}


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
            f'{{service="prediction-service",method="{method}",path="{path}",status="{status_code}"}} {count}'
        )
    return "\n".join(lines) + "\n"


@app.post("/api/v1/predictions", response_model=PredictionResponse, include_in_schema=False)
@app.post("/predictions", response_model=PredictionResponse)
def create_prediction(request: PredictionRequest) -> PredictionResponse:
    prediction = build_prediction(request.segment_id)
    redis_json_set(f"prediction:id:{prediction.prediction_id}", prediction.model_dump(), 300)
    return prediction


@app.get("/api/v1/predictions/{prediction_id}", response_model=PredictionResponse, include_in_schema=False)
@app.get("/predictions/{prediction_id}", response_model=PredictionResponse)
def get_prediction_by_id(prediction_id: str) -> PredictionResponse:
    cached = redis_json_get(f"prediction:id:{prediction_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return PredictionResponse(**cached)


@app.get("/api/v1/segments/{segment_id}/prediction", response_model=PredictionResponse, include_in_schema=False)
@app.get("/segments/{segment_id}/prediction", response_model=PredictionResponse)
def get_segment_prediction(segment_id: str) -> PredictionResponse:
    prediction = build_prediction(segment_id)
    redis_json_set(f"prediction:id:{prediction.prediction_id}", prediction.model_dump(), 300)
    return prediction


@app.get("/api/v1/zones/{zone_id}/prediction", response_model=PredictionResponse, include_in_schema=False)
@app.get("/zones/{zone_id}/prediction", response_model=PredictionResponse)
def get_zone_prediction(zone_id: str) -> PredictionResponse:
    with engine.connect() as connection:
        segment_id = connection.execute(
            text(
                """
                SELECT parking_segments.id
                FROM parking_segments
                JOIN zones ON ST_Intersects(parking_segments.geometry, zones.polygon)
                WHERE zones.id = :zone_id
                ORDER BY parking_segments.id
                LIMIT 1
                """
            ),
            {"zone_id": zone_id},
        ).scalar_one_or_none()
    if segment_id is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    return get_segment_prediction(segment_id)


@app.get("/api/v1/segment-heatmap", response_model=SegmentHeatmapResponse, include_in_schema=False)
@app.get("/segment-heatmap", response_model=SegmentHeatmapResponse)
def get_segment_heatmap(
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat"),
    zoom: int = Query(15, ge=1, le=20),
) -> SegmentHeatmapResponse:
    cache_source = f"{SEGMENT_HEATMAP_CACHE_VERSION}:{bbox or 'all'}:{zoom}"
    cache_key = f"segment-heatmap:{hashlib.sha1(cache_source.encode()).hexdigest()}"
    cached = redis_json_get(cache_key)
    if cached:
        return SegmentHeatmapResponse(**cached)

    where_sql, params = parse_bbox(bbox)
    now = datetime.now(UTC)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                SELECT
                    id,
                    street_name,
                    parking_type,
                    tariff_zone,
                    source_confidence::float AS source_confidence,
                    ST_AsGeoJSON(geometry)::json AS geometry,
                    ST_AsGeoJSON(ST_LineInterpolatePoint(geometry, 0.5))::json AS midpoint
                FROM parking_segments
                {where_sql}
                ORDER BY street_name, id
                """
            ),
            params,
        ).mappings().all()

    segments = []
    for row in rows:
        prediction = build_prediction(row["id"])
        segment = dict(row)
        segments.append(
            SegmentHeatmapItemResponse(
                segment_id=row["id"],
                street_name=row["street_name"],
                line=row["geometry"],
                point=row["midpoint"],
                parking_type=row["parking_type"],
                parking_label=parking_label(segment),
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


@app.get("/api/v1/heatmap", response_model=SegmentHeatmapResponse, include_in_schema=False)
@app.get("/heatmap", response_model=SegmentHeatmapResponse)
def get_heatmap(
    bbox: str | None = Query(None, description="minLon,minLat,maxLon,maxLat"),
    zoom: int = Query(15, ge=1, le=20),
) -> SegmentHeatmapResponse:
    return get_segment_heatmap(bbox, zoom)
