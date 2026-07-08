import json
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}


class ExplainRequest(BaseModel):
    segment_id: str | None = None
    segment_name: str | None = None
    zone_id: str | None = None
    zone_name: str | None = None
    parkability_percent: int = Field(..., ge=0, le=100)
    status: str
    trend: str
    confidence: float = Field(..., ge=0, le=1)
    estimated_search_time_min: int = Field(..., ge=0, le=120)
    recommendation: str
    context: dict[str, Any] = Field(default_factory=dict)


class ExplainResponse(BaseModel):
    model: str
    explanation: str
    action: str
    caveat: str


app = FastAPI(
    title="ParcheggIA Nemotron Service",
    description="Spiegazioni AI/fallback per la demo ParcheggIA.",
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
                "service": "nemotron-service",
            }
        )
    )
    return response


def status_label(status: str) -> str:
    return {
        "very_difficult": "molto difficile",
        "difficult": "difficile",
        "uncertain": "incerta",
        "good": "buona",
        "favorable": "favorevole",
    }.get(status, status)


def action_for_status(request: ExplainRequest) -> str:
    if request.parkability_percent < 25:
        return "Evita la zona se puoi e prova una laterale o una zona vicina con score piu alto."
    if request.parkability_percent < 50:
        return "Entraci solo se hai margine: controlla prima le alternative vicine."
    if request.parkability_percent < 75:
        return "Puoi provarci, restando pronto a spostarti se il traffico peggiora."
    return "Zona consigliata: mantieni il radar attivo e cerca sulle strade meno trafficate."


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "nemotron-service"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    return {"status": "ready", "mode": "rule-based-fallback"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = [
        "# HELP parcheggia_http_requests_total HTTP requests by method, path and status.",
        "# TYPE parcheggia_http_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(REQUEST_COUNTS.items()):
        lines.append(
            "parcheggia_http_requests_total"
            f'{{service="nemotron-service",method="{method}",path="{path}",status="{status_code}"}} {count}'
        )
    return "\n".join(lines) + "\n"


@app.post("/ai/explain", response_model=ExplainResponse)
@app.post("/explain", response_model=ExplainResponse)
def explain(request: ExplainRequest) -> ExplainResponse:
    trend_text = {
        "better": "in miglioramento",
        "worse": "in peggioramento",
        "stable": "stabile",
    }.get(request.trend, request.trend)

    explanation = (
        f"{request.segment_name or request.zone_name or 'Il tratto selezionato'} risulta {status_label(request.status)}: "
        f"score {request.parkability_percent}%, trend {trend_text}, "
        f"ricerca stimata {request.estimated_search_time_min} minuti."
    )

    caveat = (
        f"Confidenza {round(request.confidence * 100)}%. "
        "La spiegazione usa solo i segnali forniti dalla demo e non inventa dati esterni."
    )

    return ExplainResponse(
        model="rule-based-fallback",
        explanation=explanation,
        action=action_for_status(request),
        caveat=caveat,
    )
