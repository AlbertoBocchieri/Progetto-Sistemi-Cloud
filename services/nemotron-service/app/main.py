import json
import hashlib
import os
import re
import time
from typing import Any
from urllib import error, request as urlrequest
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field


REQUEST_COUNTS: dict[tuple[str, str, int], int] = {}
EXPLAIN_CACHE: dict[str, tuple[float, "ExplainResponse"]] = {}
TTS_CACHE: dict[str, bytes] = {}
NEMOTRON_API_KEY = os.getenv("NEMOTRON_API_KEY", "").strip()
NEMOTRON_BASE_URL = os.getenv("NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
NEMOTRON_MODEL = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
NEMOTRON_TIMEOUT_SECONDS = float(os.getenv("NEMOTRON_TIMEOUT_SECONDS", "45"))
NEMOTRON_CACHE_TTL_SECONDS = int(os.getenv("NEMOTRON_CACHE_TTL_SECONDS", "600"))
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_BASE_URL = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1").rstrip("/")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_22050_32")
ELEVENLABS_TIMEOUT_SECONDS = float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "20"))
ELEVENLABS_SIMILARITY_BOOST = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.50"))
ELEVENLABS_STYLE_EXAGGERATION = float(os.getenv("ELEVENLABS_STYLE_EXAGGERATION", "0.25"))


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
    summary: str | None = None
    reason: str | None = None
    risk: str | None = None
    target_segment_ids: list[str] = Field(default_factory=list)
    target_parking_poi_ids: list[str] = Field(default_factory=list)
    cached: bool = False


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=700)


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


def clean_italian(text: Any) -> str:
    value = str(text or "")
    replacements = {
        "parkability": "possibilita di parcheggio",
        "score": "percentuale",
        "trend": "andamento",
        "confidence": "affidabilita",
        "status": "stato",
        "parking": "parcheggio",
    }
    for source, target in replacements.items():
        value = value.replace(source, target).replace(source.capitalize(), target.capitalize())
    return value


