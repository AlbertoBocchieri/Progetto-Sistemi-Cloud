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
        "network-label",
        "weather-icon",
        "weather-temp",
        "radar-status",
        "zone-name",
        "score",
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
            "Spiegazione AI",
            "maplibre-gl",
            "pmtiles",
            "Material+Symbols",
            "Stato e demo",
            "realtime-status",
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
            "route-line",
            "syncMapSources",
            "syncCamera",
            "sampleLineCoordinates",
            'sendReport("found_spot")',
            'sendReport("full_zone")',
            'sendReport("released_spot")',
            'sendReport("parking_closed")',
            'api("/live-sessions/start"',
            'api("/segments")',
            'api("/segment-heatmap")',
            'api("/segment-reports"',
            "current_segment",
            "nearby_segments",
            'api("/admin/source-health")',
            'aiApi("/ai/explain"',
            'ingestionApi("/scenarios")',
            "navigator.geolocation",
            "navigator.connection",
            "open-meteo.com",
            "updateWeather",
            "updateNetworkStatus",
            "watchPosition",
            "LOCAL_RADIUS_M",
            "localStorage",
        ],
        "Frontend JS",
    )
    require_contains(
        css,
        [
            "@media (max-width: 980px)",
            "height: 100vh",
            ".drive-shell",
            ".drive-dock",
            ".bottom-sheet",
            ".hud-panel",
            "letter-spacing: 0",
            "position: absolute",
        ],
        "Frontend CSS",
    )

    print("Frontend checks OK")


if __name__ == "__main__":
    main()
