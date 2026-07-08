const GATEWAY_URL = "http://localhost:8000";
const API_URL = `${GATEWAY_URL}/api/v1`;
const AI_URL = GATEWAY_URL;
const INGESTION_URL = `${GATEWAY_URL}/ingestion`;
const LOCAL_RADIUS_M = 900;
const REFRESH_MS = 20000;
const WEATHER_REFRESH_MS = 10 * 60 * 1000;
const GPS_OPTIONS = { enableHighAccuracy: true, maximumAge: 8000, timeout: 10000 };
const PMTILES_URL = new URL("/assets/catania.pmtiles", window.location.href).href;
const FAVORITES_KEY = "parcheggia:favorites";
const MAP_DEFAULT_ZOOM = 17.6;
const MAP_TRACKING_ZOOM = 18.1;

const demoPoints = [
  { id: "stesicoro", label: "Stesicoro", lat: 37.507, lon: 15.083 },
  { id: "borgo", label: "Borgo", lat: 37.525, lon: 15.071 },
  { id: "sanzio", label: "Sanzio", lat: 37.521, lon: 15.083 },
  { id: "europa", label: "Europa", lat: 37.519, lon: 15.104 },
];

const colors = {
  very_difficult: "#ff4545",
  difficult: "#ff7a30",
  uncertain: "#ffd447",
  good: "#29ca4a",
  favorable: "#18b93f",
};

const labels = {
  very_difficult: "Molto difficile",
  difficult: "Difficile",
  uncertain: "Medio",
  good: "Alta",
  favorable: "Alta",
  stable: "Stabile",
  better: "Migliora",
  worse: "Peggiora",
};

const state = {
  segments: [],
  heatmap: new Map(),
  currentPoint: demoPoints[0],
  currentSegment: null,
  prediction: null,
  nearby: [],
  session: null,
  destinationSegmentId: "",
  map: null,
  mapLoaded: false,
  segmentClickBound: false,
  userMarker: null,
  destinationMarker: null,
  trackingGps: false,
  watchId: null,
  lastUpdatedAt: null,
  refreshTimer: null,
  updateToken: 0,
  weatherKey: "",
  weatherUpdatedAt: 0,
  activeSheet: "navigation",
  favorites: loadFavorites(),
};

const els = {
  map: document.querySelector("#map"),
  clock: document.querySelector("#clock"),
  networkLabel: document.querySelector("#network-label"),
  weatherIcon: document.querySelector("#weather-icon"),
  weatherTemp: document.querySelector("#weather-temp"),
  soundToggle: document.querySelector("#sound-toggle"),
  nextDistance: document.querySelector("#next-distance"),
  nextAction: document.querySelector("#next-action"),
  nextRoad: document.querySelector("#next-road"),
  followingAction: document.querySelector("#following-action"),
  followingRoad: document.querySelector("#following-road"),
  followingDistance: document.querySelector("#following-distance"),
  arrivalTime: document.querySelector("#arrival-time"),
  arrivalMinutes: document.querySelector("#arrival-minutes"),
  arrivalDistance: document.querySelector("#arrival-distance"),
  arrivalAddress: document.querySelector("#arrival-address"),
  locateMe: document.querySelector("#locate-me"),
  recenterMap: document.querySelector("#recenter-map"),
  zoomIn: document.querySelector("#zoom-in"),
  zoomOut: document.querySelector("#zoom-out"),
  destinationFloating: document.querySelector("#destination-marker-button"),
  destinationFloatingLabel: document.querySelector("#destination-floating-label"),
  tabNavigation: document.querySelector("#tab-navigation"),
  tabParking: document.querySelector("#tab-parking"),
  tabFavorites: document.querySelector("#tab-favorites"),
  tabSettings: document.querySelector("#tab-settings"),
  openMenu: document.querySelector("#open-menu"),
  bottomSheet: document.querySelector("#bottom-sheet"),
  closeSheet: document.querySelector("#close-sheet"),
  sheetKicker: document.querySelector("#sheet-kicker"),
  sheetTitle: document.querySelector("#sheet-title"),
  navigationContent: document.querySelector("#navigation-content"),
  parkingContent: document.querySelector("#parking-content"),
  favoritesContent: document.querySelector("#favorites-content"),
  settingsContent: document.querySelector("#settings-content"),
  currentSummary: document.querySelector("#current-summary"),
  radarStatus: document.querySelector("#radar-status"),
  gpsStatus: document.querySelector("#gps-status"),
  localScope: document.querySelector("#local-scope"),
  lastUpdated: document.querySelector("#last-updated"),
  zoneName: document.querySelector("#zone-name"),
  score: document.querySelector("#score"),
  status: document.querySelector("#status"),
  trend: document.querySelector("#trend"),
  searchTime: document.querySelector("#search-time"),
  confidence: document.querySelector("#confidence"),
  recommendation: document.querySelector("#recommendation"),
  explainAi: document.querySelector("#explain-ai"),
  aiExplanation: document.querySelector("#ai-explanation"),
  nearby: document.querySelector("#nearby"),
  foundSpot: document.querySelector("#found-spot"),
  fullZone: document.querySelector("#full-zone"),
  releasedSpot: document.querySelector("#released-spot"),
  parkingClosed: document.querySelector("#parking-closed"),
  favoriteList: document.querySelector("#favorite-list"),
  saveFavorite: document.querySelector("#save-favorite"),
  destinationZone: document.querySelector("#destination-zone"),
  destinationResult: document.querySelector("#destination-result"),
  demoPoints: document.querySelector("#demo-points"),
  scenarioButtons: document.querySelector("#scenario-buttons"),
  scenarioStatus: document.querySelector("#scenario-status"),
  sourceHealth: document.querySelector("#source-health"),
  recentEvents: document.querySelector("#recent-events"),
};

