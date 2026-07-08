import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

import pika
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from redis import Redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://parcheggia:parcheggia@localhost:5672/%2F")
EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "parcheggia.events")
ZONE_SERVICE_URL = os.getenv("ZONE_SERVICE_URL", "http://localhost:8001/api/v1")

redis = Redis.from_url(REDIS_URL, decode_responses=True)
REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}

app = FastAPI(
    title="ParcheggIA Admin Service",
    description="Dashboard admin, source health e controllo demo.",
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
                "service": "admin-service",
            }
        )
    )
    return response


def get_json(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise HTTPException(status_code=502, detail=f"Upstream error: {url}") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Upstream unavailable: {url}") from error


def rabbitmq_check() -> None:
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=EVENT_EXCHANGE, exchange_type="fanout", durable=True)
    finally:
        connection.close()


def delete_pattern(pattern: str) -> None:
    keys = list(redis.scan_iter(pattern))
    if keys:
        redis.delete(*keys)


@app.get("/api/v1/health", include_in_schema=False)
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "admin-service"}


@app.get("/api/v1/ready", include_in_schema=False)
@app.get("/ready")
def readiness_check() -> dict[str, str]:
    try:
        redis.ping()
        rabbitmq_check()
        get_json(f"{ZONE_SERVICE_URL}/ready")
    except (RedisError, HTTPException) as error:
        raise HTTPException(status_code=503, detail="Dependency unavailable") from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="RabbitMQ unavailable") from error
    return {"status": "ready", "redis": "up", "rabbitmq": "up", "zone_service": "up"}


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
            f'{{service="admin-service",method="{method}",path="{path}",status="{status_code}"}} {count}'
        )
    return "\n".join(lines) + "\n"


@app.get("/api/v1/admin/source-health", include_in_schema=False)
@app.get("/admin/source-health")
def get_source_health() -> dict[str, Any]:
    database = "down"
    zone_service = "down"
    redis_status = "down"
    rabbitmq = "down"
    last_event_at = None

    try:
        zone_ready = get_json(f"{ZONE_SERVICE_URL}/ready") or {}
        zone_service = "up"
        database = str(zone_ready.get("database", "up"))
    except HTTPException:
        pass

    try:
        redis.ping()
        redis_status = "up"
        events = redis.lrange("raw_events", 0, 0)
        if events:
            last_event_at = json.loads(events[0]).get("timestamp")
    except (RedisError, json.JSONDecodeError):
        pass

    try:
        rabbitmq_check()
        rabbitmq = "up"
    except Exception:
        pass

    return {
        "database": database,
        "zone_service": zone_service,
        "redis": redis_status,
        "rabbitmq": rabbitmq,
        "last_event_at": last_event_at,
    }


@app.get("/api/v1/admin/events", include_in_schema=False)
@app.get("/admin/events")
def get_recent_events(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        events = redis.lrange("raw_events", 0, limit - 1)
    except RedisError:
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
    try:
        delete_pattern("zone:signals:*")
        delete_pattern("segment:signals:*")
        delete_pattern("prediction:*")
        delete_pattern("heatmap:*")
        delete_pattern("segment-prediction:*")
        delete_pattern("segment-heatmap:*")
        redis.delete("raw_events")
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Redis unavailable") from error
    request = urllib.request.Request(
        f"{ZONE_SERVICE_URL}/admin/demo-scenarios/reset",
        data=b"",
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5):
            pass
    except Exception as error:
        raise HTTPException(status_code=502, detail="Unable to reset zone-service demo state") from error
    return {"status": "reset"}
