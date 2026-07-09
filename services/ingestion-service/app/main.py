import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pika
import redis
from redis.exceptions import RedisError
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.tomtom import (
    TomTomError,
    budget_cap,
    cell_key,
    estimate_nearby,
    load_api_key,
    search_parking_pois,
)


RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL",
    "amqp://parcheggia:parcheggia@localhost:5672/%2F",
)
EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "parcheggia.events")
SCENARIOS_PATH = Path(
    os.getenv("SCENARIOS_PATH", "/app/data/synthetic/demo_scenarios.json")
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TOMTOM_BUDGET_FRACTION = float(os.getenv("TOMTOM_BUDGET_FRACTION", "0.05"))
TOMTOM_MONTHLY_LIMITS = {
    "traffic_flow": int(os.getenv("TOMTOM_MONTHLY_LIMIT_TRAFFIC_FLOW", "200000")),
    "traffic_incidents": int(os.getenv("TOMTOM_MONTHLY_LIMIT_TRAFFIC_INCIDENTS", "2500")),
    "search": int(os.getenv("TOMTOM_MONTHLY_LIMIT_SEARCH", "2500")),
    "routing": int(os.getenv("TOMTOM_MONTHLY_LIMIT_ROUTING", "20000")),
}
ESTIMATE_CACHE_TTL_SECONDS = int(os.getenv("TOMTOM_ESTIMATE_CACHE_TTL_SECONDS", "300"))
PARKING_POIS_CACHE_TTL_SECONDS = int(os.getenv("TOMTOM_PARKING_POIS_CACHE_TTL_SECONDS", "86400"))
REDIS = redis.Redis.from_url(REDIS_URL, decode_responses=True)
REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}

app = FastAPI(
    title="ParcheggIA Ingestion Service",
    description="Simulatore demo per eventi traffico, parcheggi ed eventi cittadini.",
    version="0.1.0",
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


class TomTomPublishRequest(BaseModel):
    lat: float
    lon: float
    segment_id: str | None = None
    zone_id: str | None = None
    radius_m: int = 500


def tomtom_status_code(error: TomTomError) -> int:
    return error.status_code if error.status_code in {400, 401, 403, 429, 503} else 502


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
                "service": "ingestion-service",
            }
        )
    )
    return response


def iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_scenarios() -> list[dict[str, Any]]:
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


def find_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Scenario not found",
    )