function request(baseUrl, path, options = {}) {
  return fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  }).then(async (response) => {
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  });
}

function api(path, options = {}) {
  return request(API_URL, path, options);
}

function ingestionApi(path, options = {}) {
  return request(INGESTION_URL, path, options);
}

function aiApi(path, options = {}) {
  return request(AI_URL, path, options);
}

function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(state.favorites));
}

function distanceMeters(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function formatDistance(meters) {
  return meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(1)} km`;
}

function segmentCenter(segment) {
  const points = segment.geometry.coordinates;
  const total = points.reduce(
    (sum, [lon, lat]) => ({ lon: sum.lon + lon, lat: sum.lat + lat }),
    { lon: 0, lat: 0 },
  );
  return { lon: total.lon / points.length, lat: total.lat / points.length };
}

function localHeatSegments() {
  return state.segments
    .map((segment) => {
      const center = segmentCenter(segment);
      return { segment, ...center, distance: distanceMeters(state.currentPoint, center) };
    })
    .filter((item) => item.distance <= LOCAL_RADIUS_M)
    .sort((a, b) => a.distance - b.distance);
}

function currentTarget() {
  if (state.destinationSegmentId) {
    const segment = state.segments.find((item) => item.id === state.destinationSegmentId);
    if (segment) return { segment, ...segmentCenter(segment) };
  }

  const nearby = state.nearby.find((item) => item.id !== state.currentSegment?.id) || state.nearby[0];
  const segment = nearby ? state.segments.find((item) => item.id === nearby.id) || nearby : null;
  if (segment) return { segment, ...segmentCenter(segment) };

  return {
    segment: null,
    lon: state.currentPoint.lon + 0.0065,
    lat: state.currentPoint.lat + 0.006,
  };
}

function bearingBetween(a, b) {
  const lon1 = (a.lon * Math.PI) / 180;
  const lon2 = (b.lon * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function createDriveStyle() {
  return {
    version: 8,
    name: "ParcheggIA Dark Catania",
    sources: {
      catania: {
        type: "vector",
        url: `pmtiles://${PMTILES_URL}`,
        attribution: "&copy; OpenStreetMap contributors",
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0b1420" } },
      { id: "earth", type: "fill", source: "catania", "source-layer": "earth", paint: { "fill-color": "#162330" } },
      { id: "natural", type: "fill", source: "catania", "source-layer": "natural", paint: { "fill-color": "#17342e", "fill-opacity": 0.38 } },
      { id: "landuse", type: "fill", source: "catania", "source-layer": "landuse", paint: { "fill-color": "#1d3740", "fill-opacity": 0.24 } },
      { id: "water", type: "fill", source: "catania", "source-layer": "water", paint: { "fill-color": "#0b2637" } },
      {
        id: "roads-casing",
        type: "line",
        source: "catania",
        "source-layer": "roads",
        paint: {
          "line-color": "#111923",
          "line-opacity": 0.95,
          "line-width": ["interpolate", ["linear"], ["zoom"], 12, 1.4, 16, 7],
        },
      },
      {
        id: "roads",
        type: "line",
        source: "catania",
        "source-layer": "roads",
        paint: {
          "line-color": "#415160",
          "line-opacity": 0.82,
          "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.8, 16, 3.5],
        },
      },
      {
        id: "buildings",
        type: "fill",
        source: "catania",
        "source-layer": "buildings",
        minzoom: 14,
        paint: { "fill-color": "#253443", "fill-opacity": 0.58 },
      },
    ],
  };
}

