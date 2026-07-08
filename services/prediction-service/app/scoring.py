from typing import Any


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


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


def report_adjustment(found_spot: Any, full_zone: Any, released_spot: Any = 0, parking_closed: Any = 0) -> int:
    found = float(found_spot or 0)
    full = float(full_zone or 0)
    released = float(released_spot or 0)
    closed = float(parking_closed or 0)
    return round(max(-15, min(15, found * 5 + released * 6 - full * 7 - closed * 8)))


def signal_delta(signals: dict[str, Any]) -> int:
    if not signals:
        return 0
    traffic_pressure = clamp01(signals.get("traffic_pressure"))
    parking_availability = clamp01(signals.get("parking_lot_availability"), 0.5)
    event_pressure = clamp01(signals.get("event_pressure"))
    return max(
        -35,
        min(20, round((parking_availability - 0.5) * 35 - traffic_pressure * 22 - event_pressure * 18)),
    )
