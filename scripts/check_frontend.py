#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.buttons: list[str] = []
        self._in_button = False
        self._button_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if "id" in attr_map and attr_map["id"]:
            self.ids.add(attr_map["id"] or "")
        if tag == "button":
            self._in_button = True
            self._button_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._in_button:
            self.buttons.append("".join(self._button_text).strip())
            self._in_button = False

    def handle_data(self, data: str) -> None:
        if self._in_button:
            self._button_text.append(data)


def require_contains(source: str, needles: list[str], label: str) -> None:
    missing = [needle for needle in needles if needle not in source]
    if missing:
        raise AssertionError(f"{label} missing: {', '.join(missing)}")


def main() -> None:
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend/app.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")

    parser = IdParser()
    parser.feed(html)

    required_ids = {
        "map",
        "clock",
        "weather-icon",
        "weather-temp",
        "sound-toggle",
        "radar-status",
        "zone-name",
        "score",
        "explain-ai",
        "ai-explanation",
        "ai-drive-card",
        "ai-hud-title",
        "ai-hud-text",
        "ai-hud-score",
        "nearby",
        "destination-zone",
        "demo-points",
        "scenario-buttons",
        "found-spot",
        "full-zone",
        "released-spot",
        "parking-closed",
        "source-health",
        "recent-events",
        "gps-status",
        "local-scope",
        "last-updated",
        "locate-me",
        "recenter-map",
        "zoom-in",
        "zoom-out",
        "bottom-sheet",
        "tab-navigation",
        "tab-parking",
        "tab-favorites",
        "tab-settings",
        "favorite-list",
        "save-favorite",
        "arrival-time",
        "next-distance",
        "tomtom-prediction-status",
        "tomtom-traffic-budget",
        "tomtom-poi-status",
        "tomtom-search-budget",
        "test-tomtom-pois",
        "drive-simulation",
        "theme-toggle",
    }
    missing_ids = sorted(required_ids - parser.ids)
    if missing_ids:
        raise AssertionError(f"Frontend missing ids: {', '.join(missing_ids)}")

    require_contains(
        html,
        [
            "Ho trovato posto",
            "Tratto pieno",
            "Posto liberato",
            "Parcheggio chiuso",
            "Suggerimento",
            "maplibre-gl",
            "pmtiles",
            "Material+Symbols",
            "Stato e demo",
            "Simula guida 500 m",
            "simulated-ai-tts",
        ],
        "HTML",
    )
    if "Disponibilita parcheggio" in html:
        raise AssertionError("HTML still contains the removed parking availability box")
    require_contains(
        js,
        [
            "maplibregl.Map",
            "pmtiles.Protocol",
            "pmtiles://",
            "parking-heat",
            "parking-ribbon-halo",
            "parking-ribbon-fill",
            "parking-segment-marker-rings",
            "parking-segment-marker-percent",
            "parking-badge-source",
            "route-line",
            "syncMapSources",
            "syncCamera",
            "sampleLineCoordinates",
            "segmentMarkerFeatures",
            "driveToMapPoint",
            "startDriveSimulation",
            "stopDriveSimulation",
            "SIMULATION_SPACING_M",
            "SIMULATION_DATA_REFRESH_EVERY",
            "SIMULATION_ANIMATION_MS",
            "visualOnly",
            "setRotation",
            "pitchAlignment",
            "percent_label",
            'sendReport("found_spot")',
            'sendReport("full_zone")',
            'sendReport("released_spot")',
            'sendReport("parking_closed")',
            'api("/live-sessions/start"',
            'api("/segments")',
            "bboxAround",
            "`/segment-heatmap?bbox=${bboxAround(state.currentPoint)}&zoom=${zoom}`",
            'api("/segment-reports"',
            "current_segment",
            "nearby_segments",
            'api("/admin/source-health")',
            'aiApi("/ai/explain"',
            "renderAiSuggestion",
            "syncAiHud",
            "closeAiHudAfterSpeech",
            "aiHudClosedKey",
            "onend",
            "handleAiHudClick",
            "playAiHudReveal",
            "playAiHudDrop",
            "aiLocalContext",
            "target_segment_ids",
            "target_parking_poi_ids",
            "heatmap_segments",
            "current_point",
            "aiTargetSegmentIds",
            "aiTargetParkingPoiIds",
            "syncAiTargetMarkers",
            "nearby_segments",
            "parking_pois",
            "scheduleAutoAiSuggestion",
            "AI_AUTO_DEBOUNCE_MS",
            "speechSynthesis",
            "getVoices",
            "SpeechSynthesisUtterance",
            'fetch(`${AI_URL}/ai/tts`',
            "new Audio",
            "URL.createObjectURL",
            "stopTtsPlayback",
            "speakBrowserSuggestion",
            "toggleTts",
            "toggleTheme",
            "dataset.theme",
            "escapeHtml",
            'ingestionApi("/scenarios")',
            "navigator.geolocation",
            "open-meteo.com",
            "updateWeather",
            'api(`/tomtom/parking-pois?',
            "syncParkingPoiMarkers",
            "applyPoiMarkerClass",
            "spin-in",
            "refreshRoadNetwork",
            'api(`/road-network?',
            "refreshTomTomPrediction",
            'ingestionApi("/traffic/tomtom/publish"',
            "TOMTOM_PREDICTION_REFRESH_MS",
            "TOMTOM_PREDICTION_SETTLE_MS",
            "testTomTomPois",
            "handleKeyboardMove",
            "snapPointToRoad",
            "ArrowUp",
            "watchPosition",
            "LOCAL_RADIUS_M",
            "localStorage",
        ],
        "Frontend JS",
    )
    if "localAiSuggestion" in js or "localAiAction" in js or "localAiRisk" in js:
        raise AssertionError("Frontend still renders local/static AI suggestions")
    ai_speech_block = js.split("function aiSpeechText", 1)[1].split("function ", 1)[0]
    if "explanation.reason" in ai_speech_block or "explanation.risk" in ai_speech_block:
        raise AssertionError("TTS speech text should stay concise and avoid reason/risk fields")
    if "element.className = poiMarkerClass" in js:
        raise AssertionError("Frontend overwrites MapLibre marker classes for parking POIs")
    if ".parking-poi-marker {\n  --poi-bg: #edf5ff;\n  --poi-color: #146cff;\n  position: relative;" in css:
        raise AssertionError("Parking POI marker overrides MapLibre absolute positioning")
    require_contains(
        css,
        [
            "@media (max-width: 980px)",
            "height: 100vh",
            ".drive-shell",
            ".drive-dock",
            ".bottom-sheet",
            ".hud-panel",
            ".maplibregl-marker",
            ".parking-poi-marker",
            ".parking-poi-marker.spawn",
            ".parking-poi-marker.spin-in",
            ".parking-poi-marker.ai-target",
            ".ai-target-segment-marker",
            ".ai-drive-card",
            ".ai-drive-card.has-suggestion",
            ".ai-drive-card:not(.has-suggestion)",
            ".ai-drive-card.closing",
            "suggestion-pop",
            "dot-drop",
            "-webkit-line-clamp: 3",
            "--poi-bg",
            "poi-pop",
            "poi-spin-in",
            "ai-pulse",
            "ai-dot-drop",
            "ai-drop-open",
            "ai-card-close",
            "ai-target-spin",
            "data-theme=\"light\"",
            "route-active",
            "letter-spacing: 0",
            "position: absolute",
        ],
        "Frontend CSS",
    )

    print("Frontend checks OK")


if __name__ == "__main__":
    main()
