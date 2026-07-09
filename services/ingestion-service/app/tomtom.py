import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
INCIDENTS_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"
NEARBY_SEARCH_URL = "https://api.tomtom.com/search/2/nearbySearch/.json"
PARKING_CATEGORY_SET = "7369,7313"
REQUEST_DELAY_SECONDS = 0.25
RETRY_DELAY_SECONDS = 1.0
INCIDENT_FIELDS = (
    "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,"
    "magnitudeOfDelay,events{description,code,iconCategory},startTime,endTime,"
    "from,to,length,delay,roadNumbers,timeValidity,probabilityOfOccurrence,"
    "numberOfReports,lastReportTime}}}"
)
BudgetGuard = Callable[[str], None]


class TomTomError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def load_api_key() -> str:
    key = os.getenv("TOMTOM_API_KEY", "").strip()
    if key:
        return key

    key_file = os.getenv("TOMTOM_API_KEY_FILE", "").strip()
    if key_file:
        return Path(key_file).read_text(encoding="utf-8").strip()

    raise TomTomError(503, "TOMTOM_API_KEY or TOMTOM_API_KEY_FILE is not configured")


def budget_cap(monthly_limit: int, fraction: float) -> int:
    return max(1, int(monthly_limit * fraction))


def cell_key(lat: float, lon: float, cell_m: int = 250) -> str:
    lat_step = cell_m / 111_320
    lon_step = cell_m / (111_320 * max(0.2, math.cos(math.radians(lat))))
    return f"{math.floor(lat / lat_step)}:{math.floor(lon / lon_step)}"


def fetch_json(
    url: str,
    params: dict[str, Any],
    timeout: int = 10,
    service: str = "tomtom",
    before_request: BudgetGuard | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, safe=",{}")
    for attempt in range(2):
        if before_request:
            before_request(service)
        request = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            if error.code in {403, 429} and attempt == 0:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            raise TomTomError(error.code, extract_error_message(body)) from error
        except Exception as error:
            raise TomTomError(502, str(error)) from error

    raise TomTomError(502, "TomTom request failed")


def extract_error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body[:300]
    detailed = payload.get("detailedError") or {}
    return detailed.get("message") or payload.get("error") or body[:300]


def bbox_from_radius(lat: float, lon: float, radius_m: int) -> str:
    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * max(0.2, math.cos(math.radians(lat))))
    return f"{lon - lon_delta:.6f},{lat - lat_delta:.6f},{lon + lon_delta:.6f},{lat + lat_delta:.6f}"


def sample_points(lat: float, lon: float, radius_m: int) -> list[tuple[str, float, float]]:
    offset_m = min(radius_m, 500) * 0.35
    lat_delta = offset_m / 111_320
    lon_delta = offset_m / (111_320 * max(0.2, math.cos(math.radians(lat))))
    return [
        ("center", lat, lon),
        ("north", lat + lat_delta, lon),
        ("east", lat, lon + lon_delta),
        ("south", lat - lat_delta, lon),
        ("west", lat, lon - lon_delta),
    ]


def traffic_pressure_from_flow(segment: dict[str, Any]) -> float | None:
    if segment.get("roadClosure") is True:
        return 1.0

    current_speed = segment.get("currentSpeed")
    free_flow_speed = segment.get("freeFlowSpeed")
    if not isinstance(current_speed, (int, float)) or not isinstance(free_flow_speed, (int, float)):
        return None
    if free_flow_speed <= 0:
        return 1.0
    return round(1 - min(1.0, current_speed / free_flow_speed), 3)


def incident_pressure(incidents: list[dict[str, Any]]) -> float:
    if not incidents:
        return 0.0

    category_weights = {
        "RoadClosed": 1.0,
        "Accident": 0.8,
        "Jam": 0.7,
        "LaneClosed": 0.55,
        "RoadWorks": 0.45,
        "BrokenDownVehicle": 0.35,
    }
    pressure = 0.0
    for incident in incidents:
        props = incident.get("properties") or {}
        category = props.get("iconCategory")
        delay = props.get("delay") or 0
        magnitude = props.get("magnitudeOfDelay")
        weighted = category_weights.get(str(category), 0.25)
        if isinstance(delay, (int, float)) and delay > 0:
            weighted = max(weighted, min(1.0, delay / 900))
        if isinstance(magnitude, (int, float)):
            weighted = max(weighted, min(1.0, magnitude / 4))
        pressure = max(pressure, weighted)
    return round(pressure, 3)


def summarize_flow(
    api_key: str,
    lat: float,
    lon: float,
    radius_m: int,
    before_request: BudgetGuard | None = None,
) -> list[dict[str, Any]]:
    samples = []
    for label, sample_lat, sample_lon in sample_points(lat, lon, radius_m):
        if samples:
            # ponytail: six-call probe stays below common 5 QPS API-key limits.
            time.sleep(REQUEST_DELAY_SECONDS)
        data = fetch_json(
            FLOW_URL,
            {"key": api_key, "point": f"{sample_lat},{sample_lon}", "unit": "KMPH"},
            service="traffic_flow",
            before_request=before_request,
        )
        segment = data.get("flowSegmentData") or {}
        pressure = traffic_pressure_from_flow(segment)
        samples.append(
            {
                "sample": label,
                "lat": round(sample_lat, 6),
                "lon": round(sample_lon, 6),
                "current_speed": segment.get("currentSpeed"),
                "free_flow_speed": segment.get("freeFlowSpeed"),
                "confidence": segment.get("confidence"),
                "road_closure": segment.get("roadClosure"),
                "traffic_pressure": pressure,
            }
        )
    return samples