def clean_driver_language(text: Any) -> str:
    value = clean_italian(text)
    value = re.sub(r"\bstima\s+inferita[:,]?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bdati?\s+inferit[ioae]\b", "indicazioni disponibili", value, flags=re.IGNORECASE)
    replacements = {
        "dato inferito": "indicazione disponibile",
        "dati inferiti": "indicazioni disponibili",
        "inferita": "",
        "inferito": "",
        "heatmap": "zona",
        "Heatmap": "Zona",
        "segmento": "tratto",
        "segmenti": "tratti",
        "target": "punto",
        "Confidence": "sicurezza",
        "confidence": "sicurezza",
        "affidabilita": "sicurezza",
        "trend": "andamento",
        "verifica segnaletica": "controlla i cartelli",
        "Verifica segnaletica": "Controlla i cartelli",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    value = re.sub(r":\s*[,.;]\s*", ": ", value)
    value = re.sub(r"[:,]\s*[.;]", ".", value)
    value = re.sub(r"\s{2,}", " ", value)
    return value.strip(" ,:")


def clean_parking_place(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    kept = [
        part for part in parts
        if not re.match(r"^\d{5}\b", part)
        and not re.fullmatch(r"Catania(?:\s+CT)?|CT|Italia|Italy", part, flags=re.IGNORECASE)
    ]
    cleaned = ", ".join(kept) if parts else text
    cleaned = re.sub(r"(?:,\s*)?\b\d{5}\s+Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:,\s*)?Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:,\s*)?(?:Italia|Italy)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.-")


def nearby_candidates(request: ExplainRequest) -> list[dict[str, Any]]:
    nearby = request.context.get("nearby_segments") if isinstance(request.context, dict) else None
    current_name = (request.segment_name or request.zone_name or "").casefold()
    candidates: list[dict[str, Any]] = []
    seen_streets: set[str] = set()
    if isinstance(nearby, list):
        for item in nearby:
            if not isinstance(item, dict) or not isinstance(item.get("parkability_percent"), int):
                continue
            street = str(item.get("street_name") or "").strip()
            street_key = street.casefold()
            if not street or street_key == current_name or street_key in seen_streets:
                continue
            if item["parkability_percent"] <= request.parkability_percent:
                continue
            seen_streets.add(street_key)
            candidates.append(item)
    candidates.sort(key=lambda item: item["parkability_percent"], reverse=True)
    return candidates[:2]


def nearest_parking_name(request: ExplainRequest) -> str:
    pois = request.context.get("parking_pois") if isinstance(request.context, dict) else None
    if isinstance(pois, list) and pois and isinstance(pois[0], dict):
        poi = pois[0]
        place = clean_parking_place(poi.get("address") or poi.get("name"))
        place = re.sub(r"\s+(parking|parcheggio|garage)\s*$", "", place, flags=re.IGNORECASE).strip(" ,.-")
        return f"parcheggio in {place}" if place else "parcheggio piu vicino"
    return "il parcheggio piu vicino"


def action_for_status(request: ExplainRequest) -> str:
    candidates = nearby_candidates(request)
    parking = nearest_parking_name(request)
    strong_candidates = [
        candidate for candidate in candidates
        if candidate["parkability_percent"] >= request.parkability_percent + 8
    ]
    if len(strong_candidates) >= 2:
        first, second = strong_candidates[0], strong_candidates[1]
        return f"Prova {first['street_name']} ({first['parkability_percent']}%) o {second['street_name']} ({second['parkability_percent']}%)."
    if len(strong_candidates) == 1:
        first = strong_candidates[0]
        if request.parkability_percent < 35:
            return f"Prova {first['street_name']} ({first['parkability_percent']}%) o {parking}."
        return f"Prova {first['street_name']} ({first['parkability_percent']}%)."
    if request.parkability_percent < 35:
        return f"Prova {parking}."
    if len(candidates) == 1:
        first = candidates[0]
        return f"Prova {first['street_name']} ({first['parkability_percent']}%)."

    if request.parkability_percent < 25:
        return f"Qui la stima e' {request.parkability_percent}%. Prova una laterale migliore."
    if request.parkability_percent < 50:
        return f"Qui la stima e' {request.parkability_percent}%. Prova una laterale vicina prima di fermarti."
    if request.parkability_percent < 75:
        return f"Puoi provarci qui ({request.parkability_percent}%), poi passa a una laterale se non trovi posto."
    return f"Resta su questo tratto ({request.parkability_percent}%): controlla strisce e segnaletica."


def risk_for_status(request: ExplainRequest) -> str:
    if request.confidence < 0.55:
        return "Affidabilita bassa."
    if request.parkability_percent < 40:
        return "Rischio alto di giro a vuoto."
    if request.parkability_percent < 70:
        return "Rischio medio."
    return "Rischio contenuto."


def fallback_target_ids(request: ExplainRequest) -> tuple[list[str], list[str]]:
    segment_ids: list[str] = []
    for candidate in nearby_candidates(request):
        candidate_id = str(candidate.get("id") or "")
        if candidate_id and candidate["parkability_percent"] >= request.parkability_percent + 8:
            segment_ids.append(candidate_id)
    pois = request.context.get("parking_pois") if isinstance(request.context, dict) else None
    poi_ids = [
        str(item.get("id"))
        for item in (pois or [])[:1]
        if isinstance(item, dict) and item.get("id") and (request.parkability_percent < 35 or not segment_ids)
    ]
    if not segment_ids and request.segment_id and request.parkability_percent >= 50:
        segment_ids.append(request.segment_id)
    return segment_ids[:2], poi_ids


def fallback_explanation(request: ExplainRequest, cached: bool = False) -> ExplainResponse:
    trend_text = {
        "better": "in miglioramento",
        "worse": "in peggioramento",
        "stable": "stabile",
    }.get(request.trend, request.trend)
    name = request.segment_name or request.zone_name or "Il tratto selezionato"
    current = request.context.get("current_segment") if isinstance(request.context, dict) else {}
    current_label = current.get("parking_label") if isinstance(current, dict) else None
    explanation = (
        f"{name} risulta {status_label(request.status)}: "
        f"percentuale {request.parkability_percent}%, andamento {trend_text}, "
        f"ricerca stimata {request.estimated_search_time_min} minuti"
        f"{f', {current_label}' if current_label else ''}."
    )
    caveat = (
        f"Affidabilita {round(request.confidence * 100)}%. "
        "Suggerimento basato sui dati locali disponibili."
    )
    target_segment_ids, target_parking_poi_ids = fallback_target_ids(request)
    return ExplainResponse(
        model="simulated-fallback" if not NEMOTRON_API_KEY else "rule-based-fallback",
        summary=f"{name}: {request.parkability_percent}% di probabilita stimata.",
        explanation=explanation,
        action=action_for_status(request),
        reason=f"Confronto percentuale, tipo sosta e alternative vicine.",
        risk=risk_for_status(request),
        caveat=caveat,
        target_segment_ids=target_segment_ids,
        target_parking_poi_ids=target_parking_poi_ids,
        cached=cached,
    )


def compact_context(request: ExplainRequest) -> dict[str, Any]:
    context = request.context if isinstance(request.context, dict) else {}
    current = context.get("current_segment") if isinstance(context.get("current_segment"), dict) else {}
    nearby = context.get("nearby_segments") if isinstance(context.get("nearby_segments"), list) else []
    heatmap = context.get("heatmap_segments") if isinstance(context.get("heatmap_segments"), list) else []
    pois = context.get("parking_pois") if isinstance(context.get("parking_pois"), list) else []
    current_point = context.get("current_point") if isinstance(context.get("current_point"), dict) else {}

    def segment_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "street_name": item.get("street_name"),
            "distance_m": item.get("distance_m"),
            "parking_type": item.get("parking_type"),
            "parking_label": item.get("parking_label"),
            "price_label": item.get("price_label"),
            "time_rules": item.get("time_rules"),
            "parkability_percent": item.get("parkability_percent"),
            "status": item.get("status"),
            "confidence": item.get("confidence"),
            "trend": item.get("trend"),
            "estimated_search_time_min": item.get("estimated_search_time_min"),
            "recommendation": item.get("recommendation"),
        }

    return {
        "current_point": {
            "lat": current_point.get("lat"),
            "lon": current_point.get("lon"),
            "heading_degrees": current_point.get("heading_degrees"),
            "local_radius_m": current_point.get("local_radius_m"),
        },
        "current_segment": {
            "id": current.get("id"),
            "street_name": current.get("street_name"),
            "parkability_percent": current.get("parkability_percent"),
            "status": current.get("status"),
            "confidence": current.get("confidence"),
            "trend": current.get("trend"),
            "estimated_search_time_min": current.get("estimated_search_time_min"),
            "recommendation": current.get("recommendation"),
            "parking_label": current.get("parking_label"),
            "parking_type": current.get("parking_type"),
            "price_label": current.get("price_label"),
            "time_rules": current.get("time_rules"),
        },
        "nearby_segments": [
            segment_item(item)
            for item in nearby[:12]
            if isinstance(item, dict)
        ],
        "heatmap_segments": [
            segment_item(item)
            for item in heatmap[:16]
            if isinstance(item, dict)
        ],
        "parking_pois": [
            {
                "id": item.get("id"),
                "name": clean_parking_place(item.get("name")),
                "address": clean_parking_place(item.get("address")),
                "distance_m": item.get("distance_m"),
                "type": item.get("type"),
                "parking_kind": item.get("parking_kind"),
            }
            for item in pois[:8]
            if isinstance(item, dict)
        ],
        "destination": context.get("destination"),
    }


def cache_key(request: ExplainRequest) -> str:
    target = request.segment_id or request.zone_id or request.segment_name or request.zone_name or "current"
    context_hash = hashlib.sha1(
        json.dumps(compact_context(request), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:10]
    return f"{NEMOTRON_MODEL}:{target}:{request.parkability_percent}:{request.status}:{context_hash}"


def cached_response(key: str) -> ExplainResponse | None:
    item = EXPLAIN_CACHE.get(key)
    if item is None:
        return None
    saved_at, response = item
    if time.time() - saved_at > NEMOTRON_CACHE_TTL_SECONDS:
        EXPLAIN_CACHE.pop(key, None)
        return None
    return response.model_copy(update={"cached": True})


def store_cache(key: str, response: ExplainResponse) -> ExplainResponse:
    EXPLAIN_CACHE[key] = (time.time(), response)
    return response


def elevenlabs_speech(text: str) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ElevenLabs non configurato")
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Testo TTS vuoto")
    cache_key = hashlib.sha1(
        (
            f"{ELEVENLABS_VOICE_ID}:{ELEVENLABS_MODEL_ID}:"
            f"{ELEVENLABS_SIMILARITY_BOOST}:{ELEVENLABS_STYLE_EXAGGERATION}:{cleaned}"
        ).encode("utf-8")
    ).hexdigest()
    if cache_key in TTS_CACHE:
        return TTS_CACHE[cache_key]

    payload = {
        "text": cleaned,
        "model_id": ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": ELEVENLABS_SIMILARITY_BOOST,
            "style": ELEVENLABS_STYLE_EXAGGERATION,
            "use_speaker_boost": True,
        },
    }
    http_request = urlrequest.Request(
        f"{ELEVENLABS_BASE_URL}/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format={ELEVENLABS_OUTPUT_FORMAT}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(http_request, timeout=ELEVENLABS_TIMEOUT_SECONDS) as response:
            audio = response.read()
    except (TimeoutError, OSError, error.HTTPError, error.URLError) as exc:
        print(json.dumps({"service": "nemotron-service", "event": "elevenlabs_tts_failed", "reason": type(exc).__name__}))
        raise HTTPException(status_code=502, detail="ElevenLabs TTS non disponibile") from exc

    if len(TTS_CACHE) >= 64:
        TTS_CACHE.clear()
    TTS_CACHE[cache_key] = audio
    return audio


def compact_json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Nemotron response is not a JSON object")
    return data


def allowed_target_ids(local_context: dict[str, Any]) -> tuple[set[str], set[str]]:
    segment_ids = {
        str(item.get("id"))
        for item in local_context.get("nearby_segments", [])
        if isinstance(item, dict) and item.get("id")
    }
    segment_ids.update(
        str(item.get("id"))
        for item in local_context.get("heatmap_segments", [])
        if isinstance(item, dict) and item.get("id")
    )
    current_id = local_context.get("current_segment", {}).get("id")
    if current_id:
        segment_ids.add(str(current_id))
    poi_ids = {
        str(item.get("id"))
        for item in local_context.get("parking_pois", [])
        if isinstance(item, dict) and item.get("id")
    }
    return segment_ids, poi_ids


def clean_id_list(value: Any, allowed: set[str], limit: int = 3) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        candidate = item.get("id") if isinstance(item, dict) else item
        candidate = str(candidate or "")
        if candidate in allowed and candidate not in result:
            result.append(candidate)
        if len(result) >= limit:
            break
    return result


def nemotron_explanation(request: ExplainRequest) -> ExplainResponse | None:
    if not NEMOTRON_API_KEY:
        return None

    local_context = compact_context(request)
    payload = {
        "model": NEMOTRON_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sei il copilota di ParcheggIA. Italiano corretto, niente termini inglesi. "
                    "Parla come un navigatore per auto: semplice, concreto, senza parole tecniche. "
                    "Usa solo i dati ricevuti. Niente trasporto pubblico, niente regole inventate, niente avvisi generici. "
                    "Non usare mai parole come stima inferita, algoritmo, modello, heatmap, segmento, confidence, trend o dati. "
                    "Scegli il consiglio piu utile confrontando la via attuale, le vie vicine visibili sulla mappa e i parcheggi vicini. "
                    "Il consiglio deve dire cosa fare adesso: resta su questa via, prosegui, svolta verso una via migliore o punta a un parcheggio. "
                    "Cita percentuali, metri, strisce blu, sosta libera o parcheggio solo quando aiutano a decidere. "
                    "action e' anche il testo letto ad alta voce: deve essere sintetica, densa, massimo 170 caratteri, una o due frasi. "
                    "Esempi di action: 'Vicino a te ci sono Via Etnea al 62% e Via Pacini al 58%; prova prima Via Etnea.' "
                    "Oppure: 'Qui la percentuale e' bassa: vai verso Via Caronda al 55%, a 80 metri. In alternativa c'e' un parcheggio in via Roma.' "
                    "minuti_ricerca_stimati indica tempo stimato per trovare posto, non minuti di guida: non dire di guidare per quel tempo. "
                    "Per i tipi di sosta scrivi 'sosta probabile libera', 'strisce blu' o 'sosta limitata', non 'parcheggio probabile libero'. "
                    "Se citi un parcheggio, scrivi 'parcheggio in via...' senza CAP o citta. "
                    "Non scrivere mai 'parcheggia in strisce blu' o formule simili: per i tratti usa sempre il nome della via. "
                    "Scrivi JSON compatto con summary, action, reason, risk, caveat, target_segment_ids, target_parking_poi_ids. "
                    "target_segment_ids e target_parking_poi_ids devono contenere solo ID presenti nel contesto, altrimenti array vuoti. "
                    "action deve essere completa, non solo un luogo, ma senza spiegazioni lunghe. "
                    "summary una frase, reason una frase con i segnali principali, risk una frase breve."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "segment_name": request.segment_name or request.zone_name,
                        "percentuale_stimata": request.parkability_percent,
                        "stato": request.status,
                        "andamento": request.trend,
                        "affidabilita": request.confidence,
                        "minuti_ricerca_stimati": request.estimated_search_time_min,
                        "recommendation": request.recommendation,
                        "contesto_locale": local_context,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 420,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    http_request = urlrequest.Request(
        f"{NEMOTRON_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEMOTRON_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(http_request, timeout=NEMOTRON_TIMEOUT_SECONDS) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        data = compact_json_from_text(content)
    except (KeyError, ValueError, TimeoutError, OSError, error.HTTPError, error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"service": "nemotron-service", "event": "nemotron_fallback", "reason": type(exc).__name__}))
        return None

    summary = clean_driver_language(data.get("summary") or data.get("action") or "")
    action = clean_driver_language(data.get("action") or data.get("summary") or "")
    reason = clean_driver_language(data.get("reason") or "")
    risk = clean_driver_language(data.get("risk") or "")
    caveat = clean_driver_language(data.get("caveat") or "")
    if not action:
        return None
    allowed_segments, allowed_pois = allowed_target_ids(local_context)
    return ExplainResponse(
        model=NEMOTRON_MODEL,
        summary=summary[:320],
        explanation=summary[:320],
        action=action[:220],
        reason=reason[:360],
        risk=risk[:240],
        caveat=caveat[:260],
        target_segment_ids=clean_id_list(data.get("target_segment_ids"), allowed_segments),
        target_parking_poi_ids=clean_id_list(data.get("target_parking_poi_ids"), allowed_pois),
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "up", "service": "nemotron-service"}


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    mode = "nemotron" if NEMOTRON_API_KEY else "simulated-fallback"
    return {"status": "ready", "mode": mode, "model": NEMOTRON_MODEL}


@app.get("/ai/ready")
def ai_readiness_check() -> dict[str, str]:
    return readiness_check()


@app.post("/ai/tts")
@app.post("/tts")
def text_to_speech(request: TtsRequest) -> Response:
    audio = elevenlabs_speech(request.text)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-TTS-Provider": "elevenlabs",
        },
    )


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
    key = cache_key(request)
    cached = cached_response(key)
    if cached is not None:
        return cached
    return store_cache(key, nemotron_explanation(request) or fallback_explanation(request))
