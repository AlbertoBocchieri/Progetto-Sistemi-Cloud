from typing import Any

from pydantic import BaseModel


class ZoneResponse(BaseModel):
    id: str
    name: str
    city: str
    zone_type: str
    baseline_capacity_estimate: int | None
    geometry: dict[str, Any]