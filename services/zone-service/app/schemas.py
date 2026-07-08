from typing import Any

from pydantic import BaseModel, Field


class ZoneResponse(BaseModel):
    id: str
    name: str
    city: str
    zone_type: str
    baseline_capacity_estimate: int | None
    geometry: dict[str, Any]
    parking_lots: list[dict[str, Any]] = Field(default_factory=list)


class ParkingSegmentResponse(BaseModel):
    id: str
    street_name: str
    city: str
    parking_type: str
    parking_label: str
    tariff_zone: str | None = None
    price_label: str | None = None
    time_rules: str | None = None
    source: str
    source_confidence: float
    length_m: int
    geometry: dict[str, Any]
    parking_lots: list[dict[str, Any]] = Field(default_factory=list)


class PredictionResponse(BaseModel):
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


class NearbyZoneResponse(ZoneResponse):
    distance_m: int
    prediction: PredictionResponse


class NearbySegmentResponse(ParkingSegmentResponse):
    distance_m: int
    prediction: PredictionResponse


class HeatmapZoneResponse(BaseModel):
    zone_id: str
    name: str
    polygon: dict[str, Any]
    parkability_percent: int
    status: str
    heatmap_intensity: float


class HeatmapResponse(BaseModel):
    generated_at: str
    expires_at: str
    zones: list[HeatmapZoneResponse]


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


class ReportRequest(BaseModel):
    zone_id: str
    report_type: str
    session_id: str | None = None


class SegmentReportRequest(BaseModel):
    segment_id: str
    report_type: str
    session_id: str | None = None


class ReportResponse(BaseModel):
    id: str
    segment_id: str
    report_type: str
    status: str


class LiveSessionResponse(BaseModel):
    session_id: str
    status: str
    started_at: str
    ended_at: str | None = None


class LocationUpdateRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class LocationUpdateResponse(BaseModel):
    session_id: str
    status: str
    current_segment: ParkingSegmentResponse | None
    prediction: PredictionResponse | None
    nearby_segments: list[NearbySegmentResponse]