def build_events(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    timestamp = iso_now()

    for zone_id in scenario["affected_zones"]:
        base = {
            "source": "ingestion-service",
            "scenario_id": scenario["id"],
            "scenario_label": scenario["label"],
            "zone_id": zone_id,
            "timestamp": timestamp,
        }
        events.extend(
            [
                {
                    **base,
                    "event_id": str(uuid4()),
                    "event_type": "traffic.snapshot.received",
                    "payload": {
                        "traffic_pressure": scenario["traffic_pressure"],
                        "current_speed": round(40 * (1 - scenario["traffic_pressure"])),
                        "free_flow_speed": 40,
                        "confidence": 0.82,
                    },
                },
                {
                    **base,
                    "event_id": str(uuid4()),
                    "event_type": "parkinglot.availability.updated",
                    "payload": {
                        "parking_lot_availability": scenario["parking_lot_availability"],
                        "confidence": 0.76,
                    },
                },
                {
                    **base,
                    "event_id": str(uuid4()),
                    "event_type": "city.event.created",
                    "payload": {
                        "event_pressure": scenario["event_pressure"],
                        "expected_status": scenario["expected_status"],
                    },
                },
            ]
        )

    return events


def redis_json_get(key: str) -> dict[str, Any] | None:
    try:
        value = REDIS.get(key)
    except RedisError as error:
        raise TomTomError(503, f"Redis unavailable for TomTom cache: {error}") from error
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def redis_json_set(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        REDIS.setex(key, ttl_seconds, json.dumps(value))
    except RedisError as error:
        raise TomTomError(503, f"Redis unavailable for TomTom cache: {error}") from error


def tomtom_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def tomtom_budget_key(service: str) -> str:
    return f"tomtom:budget:{tomtom_month()}:{service}"


def tomtom_budget_guard(service: str) -> None:
    monthly_limit = TOMTOM_MONTHLY_LIMITS.get(service, 2500)
    limit = budget_cap(monthly_limit, TOMTOM_BUDGET_FRACTION)
    key = tomtom_budget_key(service)
    try:
        current = int(REDIS.get(key) or 0)
        if current >= limit:
            raise TomTomError(429, f"TomTom {service} test budget exceeded ({current}/{limit})")
        value = REDIS.incr(key)
        if value == 1:
            REDIS.expire(key, 45 * 24 * 60 * 60)
    except RedisError as error:
        raise TomTomError(503, f"Redis unavailable for TomTom budget guard: {error}") from error


def tomtom_budget_snapshot() -> dict[str, Any]:
    services = {}
    for service, monthly_limit in TOMTOM_MONTHLY_LIMITS.items():
        limit = budget_cap(monthly_limit, TOMTOM_BUDGET_FRACTION)
        try:
            used = int(REDIS.get(tomtom_budget_key(service)) or 0)
        except RedisError:
            used = -1
        services[service] = {
            "used": used,
            "test_limit": limit,
            "monthly_limit": monthly_limit,
        }
    return {
        "month": tomtom_month(),
        "budget_fraction": TOMTOM_BUDGET_FRACTION,
        "services": services,
    }


def cached_estimate_nearby(lat: float, lon: float, radius_m: int) -> dict[str, Any]:
    cache_key = f"tomtom:estimate:{cell_key(lat, lon)}:{radius_m}"
    cached = redis_json_get(cache_key)
    if cached:
        cached["cache_hit"] = True
        return cached

    estimate = estimate_nearby(load_api_key(), lat, lon, radius_m, tomtom_budget_guard)
    estimate["cache_hit"] = False
    redis_json_set(cache_key, estimate, ESTIMATE_CACHE_TTL_SECONDS)
    return estimate


def cached_parking_pois(lat: float, lon: float, radius_m: int, limit: int) -> dict[str, Any]:
    cache_key = f"tomtom:parking-pois:{cell_key(lat, lon)}:{radius_m}:{limit}"
    cached = redis_json_get(cache_key)
    if cached:
        cached["cache_hit"] = True
        return cached

    result = search_parking_pois(load_api_key(), lat, lon, radius_m, limit, tomtom_budget_guard)
    result["cache_hit"] = False
    redis_json_set(cache_key, result, PARKING_POIS_CACHE_TTL_SECONDS)
    return result


def build_tomtom_events(
    estimate: dict[str, Any],
    target_id: str | None = None,
    target_field: str = "segment_id",
) -> list[dict[str, Any]]:
    timestamp = iso_now()
    base = {
        "source": "tomtom",
        "timestamp": timestamp,
        "lat": estimate["lat"],
        "lon": estimate["lon"],
        "radius_m": estimate["radius_m"],
    }
    if target_id:
        base[target_field] = target_id
    events = [
        {
            **base,
            "event_id": str(uuid4()),
            "event_type": "traffic.snapshot.received",
            "payload": {
                "traffic_pressure": estimate["traffic_pressure"],
                "current_speed": estimate["current_speed"],
                "free_flow_speed": estimate["free_flow_speed"],
                "confidence": estimate["confidence"],
                "radius_m": estimate["radius_m"],
                "sample_count": len(estimate["flow_samples"]),
                "provider": "tomtom",
            },
        }
    ]
    if estimate["event_pressure"] > 0:
        events.append(
            {
                **base,
                "event_id": str(uuid4()),
                "event_type": "city.event.created",
                "payload": {
                    "event_pressure": estimate["event_pressure"],
                    "incidents_count": estimate["incidents_count"],
                    "incidents_sample": estimate["incidents_sample"],
                    "expected_status": "real_time_traffic",
                },
            }
        )
    return events


def publish_events(events: list[dict[str, Any]]) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="fanout",
            durable=True,
        )

        for event in events:
            channel.basic_publish(
                exchange=EVENT_EXCHANGE,
                routing_key="",
                body=json.dumps(event).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
    finally:
        connection.close()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "ingestion-service"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        connection.close()
        REDIS.ping()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ or Redis is not available",
        ) from error

    return {"status": "ready", "rabbitmq": "up", "redis": "up"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = [
        "# HELP parcheggia_http_requests_total HTTP requests by method, path and status.",
        "# TYPE parcheggia_http_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(REQUEST_COUNTS.items()):
        lines.append(
            "parcheggia_http_requests_total"
            f'{{service="ingestion-service",method="{method}",path="{path}",status="{status_code}"}} {count}'
        )
    for service, values in tomtom_budget_snapshot()["services"].items():
        if values["used"] >= 0:
            lines.append(
                f'parcheggia_tomtom_requests_month_total{{service="{service}"}} {values["used"]}'
            )
            lines.append(
                f'parcheggia_tomtom_test_budget_limit{{service="{service}"}} {values["test_limit"]}'
            )
    return "\n".join(lines) + "\n"


@app.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    return load_scenarios()


@app.get("/traffic/tomtom/probe")
def probe_tomtom_traffic(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(500, ge=100, le=3000),
) -> dict[str, Any]:
    try:
        return cached_estimate_nearby(lat, lon, radius_m)
    except TomTomError as error:
        raise HTTPException(
            status_code=tomtom_status_code(error),
            detail={"provider": "tomtom", "status_code": error.status_code, "message": error.message},
        ) from error


@app.post("/traffic/tomtom/publish")
def publish_tomtom_traffic(request: TomTomPublishRequest) -> dict[str, Any]:
    target_id = request.segment_id or request.zone_id
    target_field = "segment_id" if request.segment_id else "zone_id"

    try:
        estimate = cached_estimate_nearby(request.lat, request.lon, request.radius_m)
        events = build_tomtom_events(estimate, target_id, target_field)
        publish_events(events)
    except TomTomError as error:
        raise HTTPException(
            status_code=tomtom_status_code(error),
            detail={"provider": "tomtom", "status_code": error.status_code, "message": error.message},
        ) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Unable to publish TomTom events") from error

    return {
        "status": "published",
        "target_field": target_field if target_id else "nearby_segments",
        "target_id": target_id,
        "events_published": len(events),
        "estimate": estimate,
    }


@app.get("/api/v1/tomtom/parking-pois")
@app.get("/tomtom/parking-pois")
def get_tomtom_parking_pois(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(500, ge=100, le=3000),
    limit: int = Query(10, ge=1, le=20),
) -> dict[str, Any]:
    try:
        return cached_parking_pois(lat, lon, radius_m, limit)
    except TomTomError as error:
        raise HTTPException(
            status_code=tomtom_status_code(error),
            detail={"provider": "tomtom", "status_code": error.status_code, "message": error.message},
        ) from error


@app.get("/traffic/tomtom/budget")
def get_tomtom_budget() -> dict[str, Any]:
    return tomtom_budget_snapshot()


@app.post("/scenarios/{scenario_id}/start")
def start_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = find_scenario(scenario_id)
    events = build_events(scenario)

    try:
        publish_events(events)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to publish scenario events",
        ) from error

    return {
        "status": "published",
        "scenario_id": scenario_id,
        "label": scenario["label"],
        "events_published": len(events),
    }