function registerPmtiles() {
  if (!window.maplibregl || !window.pmtiles) throw new Error("MapLibre o PMTiles non disponibili");
  if (state.pmtilesRegistered) return;
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  protocol.add(new pmtiles.PMTiles(PMTILES_URL));
  state.pmtilesRegistered = true;
}

function initMap() {
  if (state.map) return;
  registerPmtiles();

  state.map = new maplibregl.Map({
    container: "map",
    style: createDriveStyle(),
    center: [state.currentPoint.lon, state.currentPoint.lat],
    zoom: MAP_DEFAULT_ZOOM,
    pitch: 45,
    bearing: -18,
    attributionControl: false,
    logoPosition: "bottom-left",
  });

  state.map.dragRotate.disable();
  state.map.touchZoomRotate.disableRotation();
  state.map.on("load", () => {
    state.mapLoaded = true;
    ensureDynamicLayers();
    syncMapSources();
    syncMarkers();
    syncCamera();
  });
}

function ensureDynamicLayers() {
  if (!state.mapLoaded) return;
  const map = state.map;

  if (!map.getSource("parking-heat-source")) {
    map.addSource("parking-heat-source", { type: "geojson", data: emptyCollection() });
    map.addSource("parking-segment-source", { type: "geojson", data: emptyCollection() });
    map.addSource("route-source", { type: "geojson", data: emptyCollection(), lineMetrics: true });
  }

  if (!map.getLayer("parking-heat")) {
    map.addLayer({
      id: "parking-heat",
      type: "heatmap",
      source: "parking-heat-source",
      maxzoom: 20,
      paint: {
        "heatmap-weight": ["*", ["get", "heatmap_intensity"], ["get", "confidence"]],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 13, 0.8, 16, 1.5],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 13, 34, 16, 86, 18, 130],
        "heatmap-opacity": 0.48,
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(24,185,63,0)",
          0.18,
          "rgba(24,185,63,0.35)",
          0.42,
          "rgba(255,212,71,0.58)",
          0.74,
          "rgba(255,122,48,0.72)",
          1,
          "rgba(255,69,69,0.84)",
        ],
      },
    });
    map.addLayer({
      id: "parking-ribbon-halo",
      type: "line",
      source: "parking-segment-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "status"], "good", colors.good, "favorable", colors.favorable, "uncertain", colors.uncertain, "difficult", colors.difficult, colors.very_difficult],
        "line-width": ["interpolate", ["linear"], ["zoom"], 14, 24, 16, 46, 18, 72],
        "line-blur": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 18, 0.65, 11, 0.95, 7],
        "line-opacity": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 0.12, 0.65, 0.22, 0.95, 0.34],
      },
    });
    map.addLayer({
      id: "parking-ribbon-fill",
      type: "line",
      source: "parking-segment-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "status"], "good", colors.good, "favorable", colors.favorable, "uncertain", colors.uncertain, "difficult", colors.difficult, colors.very_difficult],
        "line-width": ["interpolate", ["linear"], ["zoom"], 14, 8, 16, 15, 18, 24],
        "line-blur": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 8, 0.65, 4, 0.95, 2],
        "line-opacity": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 0.22, 0.65, 0.44, 0.95, 0.68],
      },
    });
    map.addLayer({
      id: "parking-segments-casing",
      type: "line",
      source: "parking-segment-source",
      paint: {
        "line-color": "rgba(3,8,14,0.78)",
        "line-width": ["case", ["==", ["get", "active"], true], 12, 8],
        "line-opacity": 0.76,
      },
    });
    map.addLayer({
      id: "parking-segments",
      type: "line",
      source: "parking-segment-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": ["match", ["get", "status"], "good", colors.good, "favorable", colors.favorable, "uncertain", colors.uncertain, "difficult", colors.difficult, colors.very_difficult],
        "line-width": ["case", ["==", ["get", "active"], true], 7, 4],
        "line-opacity": ["case", ["==", ["get", "active"], true], 0.96, 0.74],
      },
    });
    map.addLayer({
      id: "parking-segments-hit",
      type: "line",
      source: "parking-segment-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "rgba(255,255,255,0)",
        "line-width": 28,
      },
    });
    map.addLayer({
      id: "route-line",
      type: "line",
      source: "route-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#0b6dff",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 7, 16, 12],
        "line-opacity": 0.98,
        "line-blur": 0.2,
      },
    });
    map.addLayer({
      id: "route-line-casing",
      type: "line",
      source: "route-source",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "rgba(222,241,255,0.95)",
        "line-width": ["interpolate", ["linear"], ["zoom"], 13, 10, 16, 16],
        "line-opacity": 0.82,
      },
    }, "route-line");

    if (!state.segmentClickBound) {
      state.segmentClickBound = true;
      map.on("click", "parking-segments-hit", (event) => {
        const feature = event.features?.[0];
        const segmentId = feature?.properties?.segment_id;
        if (!segmentId) return;
        chooseDestination(segmentId);
        setSheet("parking", true);
      });
      map.on("mouseenter", "parking-segments-hit", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "parking-segments-hit", () => {
        map.getCanvas().style.cursor = "";
      });
    }
  }
}

