import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pika
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://parcheggia:parcheggia@localhost:5672/%2F")
EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "parcheggia.events")
ZONE_SERVICE_URL = os.getenv("ZONE_SERVICE_URL", "http://localhost:8001/api/v1")
PREDICTION_SERVICE_URL = os.getenv("PREDICTION_SERVICE_URL", "http://localhost:8004/api/v1")

redis = Redis.from_url(REDIS_URL, decode_responses=True)
REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}

app = FastAPI(
    title="ParcheggIA Location Service",
    description="Live session, posizione utente e nearby segments.",
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
                "service": "location-service",
            }
        )
    )
    return response


class LocationUpdateRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class LiveSessionResponse(BaseModel):
    session_id: str
    status: str
    started_at: str
    ended_at: str | None = None


class LocationUpdateResponse(BaseModel):
    session_id: str
    status: str
    current_segment: dict[str, Any] | None
    prediction: dict[str, Any] | None
    nearby_segments: list[dict[str, Any]]


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_json(url: str) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise HTTPException(status_code=502, detail=f"Upstream error: {url}") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Upstream unavailable: {url}") from error


def save_session(session: dict[str, Any]) -> None:
    redis.setex(f"live_session:{session['session_id']}", 3600, json.dumps(session))


def load_session(session_id: str) -> dict[str, Any]:
    raw = redis.get(f"live_session:{session_id}")
    if raw is None:
        raise HTTPException(status_code=404, detail="Live session not found")
    return json.loads(raw)


def publish_location_event(session_id: str, location: LocationUpdateRequest, segment_id: str | None) -> None:
    event = {
        "event_id": str(uuid4()),
        "event_type": "user.location.updated",
        "source": "location-service",
        "session_id": session_id,
        "segment_id": segment_id,
        "timestamp": iso_now(),
        "payload": {
            "lat_bucket": round(location.lat, 3),
            "lon_bucket": round(location.lon, 3),
        },
    }
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


def session_response(session: dict[str, Any]) -> LiveSessionResponse:
    return LiveSessionResponse(
        session_id=session["session_id"],
        status=session["status"],
        started_at=session["started_at"],
        ended_at=session.get("ended_at"),
    )


@app.get("/api/v1/health", include_in_schema=False)
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "location-service"}


@app.get("/api/v1/ready", include_in_schema=False)
@app.get("/ready")
def readiness_check() -> dict[str, str]:
    try:
        redis.ping()
        get_json(f"{ZONE_SERVICE_URL}/ready")
        get_json(f"{PREDICTION_SERVICE_URL}/ready")
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        connection.close()
    except (RedisError, HTTPException) as error:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="RabbitMQ unavailable") from error
    return {"status": "ready", "redis": "up", "rabbitmq": "up"}


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
            f'{{service="location-service",method="{method}",path="{path}",status="{status_code}"}} {count}'
        )
    return "\n".join(lines) + "\n"


@app.post("/api/v1/live-sessions/start", response_model=LiveSessionResponse, include_in_schema=False)
@app.post("/live-sessions/start", response_model=LiveSessionResponse)
def start_live_session() -> LiveSessionResponse:
    session = {
        "session_id": str(uuid4()),
        "status": "active",
        "started_at": iso_now(),
        "ended_at": None,
        "last_lat": None,
        "last_lon": None,
    }
    save_session(session)
    return session_response(session)


@app.post("/api/v1/live-sessions/{session_id}/location", response_model=LocationUpdateResponse, include_in_schema=False)
@app.post("/live-sessions/{session_id}/location", response_model=LocationUpdateResponse)
def update_location(session_id: str, location: LocationUpdateRequest) -> LocationUpdateResponse:
    session = load_session(session_id)
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Live session is not active")

    query = f"lat={location.lat}&lon={location.lon}"
    current_segment = get_json(f"{ZONE_SERVICE_URL}/segments/current?{query}")
    nearby_segments = get_json(f"{ZONE_SERVICE_URL}/segments/nearby?{query}&radius_m=900&limit=20") or []
    prediction = None

    if current_segment:
        prediction = get_json(f"{PREDICTION_SERVICE_URL}/segments/{current_segment['id']}/prediction")

    session["last_lat"] = location.lat
    session["last_lon"] = location.lon
    save_session(session)
    publish_location_event(session_id, location, current_segment["id"] if current_segment else None)

    return LocationUpdateResponse(
        session_id=session_id,
        status=session["status"],
        current_segment=current_segment,
        prediction=prediction,
        nearby_segments=nearby_segments,
    )


@app.get("/api/v1/live-sessions/{session_id}/nearby-segments", include_in_schema=False)
@app.get("/live-sessions/{session_id}/nearby-segments")
def nearby_segments(session_id: str) -> list[dict[str, Any]]:
    session = load_session(session_id)
    if session["last_lat"] is None or session["last_lon"] is None:
        raise HTTPException(status_code=409, detail="Live session has no location yet")
    query = f"lat={session['last_lat']}&lon={session['last_lon']}"
    return get_json(f"{ZONE_SERVICE_URL}/segments/nearby?{query}&radius_m=900&limit=20") or []


@app.post("/api/v1/live-sessions/{session_id}/stop", response_model=LiveSessionResponse, include_in_schema=False)
@app.post("/live-sessions/{session_id}/stop", response_model=LiveSessionResponse)
def stop_live_session(session_id: str) -> LiveSessionResponse:
    session = load_session(session_id)
    session["status"] = "stopped"
    session["ended_at"] = iso_now()
    save_session(session)
    return session_response(session)