def fetch_incidents(
    api_key: str,
    lat: float,
    lon: float,
    radius_m: int,
    before_request: BudgetGuard | None = None,
) -> list[dict[str, Any]]:
    data = fetch_json(
        INCIDENTS_URL,
        {
            "key": api_key,
            "bbox": bbox_from_radius(lat, lon, radius_m),
            "fields": INCIDENT_FIELDS,
            "language": "it-IT",
            "timeValidityFilter": "present",
        },
        service="traffic_incidents",
        before_request=before_request,
    )
    return data.get("incidents") or []


def estimate_nearby(
    api_key: str,
    lat: float,
    lon: float,
    radius_m: int = 500,
    before_request: BudgetGuard | None = None,
) -> dict[str, Any]:
    flows = summarize_flow(api_key, lat, lon, radius_m, before_request)
    valid_flows = [flow for flow in flows if flow["traffic_pressure"] is not None]
    if not valid_flows:
        raise TomTomError(502, "TomTom Flow did not return usable speed data")

    flow_pressure = sum(flow["traffic_pressure"] for flow in valid_flows) / len(valid_flows)
    current_speeds = [flow["current_speed"] for flow in valid_flows if isinstance(flow["current_speed"], (int, float))]
    free_speeds = [flow["free_flow_speed"] for flow in valid_flows if isinstance(flow["free_flow_speed"], (int, float))]
    confidences = [flow["confidence"] for flow in valid_flows if isinstance(flow["confidence"], (int, float))]
    time.sleep(REQUEST_DELAY_SECONDS)
    incidents = fetch_incidents(api_key, lat, lon, radius_m, before_request)
    events_pressure = incident_pressure(incidents)

    return {
        "provider": "tomtom",
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "traffic_pressure": round(max(flow_pressure, min(1.0, flow_pressure + events_pressure * 0.25)), 3),
        "event_pressure": events_pressure,
        "current_speed": round(sum(current_speeds) / len(current_speeds), 1) if current_speeds else None,
        "free_flow_speed": round(sum(free_speeds) / len(free_speeds), 1) if free_speeds else None,
        "confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.5,
        "flow_samples": flows,
        "incidents_count": len(incidents),
        "incidents_sample": [
            {
                "category": (incident.get("properties") or {}).get("iconCategory"),
                "delay": (incident.get("properties") or {}).get("delay"),
                "length": (incident.get("properties") or {}).get("length"),
                "from": (incident.get("properties") or {}).get("from"),
                "to": (incident.get("properties") or {}).get("to"),
            }
            for incident in incidents[:5]
        ],
    }


def parking_kind(result: dict[str, Any]) -> str:
    category_ids = {
        str(category.get("id"))
        for category in (result.get("poi") or {}).get("categorySet", [])
        if category.get("id") is not None
    }
    if "7313" in category_ids:
        return "parking_garage"
    if "7369" in category_ids:
        return "open_parking_area"
    return "parking"


def clean_parking_address(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.split(",") if part.strip()]
    kept = []
    for part in parts:
        if re.match(r"^\d{5}\b", part):
            continue
        if re.fullmatch(r"Catania(?:\s+CT)?|CT|Italia|Italy", part, flags=re.IGNORECASE):
            continue
        kept.append(part)
    cleaned = ", ".join(kept) if parts else text
    cleaned = re.sub(r"(?:,\s*)?\b\d{5}\s+Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:,\s*)?Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:,\s*)?(?:Italia|Italy)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.-") or None


def parse_parking_pois(data: dict[str, Any]) -> list[dict[str, Any]]:
    pois = []
    for result in data.get("results") or []:
        poi = result.get("poi") or {}
        address = result.get("address") or {}
        position = result.get("position") or {}
        display_address = clean_parking_address(address.get("freeformAddress"))
        pois.append(
            {
                "id": result.get("id"),
                "name": poi.get("name") or display_address or "Parcheggio",
                "parking_kind": parking_kind(result),
                "lat": position.get("lat"),
                "lon": position.get("lon"),
                "distance_m": result.get("dist"),
                "address": display_address,
                "opening_hours": poi.get("openingHours"),
                "data_sources": result.get("dataSources"),
            }
        )
    return pois


def search_parking_pois(
    api_key: str,
    lat: float,
    lon: float,
    radius_m: int = 500,
    limit: int = 10,
    before_request: BudgetGuard | None = None,
) -> dict[str, Any]:
    data = fetch_json(
        NEARBY_SEARCH_URL,
        {
            "key": api_key,
            "lat": lat,
            "lon": lon,
            "radius": radius_m,
            "limit": limit,
            "countrySet": "IT",
            "categorySet": PARKING_CATEGORY_SET,
            "language": "it-IT",
        },
        service="search",
        before_request=before_request,
    )
    return {
        "provider": "tomtom",
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "parking_pois": parse_parking_pois(data),
    }