function emptyCollection() {
  return { type: "FeatureCollection", features: [] };
}

function syncMapSources() {
  if (!state.mapLoaded) return;
  ensureDynamicLayers();
  const heatSource = state.map.getSource("parking-heat-source");
  const segmentSource = state.map.getSource("parking-segment-source");
  const routeSource = state.map.getSource("route-source");
  if (!heatSource || !segmentSource || !routeSource) return;

  heatSource.setData(heatFeatures());
  segmentSource.setData(segmentFeatures());
  routeSource.setData(routeFeature());
  syncMarkers();
}

function heatFeatures() {
  return {
    type: "FeatureCollection",
    features: localHeatSegments().flatMap((item) => {
      const heat = state.heatmap.get(item.segment.id) || {};
      const prediction = predictionForSegment(item.segment.id);
      const line = heat.line || item.segment.geometry;
      const properties = {
        segment_id: item.segment.id,
        parkability_percent: heat.parkability_percent ?? 50,
        status: heat.status || "uncertain",
        heatmap_intensity: heat.heatmap_intensity ?? 0.45,
        confidence: prediction?.confidence ?? 0.55,
      };
      return sampleLineCoordinates(line.coordinates).map((point) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: point },
        properties,
      }));
    }),
  };
}

function coordinateDistanceMeters(a, b) {
  return distanceMeters({ lon: a[0], lat: a[1] }, { lon: b[0], lat: b[1] });
}

function interpolateCoordinate(a, b, ratio) {
  return [a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio];
}

function sampleLineCoordinates(coordinates, spacingMeters = 18) {
  if (!Array.isArray(coordinates) || coordinates.length < 2) return coordinates || [];
  const points = [coordinates[0]];
  for (let index = 1; index < coordinates.length; index += 1) {
    const start = coordinates[index - 1];
    const end = coordinates[index];
    const pieces = Math.max(1, Math.ceil(coordinateDistanceMeters(start, end) / spacingMeters));
    for (let piece = 1; piece <= pieces; piece += 1) {
      points.push(interpolateCoordinate(start, end, piece / pieces));
    }
  }
  return points;
}

function predictionForSegment(segmentId) {
  if (state.currentSegment?.id === segmentId && state.prediction) return state.prediction;
  return state.nearby.find((item) => item.id === segmentId)?.prediction || null;
}

function segmentFeatures() {
  return {
    type: "FeatureCollection",
    features: localHeatSegments().map((item) => {
      const heat = state.heatmap.get(item.segment.id) || {};
      return {
        type: "Feature",
        geometry: heat.line || item.segment.geometry,
        properties: {
          segment_id: item.segment.id,
          street_name: item.segment.street_name,
          parking_type: item.segment.parking_type,
          status: heat.status || "uncertain",
          confidence: predictionForSegment(item.segment.id)?.confidence ?? 0.55,
          active: item.segment.id === state.currentSegment?.id,
        },
      };
    }),
  };
}

function routeFeature() {
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "LineString", coordinates: buildRouteCoordinates() },
        properties: {},
      },
    ],
  };
}

function buildRouteCoordinates() {
  const start = state.currentPoint;
  const target = currentTarget();
  const direct = distanceMeters(start, target);
  if (direct < 80) {
    return [
      [start.lon, start.lat],
      [start.lon + 0.001, start.lat + 0.0016],
      [start.lon + 0.0032, start.lat + 0.0028],
      [start.lon + 0.0058, start.lat + 0.0042],
      [start.lon + 0.0072, start.lat + 0.0056],
    ];
  }
  return [
    [start.lon, start.lat],
    [start.lon + (target.lon - start.lon) * 0.18, start.lat + (target.lat - start.lat) * 0.35],
    [start.lon + (target.lon - start.lon) * 0.42, start.lat + (target.lat - start.lat) * 0.58],
    [start.lon + (target.lon - start.lon) * 0.7, start.lat + (target.lat - start.lat) * 0.78],
    [target.lon, target.lat],
  ];
}

function syncMarkers() {
  if (!state.mapLoaded) return;
  const current = [state.currentPoint.lon, state.currentPoint.lat];
  const target = currentTarget();

  if (!state.userMarker) {
    const element = document.createElement("div");
    element.className = "user-map-marker";
    element.innerHTML = '<span class="material-symbols-rounded">navigation</span>';
    state.userMarker = new maplibregl.Marker({ element, rotationAlignment: "map" }).setLngLat(current).addTo(state.map);
  }
  state.userMarker.setLngLat(current);

  if (!state.destinationMarker) {
    const element = document.createElement("div");
    element.className = "destination-map-marker";
    element.innerHTML = '<span class="material-symbols-rounded">location_on</span>';
    state.destinationMarker = new maplibregl.Marker({ element, anchor: "bottom" }).setLngLat([target.lon, target.lat]).addTo(state.map);
  }
  state.destinationMarker.setLngLat([target.lon, target.lat]);
}

function syncCamera(options = {}) {
  if (!state.mapLoaded) return;
  const target = currentTarget();
  const bearing = Number.isFinite(target.lon) ? bearingBetween(state.currentPoint, target) - 8 : -18;
  state.map.easeTo({
    center: [state.currentPoint.lon, state.currentPoint.lat],
    zoom: state.trackingGps ? MAP_TRACKING_ZOOM : MAP_DEFAULT_ZOOM,
    pitch: 45,
    bearing: options.bearing ?? bearing,
    duration: options.instant ? 0 : 650,
  });
}

function setFreshness() {
  els.lastUpdated.textContent = state.lastUpdatedAt
    ? `Aggiornato ${state.lastUpdatedAt.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
    : "--";
}

function updateClock() {
  els.clock.textContent = new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
}

function updateNetworkStatus() {
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  if (!navigator.onLine) {
    els.networkLabel.textContent = "Offline";
    return;
  }
  els.networkLabel.textContent = connection?.effectiveType
    ? connection.effectiveType.toUpperCase()
    : "Online";
}

function weatherIconFor(code) {
  if (code === 0) return "clear_day";
  if ([1, 2, 3].includes(code)) return "partly_cloudy_day";
  if ([45, 48].includes(code)) return "foggy";
  if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return "rainy";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "weather_snowy";
  if ([95, 96, 99].includes(code)) return "thunderstorm";
  return "cloud";
}

async function updateWeather(point = state.currentPoint, force = false) {
  const key = `${point.lat.toFixed(2)},${point.lon.toFixed(2)}`;
  if (!force && state.weatherKey === key && Date.now() - state.weatherUpdatedAt < WEATHER_REFRESH_MS) return;
  state.weatherKey = key;
  state.weatherUpdatedAt = Date.now();

  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.search = new URLSearchParams({
    latitude: point.lat.toFixed(4),
    longitude: point.lon.toFixed(4),
    current: "temperature_2m,weather_code",
    timezone: "auto",
  }).toString();

  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Weather unavailable");
    const weather = await response.json();
    const current = weather.current || {};
    const temperature = Math.round(current.temperature_2m);
    if (Number.isFinite(temperature)) els.weatherTemp.textContent = `${temperature}°C`;
    els.weatherIcon.textContent = weatherIconFor(Number(current.weather_code));
  } catch {
    state.weatherUpdatedAt = 0;
    els.weatherTemp.textContent = "--°";
    els.weatherIcon.textContent = "cloud_off";
  }
}

function setSheet(name, open = true) {
  state.activeSheet = name;
  els.bottomSheet.classList.toggle("open", open);
  for (const [key, element] of Object.entries({
    navigation: els.navigationContent,
    parking: els.parkingContent,
    favorites: els.favoritesContent,
    settings: els.settingsContent,
  })) {
    element.classList.toggle("active", key === name);
  }
  els.tabNavigation.classList.toggle("active", name === "navigation" && !open);
  els.tabParking.classList.toggle("active", name === "parking" && open);
  els.tabFavorites.classList.toggle("active", name === "favorites" && open);
  els.sheetKicker.textContent = name === "settings" ? "Sistema" : name === "favorites" ? "Preferiti" : name === "navigation" ? "Navigazione" : "Parcheggi";
  els.sheetTitle.textContent = name === "settings" ? "Stato e demo" : name === "favorites" ? "Segmenti salvati" : name === "navigation" ? "Tratto corrente" : "Migliori vicino a te";
}

function renderDemoButtons() {
  els.demoPoints.replaceChildren();
  for (const point of demoPoints) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = point.label;
    button.className = point.id === state.currentPoint.id ? "active" : "";
    button.addEventListener("click", () => {
      state.trackingGps = false;
      els.gpsStatus.textContent = "GPS demo";
      setPoint(point);
    });
    els.demoPoints.appendChild(button);
  }
}

function renderDestinationOptions() {
  const previous = state.destinationSegmentId;
  els.destinationZone.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Auto";
  els.destinationZone.appendChild(placeholder);

  for (const segment of state.segments) {
    const option = document.createElement("option");
    option.value = segment.id;
    option.textContent = `${segment.street_name} · ${segment.parking_label}`;
    els.destinationZone.appendChild(option);
  }
  els.destinationZone.value = previous;
}

function chooseDestination(segmentId) {
  state.destinationSegmentId = segmentId;
  els.destinationZone.value = segmentId;
  syncMapSources();
  syncCamera();
  renderPanel();
}

function renderDestination() {
  const target = currentTarget();
  const heat = target.segment ? state.heatmap.get(target.segment.id) : null;
  const name = target.segment?.street_name || "Destinazione";
  const currentLabel = state.currentSegment && state.prediction
    ? `${state.currentSegment.street_name} · ${state.prediction.parkability_percent}% · ${state.currentSegment.parking_label}`
    : "Tratto non stimato";
  els.destinationFloatingLabel.textContent = currentLabel;
  els.destinationFloating.style.display = "inline-flex";
  els.arrivalAddress.textContent = target.segment ? `${name} · ${target.segment.parking_label}` : "Percorso demo";
  els.destinationResult.textContent = target.segment && heat
    ? `${name}: ${heat.parkability_percent}%, ${labels[heat.status] || heat.status}, ${target.segment.parking_label}.`
    : "";
}

async function loadScenarios() {
  const scenarios = await ingestionApi("/scenarios");
  els.scenarioButtons.replaceChildren();

  for (const scenario of scenarios) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = scenario.label;
    button.addEventListener("click", () => startScenario(scenario.id, scenario.label));
    els.scenarioButtons.appendChild(button);
  }

  const reset = document.createElement("button");
  reset.type = "button";
  reset.textContent = "Reset scenari";
  reset.addEventListener("click", resetScenarios);
  els.scenarioButtons.appendChild(reset);
}

function renderPanel() {
  const target = currentTarget();
  const routeMeters = Math.max(120, distanceMeters(state.currentPoint, target) * 1.25);
  const minutes = Math.max(3, Math.round(routeMeters / 420));
  const eta = new Date(Date.now() + minutes * 60000);
  const targetRoad = target.segment ? target.segment.street_name : "Via Garibaldi";

  els.nextDistance.textContent = formatDistance(Math.min(routeMeters * 0.34, 850));
  els.nextAction.textContent = bearingBetween(state.currentPoint, target) > 180 ? "Svolta a sinistra" : "Svolta a destra";
  els.nextRoad.textContent = targetRoad;
  els.followingAction.textContent = "Poi prosegui";
  els.followingRoad.textContent = target.segment?.parking_label || "Tratto parcheggio";
  els.followingDistance.textContent = formatDistance(Math.max(220, routeMeters * 0.55));
  els.arrivalTime.textContent = eta.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  els.arrivalMinutes.textContent = `${minutes} min`;
  els.arrivalDistance.textContent = formatDistance(routeMeters);

  if (!state.currentSegment || !state.prediction) {
    els.currentSummary.textContent = state.currentPoint.label || "Posizione corrente";
    els.zoneName.textContent = "Fuori area stimata";
    els.score.textContent = "--%";
    els.status.textContent = "--";
    els.trend.textContent = "--";
    els.searchTime.textContent = "--";
    els.confidence.textContent = "--";
    els.recommendation.textContent = state.trackingGps ? "Radar attivo, stime non disponibili in questa area." : "Scegli una zona demo o usa il GPS.";
    els.aiExplanation.textContent = "";
    renderNearby();
    renderDestination();
    renderFavorites();
    return;
  }

  const prediction = state.prediction;
  const meta = [
    state.currentSegment.parking_label,
    state.currentSegment.price_label,
    state.currentSegment.time_rules,
  ].filter(Boolean);
  els.currentSummary.textContent = `${state.currentSegment.street_name} · ${prediction.parkability_percent}% · ${state.currentSegment.parking_label}`;
  els.zoneName.textContent = state.currentSegment.street_name;
  els.score.textContent = `${prediction.parkability_percent}%`;
  els.status.textContent = labels[prediction.status] || prediction.status;
  els.trend.textContent = labels[prediction.trend] || prediction.trend;
  els.searchTime.textContent = `${prediction.estimated_search_time_min} min`;
  els.confidence.textContent = `${Math.round(prediction.confidence * 100)}%`;
  els.recommendation.textContent = `${meta.join(" · ")}. ${prediction.recommendation}`;
  els.aiExplanation.textContent = "";
  renderNearby();
  renderDestination();
  renderFavorites();
}

function renderNearby() {
  els.nearby.replaceChildren();
  const rows = state.nearby.slice(0, 5);
  for (const segment of rows) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const status = segment.prediction?.status || "uncertain";
    button.type = "button";
    button.innerHTML = `<i style="background:${colors[status] || colors.uncertain}"></i><span>${segment.street_name}<small>${formatDistance(segment.distance_m)} · ${segment.parking_label}</small></span><strong>${segment.prediction?.parkability_percent ?? "--"}%</strong>`;
    button.addEventListener("click", () => chooseDestination(segment.id));
    item.appendChild(button);
    els.nearby.appendChild(item);
  }
}

function renderFavorites() {
  els.favoriteList.replaceChildren();
  if (!state.favorites.length) {
    const empty = document.createElement("p");
    empty.textContent = "Nessun preferito salvato.";
    els.favoriteList.appendChild(empty);
    return;
  }

  for (const favorite of state.favorites) {
    const segment = state.segments.find((item) => item.id === favorite.id);
    if (!segment) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `<span>${segment.street_name}<small>${segment.parking_label}</small></span><strong class="material-symbols-rounded">near_me</strong>`;
    button.addEventListener("click", () => {
      state.destinationSegmentId = segment.id;
      els.destinationZone.value = segment.id;
      setSheet("parking", true);
      syncMapSources();
      syncCamera();
      renderPanel();
    });
    els.favoriteList.appendChild(button);
  }
}

async function loadAdminPanel() {
  const [health, events] = await Promise.all([
    api("/admin/source-health"),
    api("/admin/events?limit=5"),
  ]);

  els.sourceHealth.replaceChildren();
  for (const [name, value] of Object.entries({ DB: health.database, Redis: health.redis, RabbitMQ: health.rabbitmq })) {
    const chip = document.createElement("span");
    chip.className = `health-chip ${value === "up" ? "up" : ""}`;
    chip.textContent = `${name}: ${value}`;
    els.sourceHealth.appendChild(chip);
  }

  els.recentEvents.replaceChildren();
  for (const event of events.slice(0, 5)) {
    const item = document.createElement("li");
    item.textContent = `${event.event_type} · ${event.segment_id || event.zone_id || "n/d"}`;
    els.recentEvents.appendChild(item);
  }
}

async function refreshHeatmap() {
  const heatmap = await api("/segment-heatmap");
  state.heatmap = new Map(heatmap.segments.map((segment) => [segment.segment_id, segment]));
}

async function setPoint(point, options = {}) {
  const token = ++state.updateToken;
  state.currentPoint = point;
  renderDemoButtons();
  els.radarStatus.textContent = "Analisi";

  await refreshHeatmap();
  const update = await api(`/live-sessions/${state.session.session_id}/location`, {
    method: "POST",
    body: JSON.stringify({ lat: point.lat, lon: point.lon }),
  });
  if (token !== state.updateToken) return;

  state.currentSegment = update.current_segment;
  state.prediction = update.prediction;
  state.nearby = update.nearby_segments || [];
  state.lastUpdatedAt = new Date();
  els.radarStatus.textContent = "Radar live";
  updateWeather(point);
  syncMapSources();
  syncCamera(options);
  renderPanel();
  setFreshness();
  await loadAdminPanel();
}

function handleGpsPosition(position) {
  const { latitude, longitude, accuracy } = position.coords;
  state.trackingGps = true;
  els.gpsStatus.textContent = "GPS attivo";
  setPoint({ id: "gps", label: "La tua posizione", lat: latitude, lon: longitude, accuracy });
}

function handleGpsError(error) {
  const denied = error.code === error.PERMISSION_DENIED;
  els.gpsStatus.textContent = denied ? "GPS non autorizzato" : "GPS non disponibile";
}

function startGps() {
  if (!navigator.geolocation) {
    els.gpsStatus.textContent = "GPS non supportato";
    return;
  }
  els.gpsStatus.textContent = "Cerco GPS";
  navigator.geolocation.getCurrentPosition(handleGpsPosition, handleGpsError, GPS_OPTIONS);
  if (state.watchId === null) {
    state.watchId = navigator.geolocation.watchPosition(handleGpsPosition, handleGpsError, GPS_OPTIONS);
  }
}

async function sendReport(reportType) {
  if (!state.currentSegment) return;
  await api("/segment-reports", {
    method: "POST",
    body: JSON.stringify({
      segment_id: state.currentSegment.id,
      report_type: reportType,
      session_id: state.session?.session_id,
    }),
  });
  await setPoint(state.currentPoint, { instant: true });
}

async function explainCurrentZone() {
  if (!state.currentSegment || !state.prediction) return;
  const explanation = await aiApi("/ai/explain", {
    method: "POST",
    body: JSON.stringify({
      segment_id: state.currentSegment.id,
      segment_name: state.currentSegment.street_name,
      parkability_percent: state.prediction.parkability_percent,
      status: state.prediction.status,
      trend: state.prediction.trend,
      confidence: state.prediction.confidence,
      estimated_search_time_min: state.prediction.estimated_search_time_min,
      recommendation: state.prediction.recommendation,
    }),
  });
  els.aiExplanation.textContent = `${explanation.explanation} ${explanation.action}`;
}

async function startScenario(scenarioId, label) {
  els.scenarioStatus.textContent = "Pubblicazione eventi su RabbitMQ...";
  const result = await ingestionApi(`/scenarios/${scenarioId}/start`, { method: "POST" });
  els.scenarioStatus.textContent = `${label}: ${result.events_published} eventi pubblicati.`;
  await new Promise((resolve) => setTimeout(resolve, 900));
  await setPoint(state.currentPoint, { instant: true });
}

async function resetScenarios() {
  await api("/admin/demo-scenarios/reset", { method: "POST" });
  els.scenarioStatus.textContent = "Scenari e cache Redis azzerati.";
  await setPoint(state.currentPoint, { instant: true });
}

function addCurrentFavorite() {
  const segment = state.currentSegment;
  if (!segment || state.favorites.some((favorite) => favorite.id === segment.id)) return;
  state.favorites.push({ id: segment.id, saved_at: new Date().toISOString() });
  saveFavorites();
  renderFavorites();
}

function startRealtimeRefresh() {
  if (state.refreshTimer) return;
  state.refreshTimer = setInterval(() => {
    if (!document.hidden && state.session) setPoint(state.currentPoint, { instant: true });
  }, REFRESH_MS);
}

function startStatusRefresh() {
  updateNetworkStatus();
  updateWeather();
  window.addEventListener("online", updateNetworkStatus);
  window.addEventListener("offline", updateNetworkStatus);
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  connection?.addEventListener?.("change", updateNetworkStatus);
  setInterval(() => updateWeather(state.currentPoint, true), WEATHER_REFRESH_MS);
}

function bindEvents() {
  els.destinationZone.addEventListener("change", (event) => {
    state.destinationSegmentId = event.target.value;
    syncMapSources();
    syncCamera();
    renderPanel();
  });
  els.locateMe.addEventListener("click", startGps);
  els.recenterMap.addEventListener("click", () => syncCamera());
  els.zoomIn.addEventListener("click", () => state.map?.zoomIn());
  els.zoomOut.addEventListener("click", () => state.map?.zoomOut());
  els.destinationFloating.addEventListener("click", () => setSheet("parking", true));
  els.openMenu.addEventListener("click", () => setSheet("settings", true));
  els.tabNavigation.addEventListener("click", () => setSheet("navigation", false));
  els.tabParking.addEventListener("click", () => setSheet("parking", true));
  els.tabFavorites.addEventListener("click", () => setSheet("favorites", true));
  els.tabSettings.addEventListener("click", () => setSheet("settings", true));
  els.closeSheet.addEventListener("click", () => setSheet(state.activeSheet, false));
  els.foundSpot.addEventListener("click", () => sendReport("found_spot"));
  els.fullZone.addEventListener("click", () => sendReport("full_zone"));
  els.releasedSpot.addEventListener("click", () => sendReport("released_spot"));
  els.parkingClosed.addEventListener("click", () => sendReport("parking_closed"));
  els.explainAi.addEventListener("click", explainCurrentZone);
  els.saveFavorite.addEventListener("click", addCurrentFavorite);
}

async function init() {
  initMap();
  updateClock();
  setInterval(updateClock, 30000);
  startStatusRefresh();
  state.segments = await api("/segments");
  state.session = await api("/live-sessions/start", { method: "POST" });
  renderDestinationOptions();
  renderDemoButtons();
  bindEvents();
  await loadScenarios();
  await setPoint(state.currentPoint, { instant: true });
  setSheet("navigation", false);
  startRealtimeRefresh();
  startGps();
}

init().catch((error) => {
  console.error(error);
  els.radarStatus.textContent = "API non disponibile";
  els.zoneName.textContent = "Demo non avviata";
  els.recommendation.textContent = "Avvia Docker Compose e ricarica la pagina.";
});
