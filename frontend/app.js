const GATEWAY_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : window.location.origin;
const API_URL = `${GATEWAY_URL}/api/v1`;
const AI_URL = GATEWAY_URL;
const INGESTION_URL = `${GATEWAY_URL}/ingestion`;
const LOCAL_RADIUS_M = 500;
const REFRESH_MS = 20000;
const WEATHER_REFRESH_MS = 10 * 60 * 1000;
const PARKING_POI_REFRESH_MS = 10 * 60 * 1000;
const PARKING_POI_RADIUS_M = 500;
const TOMTOM_PREDICTION_REFRESH_MS = 5 * 60 * 1000;
const TOMTOM_PREDICTION_SETTLE_MS = 700;
const ROAD_NETWORK_RADIUS_M = 700;
const DATA_REFRESH_DEBOUNCE_MS = 180;
const TOMTOM_POI_TEST_CELLS = 3;
const KEYBOARD_MOVE_M = 22;
const KEYBOARD_TURN_DEGREES = 24;
const KEYBOARD_REPEAT_MS = 110;
const KEYBOARD_ANIMATION_MS = 230;
const ROAD_SNAP_RADIUS_M = 85;
const CLICK_DRIVE_ANIMATION_MS = 450;
const SIMULATION_STEP_MS = 420;
const SIMULATION_ANIMATION_MS = 560;
const SIMULATION_SPACING_M = 6;
const SIMULATION_DATA_REFRESH_EVERY = 10;
const AI_AUTO_DEBOUNCE_MS = 220;
const GPS_OPTIONS = { enableHighAccuracy: true, maximumAge: 8000, timeout: 10000 };
const PMTILES_URL = new URL("/assets/catania.pmtiles", window.location.href).href;
const FAVORITES_KEY = "parcheggia:favorites";
const THEME_KEY = "parcheggia:theme";
const TTS_MUTED_KEY = "parcheggia:tts-muted";
const MAP_DEFAULT_ZOOM = 18.6;
const MAP_TRACKING_ZOOM = 19.1;

const demoPoints = [
  { id: "stesicoro", label: "Stesicoro", lat: 37.507, lon: 15.083 },
  { id: "borgo", label: "Borgo", lat: 37.525, lon: 15.071 },
  { id: "sanzio", label: "Sanzio", lat: 37.521, lon: 15.083 },
  { id: "europa", label: "Europa", lat: 37.519, lon: 15.104 },
];

const simulationRoute = [
  [15.0830503, 37.5070732],
  [15.082374, 37.506974],
  [15.0816438, 37.5068901],
  [15.081009, 37.5070795],
  [15.080297, 37.507413],
  [15.0794698, 37.5073467],
  [15.0791621, 37.5069917],
  [15.0786083, 37.5062012],
  [15.0784916, 37.506047],
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
  lastSegmentClickAt: 0,
  userMarker: null,
  destinationMarker: null,
  parkingPois: [],
  parkingPoiMarkers: new Map(),
  visiblePoiIds: new Set(),
  parkingPoiFetchKey: "",
  parkingPoiFetchAt: 0,
  tomtomPredictionFetchKey: "",
  tomtomPredictionFetchAt: 0,
  roadEdges: [],
  roadNetworkFetchKey: "",
  pointRefreshTimer: null,
  simulationTimer: null,
  simulationActive: false,
  driveBearing: -18,
  lastKeyboardMoveAt: 0,
  trackingGps: false,
  watchId: null,
  lastUpdatedAt: null,
  refreshTimer: null,
  updateToken: 0,
  weatherKey: "",
  weatherUpdatedAt: 0,
  aiSuggestion: null,
  aiSuggestionKey: "",
  aiSuggestionLoading: false,
  aiAutoTimer: null,
  aiHudClosedKey: "",
  aiSpeechSerial: 0,
  aiAudio: null,
  aiAudioUrl: "",
  aiTargetSegmentIds: new Set(),
  aiTargetParkingPoiIds: new Set(),
  aiTargetSegmentMarkers: new Map(),
  lastAiSegmentId: "",
  lastAiPercent: null,
  lastAutoAiKey: "",
  theme: loadTheme(),
  ttsMuted: localStorage.getItem(TTS_MUTED_KEY) === "1",
  activeSheet: "navigation",
  favorites: loadFavorites(),
};

const els = {
  map: document.querySelector("#map"),
  clock: document.querySelector("#clock"),
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
  aiDriveCard: document.querySelector("#ai-drive-card"),
  aiHudTitle: document.querySelector("#ai-hud-title"),
  aiHudText: document.querySelector("#ai-hud-text"),
  aiHudScore: document.querySelector("#ai-hud-score"),
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
  shell: document.querySelector(".drive-shell"),
  tomtomPoiStatus: document.querySelector("#tomtom-poi-status"),
  tomtomSearchBudget: document.querySelector("#tomtom-search-budget"),
  tomtomPredictionStatus: document.querySelector("#tomtom-prediction-status"),
  tomtomTrafficBudget: document.querySelector("#tomtom-traffic-budget"),
  testTomtomPois: document.querySelector("#test-tomtom-pois"),
  driveSimulation: document.querySelector("#drive-simulation"),
  themeToggle: document.querySelector("#theme-toggle"),
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

function loadTheme() {
  return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify(state.favorites));
}

function mapThemePaints(theme = state.theme) {
  if (theme === "light") {
    return {
      name: "ParcheggIA Light Catania",
      background: "#edf3f8",
      earth: "#e7eef4",
      natural: "#d9eadf",
      landuse: "#dfeee8",
      water: "#bdd8ec",
      roadCasing: "#d1dbe5",
      road: "#fbfcfe",
      buildings: "#d6dee7",
    };
  }
  return {
    name: "ParcheggIA Dark Catania",
    background: "#0b1420",
    earth: "#162330",
    natural: "#17342e",
    landuse: "#1d3740",
    water: "#0b2637",
    roadCasing: "#111923",
    road: "#415160",
    buildings: "#253443",
  };
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.style.colorScheme = state.theme;
  syncThemeToggle();
  if (!state.mapLoaded) return;
  const paint = mapThemePaints();
  for (const [layer, property, value] of [
    ["background", "background-color", paint.background],
    ["earth", "fill-color", paint.earth],
    ["natural", "fill-color", paint.natural],
    ["landuse", "fill-color", paint.landuse],
    ["water", "fill-color", paint.water],
    ["roads-casing", "line-color", paint.roadCasing],
    ["roads", "line-color", paint.road],
    ["buildings", "fill-color", paint.buildings],
  ]) {
    if (state.map.getLayer(layer)) state.map.setPaintProperty(layer, property, value);
  }
}

function toggleTheme() {
  state.theme = state.theme === "light" ? "dark" : "light";
  localStorage.setItem(THEME_KEY, state.theme);
  applyTheme();
}

function syncThemeToggle() {
  if (!els.themeToggle) return;
  els.themeToggle.textContent = state.theme === "light" ? "Tema scuro" : "Tema chiaro";
}

function syncSoundToggle() {
  if (!els.soundToggle) return;
  const icon = els.soundToggle.querySelector(".material-symbols-rounded");
  if (icon) icon.textContent = state.ttsMuted ? "volume_off" : "volume_up";
  els.soundToggle.setAttribute("aria-pressed", String(!state.ttsMuted));
  els.soundToggle.setAttribute("aria-label", state.ttsMuted ? "Riattiva voce" : "Disattiva voce");
  els.soundToggle.title = state.ttsMuted ? "Riattiva voce" : "Disattiva voce";
}

function toggleTts() {
  state.ttsMuted = !state.ttsMuted;
  localStorage.setItem(TTS_MUTED_KEY, state.ttsMuted ? "1" : "0");
  if (state.ttsMuted) stopTtsPlayback();
  syncSoundToggle();
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

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function currentAiKey() {
  if (!state.currentSegment || !state.prediction) return "";
  return `${state.currentSegment.id}:${state.prediction.parkability_percent}:${state.prediction.status}`;
}

function parkingPoiId(poi) {
  return String(poi?.id || `${poi?.lat},${poi?.lon}`);
}

function segmentTargetPoint(segmentId) {
  const heat = state.heatmap.get(segmentId);
  const segment = state.segments.find((item) => item.id === segmentId)
    || state.nearby.find((item) => item.id === segmentId);
  const geometry = heat?.line || segment?.geometry;
  return geometry ? lineLabelPoint(geometry) : null;
}

function syncAiTargetMarkers() {
  if (!state.mapLoaded) return;

  for (const segmentId of state.aiTargetSegmentIds) {
    const point = segmentTargetPoint(segmentId);
    if (!point) continue;
    let marker = state.aiTargetSegmentMarkers.get(segmentId);
    if (!marker) {
      const element = document.createElement("div");
      element.className = "ai-target-segment-marker";
      marker = new maplibregl.Marker({ element, anchor: "center" }).setLngLat(point).addTo(state.map);
      state.aiTargetSegmentMarkers.set(segmentId, marker);
    }
    marker.setLngLat(point);
  }

  for (const [segmentId, marker] of state.aiTargetSegmentMarkers) {
    if (!state.aiTargetSegmentIds.has(segmentId) || !segmentTargetPoint(segmentId)) {
      marker.remove();
      state.aiTargetSegmentMarkers.delete(segmentId);
    }
  }

  for (const [poiId, marker] of state.parkingPoiMarkers) {
    marker.getElement().classList.toggle("ai-target", state.aiTargetParkingPoiIds.has(poiId));
  }
}

function clearAiTargets() {
  state.aiTargetSegmentIds.clear();
  state.aiTargetParkingPoiIds.clear();
  for (const marker of state.aiTargetSegmentMarkers.values()) marker.remove();
  state.aiTargetSegmentMarkers.clear();
  for (const marker of state.parkingPoiMarkers.values()) marker.getElement().classList.remove("ai-target");
}

function applyAiTargets(explanation) {
  state.aiTargetSegmentIds = new Set(
    (explanation.target_segment_ids || [])
      .map(String)
      .filter((id) => Boolean(segmentTargetPoint(id))),
  );
  state.aiTargetParkingPoiIds = new Set(
    (explanation.target_parking_poi_ids || [])
      .map(String)
      .filter((id) => state.parkingPois.some((poi) => parkingPoiId(poi) === id)),
  );
  syncAiTargetMarkers();
}

function clearAiSuggestion() {
  els.aiExplanation.replaceChildren();
  els.aiExplanation.hidden = true;
  state.aiHudClosedKey = "";
  clearAiTargets();
}

function resetAiSuggestion() {
  state.aiSuggestion = null;
  state.aiSuggestionKey = "";
  state.aiHudClosedKey = "";
  state.lastAiSegmentId = "";
  state.lastAiPercent = null;
  window.clearTimeout(state.aiAutoTimer);
  stopTtsPlayback();
  clearAiSuggestion();
  syncAiHud();
}

function syncAiHud() {
  if (!els.aiDriveCard) return;
  const key = currentAiKey();
  const hasSuggestion = state.aiSuggestion && state.aiSuggestionKey === key;
  const hasSegment = Boolean(key);
  const closed = !state.aiSuggestionLoading && hasSuggestion && state.aiHudClosedKey === key;
  els.aiDriveCard.hidden = !hasSegment || closed || (!state.aiSuggestionLoading && !hasSuggestion);
  if (els.aiDriveCard.hidden) {
    els.aiDriveCard.classList.remove("closing");
    return;
  }

  els.aiDriveCard.classList.toggle("loading", state.aiSuggestionLoading);
  els.aiDriveCard.classList.toggle("has-suggestion", Boolean(hasSuggestion));
  els.aiHudScore.textContent = state.prediction ? `${state.prediction.parkability_percent}%` : "--%";

  if (state.aiSuggestionLoading && !hasSuggestion) {
    els.aiHudTitle.textContent = "Analisi";
    els.aiHudText.textContent = "Sto valutando il tratto corrente";
    return;
  }

  if (hasSuggestion) {
    els.aiHudTitle.textContent = "Suggerimento";
    els.aiHudText.textContent = state.aiSuggestion.action || state.aiSuggestion.summary || "Suggerimento disponibile";
    return;
  }

  els.aiHudTitle.textContent = "Suggerimento";
  els.aiHudText.textContent = "Analizza il tratto corrente";
}

function syncAiSuggestionForCurrentSegment() {
  const key = currentAiKey();
  const segmentId = state.currentSegment?.id || "";
  const percent = state.prediction?.parkability_percent ?? null;
  const shouldAutoSuggest = Boolean(
    state.lastAiSegmentId
    && segmentId
    && segmentId !== state.lastAiSegmentId
    && percent !== state.lastAiPercent
    && key !== state.lastAutoAiKey,
  );

  if (state.aiSuggestionKey && state.aiSuggestionKey !== key) {
    state.aiSuggestion = null;
    state.aiSuggestionKey = "";
    clearAiSuggestion();
  }
  state.lastAiSegmentId = segmentId;
  state.lastAiPercent = percent;
  syncAiHud();
  if (shouldAutoSuggest) scheduleAutoAiSuggestion(key);
}

function scheduleAutoAiSuggestion(key) {
  window.clearTimeout(state.aiAutoTimer);
  state.aiAutoTimer = window.setTimeout(() => {
    if (currentAiKey() !== key || (state.aiSuggestion && state.aiSuggestionKey === key)) return;
    state.lastAutoAiKey = key;
    explainCurrentZone({ automatic: true });
  }, AI_AUTO_DEBOUNCE_MS);
}

function playAiHudDrop() {
  if (!els.aiDriveCard) return;
  els.aiDriveCard.classList.remove("dot-drop", "closing");
  void els.aiDriveCard.offsetWidth;
  els.aiDriveCard.classList.add("dot-drop");
}

function playAiHudReveal() {
  if (!els.aiDriveCard) return;
  els.aiDriveCard.classList.remove("suggestion-pop", "closing");
  void els.aiDriveCard.offsetWidth;
  els.aiDriveCard.classList.add("suggestion-pop");
}

function closeAiHudAfterSpeech(key) {
  if (!els.aiDriveCard || key !== currentAiKey() || state.aiSuggestionKey !== key || els.aiDriveCard.hidden) return;
  els.aiDriveCard.classList.remove("suggestion-pop", "dot-drop");
  els.aiDriveCard.classList.add("closing");
  window.setTimeout(() => {
    if (key !== currentAiKey() || state.aiSuggestionKey !== key) return;
    state.aiHudClosedKey = key;
    els.aiDriveCard.classList.remove("closing");
    syncAiHud();
  }, 420);
}

function cleanParkingAddress(value) {
  const parts = String(value || "")
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part && !/^\d{5}\b/.test(part) && !/^(catania(?:\s+ct)?|ct|italia|italy)$/i.test(part));
  return parts
    .join(", ")
    .replace(/(?:,\s*)?\b\d{5}\s+Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$/i, "")
    .replace(/(?:,\s*)?Catania(?:\s+CT)?(?:,\s*(?:Italia|Italy))?$/i, "")
    .replace(/(?:,\s*)?(?:Italia|Italy)$/i, "")
    .trim();
}

function parkingPoiPlace(poi) {
  return (cleanParkingAddress(poi?.address) || cleanParkingAddress(poi?.name) || "Parcheggio")
    .replace(/\s+(parking|parcheggio|garage)\s*$/i, "")
    .trim();
}

function aiLocalContext() {
  const segmentContext = (segment) => {
    const prediction = segment.prediction || predictionForSegment(segment.id) || {};
    const heat = state.heatmap.get(segment.id) || {};
    const distance = segment.distance_m ?? (segment.geometry ? distanceMeters(state.currentPoint, segmentCenter(segment)) : 0);
    return {
      id: segment.id,
      street_name: segment.street_name,
      distance_m: Math.round(distance),
      parking_type: segment.parking_type,
      parking_label: segment.parking_label,
      price_label: segment.price_label,
      time_rules: segment.time_rules,
      parkability_percent: prediction.parkability_percent ?? heat.parkability_percent,
      status: prediction.status ?? heat.status,
      confidence: prediction.confidence,
      trend: prediction.trend,
      estimated_search_time_min: prediction.estimated_search_time_min,
      recommendation: prediction.recommendation,
    };
  };

  return {
    current_point: {
      lat: Number(state.currentPoint.lat.toFixed(6)),
      lon: Number(state.currentPoint.lon.toFixed(6)),
      heading_degrees: Math.round(normalizeBearing(state.driveBearing)),
      local_radius_m: LOCAL_RADIUS_M,
    },
    current_segment: {
      id: state.currentSegment.id,
      street_name: state.currentSegment.street_name,
      parking_type: state.currentSegment.parking_type,
      parking_label: state.currentSegment.parking_label,
      price_label: state.currentSegment.price_label,
      time_rules: state.currentSegment.time_rules,
      parkability_percent: state.prediction?.parkability_percent,
      status: state.prediction?.status,
      confidence: state.prediction?.confidence,
      trend: state.prediction?.trend,
      estimated_search_time_min: state.prediction?.estimated_search_time_min,
      recommendation: state.prediction?.recommendation,
    },
    nearby_segments: state.nearby.slice(0, 12).map(segmentContext),
    heatmap_segments: localHeatSegments().slice(0, 16).map((item) => segmentContext({ ...item.segment, distance_m: item.distance })),
    parking_pois: state.parkingPois.slice(0, 8).map((poi) => ({
      id: parkingPoiId(poi),
      name: poi.name || "Parcheggio",
      distance_m: Math.round(poi.distance_m || 0),
      address: cleanParkingAddress(poi.address || poi.name),
      type: poi.category || poi.type,
      parking_kind: poi.parking_kind,
      lat: Number(poi.lat?.toFixed?.(6) ?? poi.lat),
      lon: Number(poi.lon?.toFixed?.(6) ?? poi.lon),
    })),
    destination: state.destinationSegmentId || null,
  };
}

function aiSpeechText(explanation) {
  return (explanation.action || explanation.summary || "").trim();
}

function stopTtsPlayback() {
  state.aiSpeechSerial += 1;
  window.speechSynthesis?.cancel?.();
  if (state.aiAudio) {
    state.aiAudio.pause();
    state.aiAudio.src = "";
    state.aiAudio = null;
  }
  if (state.aiAudioUrl) {
    URL.revokeObjectURL(state.aiAudioUrl);
    state.aiAudioUrl = "";
  }
}

function speakBrowserSuggestion(text, speechKey, serial) {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  const italianVoices = voices.filter((voice) => voice.lang?.toLowerCase().startsWith("it"));
  const preferred = italianVoices.find((voice) => /google|alice|samantha|premium|enhanced/i.test(voice.name)) || italianVoices[0];
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "it-IT";
  if (preferred) utterance.voice = preferred;
  utterance.rate = 0.96;
  utterance.pitch = 1.02;
  utterance.onend = () => {
    if (!state.ttsMuted && serial === state.aiSpeechSerial) closeAiHudAfterSpeech(speechKey);
  };
  window.speechSynthesis.speak(utterance);
}

async function speakAiSuggestion(explanation) {
  if (state.ttsMuted || document.hidden) return;
  const text = aiSpeechText(explanation);
  if (!text) return;
  const speechKey = state.aiSuggestionKey;
  const serial = ++state.aiSpeechSerial;
  stopTtsPlayback();
  state.aiSpeechSerial = serial;

  try {
    const response = await fetch(`${AI_URL}/ai/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error("ElevenLabs TTS unavailable");
    const audioUrl = URL.createObjectURL(await response.blob());
    const audio = new Audio(audioUrl);
    state.aiAudio = audio;
    state.aiAudioUrl = audioUrl;
    audio.onended = () => {
      if (!state.ttsMuted && serial === state.aiSpeechSerial) closeAiHudAfterSpeech(speechKey);
      if (state.aiAudio === audio) {
        state.aiAudio = null;
        URL.revokeObjectURL(audioUrl);
        state.aiAudioUrl = "";
      }
    };
    audio.onerror = () => {
      if (serial === state.aiSpeechSerial) speakBrowserSuggestion(text, speechKey, serial);
    };
    await audio.play();
  } catch {
    if (!state.ttsMuted && serial === state.aiSpeechSerial) speakBrowserSuggestion(text, speechKey, serial);
  }
}

function renderAiSuggestion(explanation, options = {}) {
  if (!explanation || explanation.model === "rule-based-fallback") {
    state.aiSuggestion = null;
    state.aiSuggestionKey = "";
    clearAiSuggestion();
    syncAiHud();
    return;
  }
  const badge = explanation.model === "simulated-fallback" ? "Simulazione" : "Suggerimento";
  const cached = explanation.cached ? " · cache" : "";
  const percent = state.prediction ? `${state.prediction.parkability_percent}%` : "--%";
  const summary = explanation.summary || explanation.explanation || "Suggerimento non disponibile.";
  state.aiSuggestion = explanation;
  state.aiSuggestionKey = currentAiKey();
  state.aiHudClosedKey = "";
  applyAiTargets(explanation);
  els.aiExplanation.hidden = false;
  els.aiExplanation.innerHTML = `
    <div class="ai-card-head">
      <span>${badge}${cached}</span>
      <strong>${escapeHtml(percent)}</strong>
    </div>
    <p class="ai-card-summary">${escapeHtml(summary)}</p>
    <div class="ai-card-grid">
      <div><span>Prossima mossa</span><p>${escapeHtml(explanation.action || "--")}</p></div>
      <div><span>Perche</span><p>${escapeHtml(explanation.reason || explanation.explanation || "--")}</p></div>
      <div><span>Rischio</span><p>${escapeHtml(explanation.risk || "--")}</p></div>
    </div>
    ${explanation.caveat ? `<small>${escapeHtml(explanation.caveat)}</small>` : ""}
  `;
  syncAiHud();
  if (options.animate !== false) playAiHudReveal();
  if (options.speak !== false) speakAiSuggestion(explanation);
}

function bboxAround(point, radiusM = LOCAL_RADIUS_M) {
  const latDelta = radiusM / 111320;
  const lonDelta = radiusM / (111320 * Math.max(0.2, Math.cos((point.lat * Math.PI) / 180)));
  return [
    point.lon - lonDelta,
    point.lat - latDelta,
    point.lon + lonDelta,
    point.lat + latDelta,
  ].map((value) => value.toFixed(6)).join(",");
}

function localCellKey(point, cellM = 250) {
  const latStep = cellM / 111320;
  const lonStep = cellM / (111320 * Math.max(0.2, Math.cos((point.lat * Math.PI) / 180)));
  return `${Math.floor(point.lat / latStep)}:${Math.floor(point.lon / lonStep)}`;
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
  const paint = mapThemePaints();
  return {
    version: 8,
    name: paint.name,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: {
      catania: {
        type: "vector",
        url: `pmtiles://${PMTILES_URL}`,
        attribution: "&copy; OpenStreetMap contributors",
      },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": paint.background } },
      { id: "earth", type: "fill", source: "catania", "source-layer": "earth", paint: { "fill-color": paint.earth } },
      { id: "natural", type: "fill", source: "catania", "source-layer": "natural", paint: { "fill-color": paint.natural, "fill-opacity": 0.38 } },
      { id: "landuse", type: "fill", source: "catania", "source-layer": "landuse", paint: { "fill-color": paint.landuse, "fill-opacity": 0.24 } },
      { id: "water", type: "fill", source: "catania", "source-layer": "water", paint: { "fill-color": paint.water } },
      {
        id: "roads-casing",
        type: "line",
        source: "catania",
        "source-layer": "roads",
        paint: {
          "line-color": paint.roadCasing,
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
          "line-color": paint.road,
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
        paint: { "fill-color": paint.buildings, "fill-opacity": 0.58 },
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
    applyTheme();
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
    map.addSource("parking-badge-source", { type: "geojson", data: emptyCollection() });
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
      id: "parking-segment-marker-rings",
      type: "circle",
      source: "parking-badge-source",
      minzoom: 17,
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 17, 14, 18.5, 19],
        "circle-color": "rgba(8,15,25,0.88)",
        "circle-opacity": ["interpolate", ["linear"], ["get", "confidence"], 0.3, 0.62, 0.65, 0.78, 0.95, 0.94],
        "circle-stroke-color": [
          "match",
          ["get", "parking_type"],
          "blue",
          "#2f8cff",
          "probable_free",
          "#eaf7ff",
          "restricted",
          "#ff5966",
          "#ffd447",
        ],
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 17, 4, 18.5, 6],
        "circle-stroke-opacity": 0.96,
      },
    });
    map.addLayer({
      id: "parking-segment-marker-percent",
      type: "symbol",
      source: "parking-badge-source",
      minzoom: 17,
      layout: {
        "text-field": ["get", "percent_label"],
        "text-font": ["Open Sans Semibold", "Arial Unicode MS Bold"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 17, 10, 18.5, 12],
        "text-allow-overlap": false,
        "text-ignore-placement": false,
      },
      paint: {
        "text-color": "#f8fbff",
        "text-halo-color": "rgba(3,8,14,0.72)",
        "text-halo-width": 1.6,
        "text-halo-blur": 0.4,
        "text-opacity": ["interpolate", ["linear"], ["zoom"], 16.8, 0, 17.3, 0.82, 18.5, 0.95],
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
        state.lastSegmentClickAt = performance.now();
        driveToMapPoint(event.lngLat);
      });
      map.on("click", (event) => {
        if (performance.now() - state.lastSegmentClickAt < 80) return;
        driveToMapPoint(event.lngLat);
      });
      map.on("mouseenter", "parking-segments-hit", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "parking-segments-hit", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("moveend", syncParkingPoiMarkers);
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
  const badgeSource = state.map.getSource("parking-badge-source");
  const routeSource = state.map.getSource("route-source");
  if (!heatSource || !segmentSource || !badgeSource || !routeSource) return;

  heatSource.setData(heatFeatures());
  segmentSource.setData(segmentFeatures());
  badgeSource.setData(segmentMarkerFeatures());
  routeSource.setData(routeFeature());
  syncMarkers();
  syncAiTargetMarkers();
  syncRouteUi();
}

function syncRouteUi() {
  els.shell?.classList.toggle("route-active", Boolean(state.destinationSegmentId));
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

function lineLabelPoint(geometry) {
  const coordinates = geometry?.coordinates || [];
  if (coordinates.length < 2) return coordinates[0] || [state.currentPoint.lon, state.currentPoint.lat];
  const sampled = sampleLineCoordinates(coordinates, 18);
  return sampled[Math.floor(sampled.length / 2)];
}

function normalizeBearing(degrees) {
  return (degrees + 360) % 360;
}

function bearingDelta(a, b) {
  return Math.abs(((a - b + 540) % 360) - 180);
}

function coordinateToMeters(origin, coordinate) {
  const scale = 111320 * Math.max(0.2, Math.cos((origin.lat * Math.PI) / 180));
  return {
    x: (coordinate[0] - origin.lon) * scale,
    y: (coordinate[1] - origin.lat) * 111320,
  };
}

function metersToPoint(origin, meters) {
  const scale = 111320 * Math.max(0.2, Math.cos((origin.lat * Math.PI) / 180));
  return {
    id: "keyboard",
    label: "Test tastiera",
    lat: origin.lat + meters.y / 111320,
    lon: origin.lon + meters.x / scale,
  };
}

function closestPointOnLine(point, coordinates, intendedBearing) {
  let best = null;
  for (let index = 1; index < coordinates.length; index += 1) {
    const start = coordinateToMeters(point, coordinates[index - 1]);
    const end = coordinateToMeters(point, coordinates[index]);
    const vx = end.x - start.x;
    const vy = end.y - start.y;
    const lengthSq = vx * vx + vy * vy;
    if (!lengthSq) continue;
    const ratio = Math.max(0, Math.min(1, -(start.x * vx + start.y * vy) / lengthSq));
    const projection = { x: start.x + vx * ratio, y: start.y + vy * ratio };
    const distance = Math.hypot(projection.x, projection.y);
    const segmentBearing = bearingBetween(
      { lon: coordinates[index - 1][0], lat: coordinates[index - 1][1] },
      { lon: coordinates[index][0], lat: coordinates[index][1] },
    );
    const reverseBearing = normalizeBearing(segmentBearing + 180);
    const forwardDelta = bearingDelta(segmentBearing, intendedBearing);
    const reverseDelta = bearingDelta(reverseBearing, intendedBearing);
    const bearing = forwardDelta <= reverseDelta ? segmentBearing : reverseBearing;
    const anglePenalty = Math.min(forwardDelta, reverseDelta) * 0.55;
    const score = distance + anglePenalty;
    if (!best || score < best.score) {
      best = { point: metersToPoint(point, projection), distance, bearing, score };
    }
  }
  return best;
}

function candidateRoadSegments(point) {
  return state.roadEdges.filter((edge) => edge.geometry?.coordinates?.length >= 2);
}

function snapPointToRoad(point, intendedBearing) {
  let best = null;
  for (const segment of candidateRoadSegments(point)) {
    const snap = closestPointOnLine(point, segment.geometry.coordinates, intendedBearing);
    if (snap && (!best || snap.score < best.score)) best = snap;
  }
  return best && best.distance <= ROAD_SNAP_RADIUS_M
    ? { ...best.point, bearing: best.bearing }
    : { ...point, bearing: intendedBearing, offRoad: true };
}

function driveToMapPoint(lngLat) {
  stopDriveSimulation();
  stopGpsWatch();
  state.trackingGps = false;
  const target = { id: "click", label: "Punto scelto", lat: lngLat.lat, lon: lngLat.lng };
  const intendedBearing = bearingBetween(state.currentPoint, target);
  const nextPoint = snapPointToRoad(target, intendedBearing);
  if (nextPoint.offRoad) {
    els.gpsStatus.textContent = "Fuori strada";
    return;
  }
  state.driveBearing = nextPoint.bearing;
  els.gpsStatus.textContent = "Click su strada";
  setPoint(nextPoint, { debounce: true, duration: CLICK_DRIVE_ANIMATION_MS, bearing: state.driveBearing }).catch((error) => console.error(error));
}

function stopDriveSimulation() {
  if (state.simulationTimer) clearInterval(state.simulationTimer);
  state.simulationTimer = null;
  state.simulationActive = false;
  els.driveSimulation?.classList.remove("active");
  if (els.driveSimulation) els.driveSimulation.textContent = "Simula guida 500 m";
}

function simulationPoints() {
  return sampleLineCoordinates(simulationRoute, SIMULATION_SPACING_M).map(([lon, lat], index) => ({
    id: `simulation-${index}`,
    label: "Simulazione guida",
    lon,
    lat,
  }));
}

function startDriveSimulation() {
  if (state.simulationActive) {
    stopDriveSimulation();
    return;
  }

  stopGpsWatch();
  state.trackingGps = false;
  state.destinationSegmentId = "";
  if (els.destinationZone) els.destinationZone.value = "";
  syncRouteUi();
  syncMapSources();
  els.gpsStatus.textContent = "Simulazione guida";
  els.driveSimulation?.classList.add("active");
  if (els.driveSimulation) els.driveSimulation.textContent = "Ferma simulazione";

  const points = simulationPoints();
  let index = 0;
  state.simulationActive = true;

  const step = () => {
    if (index >= points.length) {
      stopDriveSimulation();
      return;
    }
    const point = points[index];
    const next = points[Math.min(index + 1, points.length - 1)];
    const intendedBearing = index < points.length - 1 ? bearingBetween(point, next) : state.driveBearing;
    const snapped = snapPointToRoad(point, intendedBearing);
    const drivePoint = snapped.offRoad ? { ...point, bearing: intendedBearing } : { ...snapped, id: point.id, label: point.label };
    state.driveBearing = drivePoint.bearing;
    const refreshData = index === 0 || index % SIMULATION_DATA_REFRESH_EVERY === 0 || index === points.length - 1;
    setPoint(drivePoint, {
      debounce: refreshData,
      duration: SIMULATION_ANIMATION_MS,
      bearing: state.driveBearing,
      skipPoiRefresh: !refreshData,
      visualOnly: !refreshData,
    }).catch((error) => console.error(error));
    index += 1;
  };

  step();
  state.simulationTimer = setInterval(step, SIMULATION_STEP_MS);
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
      const prediction = predictionForSegment(item.segment.id);
      const percent = heat.parkability_percent ?? prediction?.parkability_percent ?? 50;
      return {
        type: "Feature",
        geometry: heat.line || item.segment.geometry,
        properties: {
          segment_id: item.segment.id,
          street_name: item.segment.street_name,
          parking_type: item.segment.parking_type,
          parkability_percent: percent,
          status: heat.status || "uncertain",
          confidence: prediction?.confidence ?? 0.55,
          active: item.segment.id === state.currentSegment?.id,
        },
      };
    }),
  };
}

function segmentMarkerFeatures() {
  return {
    type: "FeatureCollection",
    features: localHeatSegments().map((item) => {
      const heat = state.heatmap.get(item.segment.id) || {};
      const prediction = predictionForSegment(item.segment.id);
      const percent = heat.parkability_percent ?? prediction?.parkability_percent ?? 50;
      const geometry = heat.line || item.segment.geometry;
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: lineLabelPoint(geometry) },
        properties: {
          segment_id: item.segment.id,
          parking_type: item.segment.parking_type,
          percent_label: `${percent}%`,
          confidence: prediction?.confidence ?? 0.55,
        },
      };
    }),
  };
}

function routeFeature() {
  if (!state.destinationSegmentId) return emptyCollection();
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
    state.userMarker = new maplibregl.Marker({ element, rotationAlignment: "map", pitchAlignment: "map" }).setLngLat(current).addTo(state.map);
  }
  state.userMarker.setLngLat(current);
  syncUserMarkerHeading();

  if (!state.destinationSegmentId) {
    if (state.destinationMarker) {
      state.destinationMarker.remove();
      state.destinationMarker = null;
    }
    syncParkingPoiMarkers();
    return;
  }

  if (!state.destinationMarker) {
    const element = document.createElement("div");
    element.className = "destination-map-marker";
    element.innerHTML = '<span class="material-symbols-rounded">location_on</span>';
    state.destinationMarker = new maplibregl.Marker({ element, anchor: "bottom" }).setLngLat([target.lon, target.lat]).addTo(state.map);
  }
  state.destinationMarker.setLngLat([target.lon, target.lat]);
  syncParkingPoiMarkers();
}

function applyPoiMarkerClass(element, poi) {
  const distance = poi.distance_m ?? distanceMeters(state.currentPoint, poi);
  const kind = poi.parking_kind === "parking_garage" ? "garage" : "open";
  const id = parkingPoiId(poi);
  element.classList.add("parking-poi-marker");
  element.classList.toggle("garage", kind === "garage");
  element.classList.toggle("open", kind === "open");
  element.classList.toggle("far", distance > 520);
  element.classList.toggle("near", distance <= 520);
  element.classList.toggle("ai-target", state.aiTargetParkingPoiIds.has(id));
}

function syncParkingPoiMarkers() {
  if (!state.mapLoaded) return;
  const liveIds = new Set();
  const bounds = state.map.getBounds();
  const nextVisibleIds = new Set();
  for (const poi of state.parkingPois) {
    if (!Number.isFinite(poi.lat) || !Number.isFinite(poi.lon)) continue;
    const id = parkingPoiId(poi);
    liveIds.add(id);
    let marker = state.parkingPoiMarkers.get(id);
    const isNew = !marker;
    const isVisible = bounds?.contains([poi.lon, poi.lat]) ?? false;
    const becameVisible = isVisible && !state.visiblePoiIds.has(id);
    if (!marker) {
      const element = document.createElement("div");
      element.innerHTML = '<span class="material-symbols-rounded">local_parking</span>';
      marker = new maplibregl.Marker({ element, anchor: "bottom" }).setLngLat([poi.lon, poi.lat]).addTo(state.map);
      state.parkingPoiMarkers.set(id, marker);
    }
    const element = marker.getElement();
    applyPoiMarkerClass(element, poi);
    if (isNew) {
      element.classList.add("spawn");
      setTimeout(() => element.classList.remove("spawn"), 900);
    }
    if (becameVisible) {
      element.classList.add("spin-in");
      setTimeout(() => element.classList.remove("spin-in"), 850);
    }
    if (isVisible) nextVisibleIds.add(id);
    const place = parkingPoiPlace(poi);
    const address = cleanParkingAddress(poi.address);
    element.title = `${poi.name || "Parcheggio"}${address && address !== place ? ` · ${address}` : ""}`;
    marker.setLngLat([poi.lon, poi.lat]);
  }

  for (const [id, marker] of state.parkingPoiMarkers) {
    if (!liveIds.has(id)) {
      marker.remove();
      state.parkingPoiMarkers.delete(id);
    }
  }
  state.visiblePoiIds = nextVisibleIds;
}

function syncCamera(options = {}) {
  if (!state.mapLoaded) return;
  const target = state.destinationSegmentId ? currentTarget() : null;
  const bearing = target ? bearingBetween(state.currentPoint, target) - 8 : state.driveBearing;
  const nextBearing = options.bearing ?? bearing;
  syncUserMarkerHeading();
  state.map.easeTo({
    center: [state.currentPoint.lon, state.currentPoint.lat],
    zoom: state.trackingGps ? MAP_TRACKING_ZOOM : MAP_DEFAULT_ZOOM,
    pitch: 45,
    bearing: nextBearing,
    duration: options.duration ?? (options.instant ? 0 : 650),
  });
}

function syncUserMarkerHeading() {
  state.userMarker?.setRotation(normalizeBearing(state.driveBearing));
  const icon = state.userMarker?.getElement().querySelector(".material-symbols-rounded");
  if (icon) icon.style.transform = "";
}

function setFreshness() {
  els.lastUpdated.textContent = state.lastUpdatedAt
    ? `Aggiornato ${state.lastUpdatedAt.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
    : "--";
}

function updateClock() {
  els.clock.textContent = new Date().toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
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
      stopDriveSimulation();
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
  syncRouteUi();
  syncMapSources();
  syncCamera();
  renderPanel();
}

function renderDestination() {
  if (!state.destinationSegmentId) {
    els.arrivalAddress.textContent = "Nessuna destinazione selezionata";
    els.destinationResult.textContent = "";
  }
  const target = currentTarget();
  const heat = target.segment ? state.heatmap.get(target.segment.id) : null;
  const name = target.segment?.street_name || "Destinazione";
  const currentLabel = state.currentSegment && state.prediction
    ? `${state.currentSegment.street_name} · ${state.prediction.parkability_percent}%`
    : "Tratto non stimato";
  els.destinationFloatingLabel.textContent = currentLabel;
  els.destinationFloating.style.display = "inline-flex";
  if (!state.destinationSegmentId) return;
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
  const target = state.destinationSegmentId ? currentTarget() : null;
  const routeMeters = target ? Math.max(120, distanceMeters(state.currentPoint, target) * 1.25) : 0;
  const minutes = target ? Math.max(3, Math.round(routeMeters / 420)) : 0;
  const eta = new Date(Date.now() + minutes * 60000);
  const targetRoad = target?.segment ? target.segment.street_name : "Test prediction";

  if (target) {
    els.nextDistance.textContent = formatDistance(Math.min(routeMeters * 0.34, 850));
    els.nextAction.textContent = bearingBetween(state.currentPoint, target) > 180 ? "Svolta a sinistra" : "Svolta a destra";
    els.nextRoad.textContent = targetRoad;
    els.followingAction.textContent = "Poi prosegui";
    els.followingRoad.textContent = target.segment?.parking_label || "Tratto parcheggio";
    els.followingDistance.textContent = formatDistance(Math.max(220, routeMeters * 0.55));
    els.arrivalTime.textContent = eta.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
    els.arrivalMinutes.textContent = `${minutes} min`;
    els.arrivalDistance.textContent = formatDistance(routeMeters);
  } else {
    els.nextDistance.textContent = "Frecce";
    els.nextAction.textContent = "Muoviti sulla mappa";
    els.nextRoad.textContent = targetRoad;
    els.followingAction.textContent = "Shift";
    els.followingRoad.textContent = "Passo lungo";
    els.followingDistance.textContent = "";
    els.arrivalTime.textContent = "--:--";
    els.arrivalMinutes.textContent = "-- min";
    els.arrivalDistance.textContent = "-- km";
  }

  if (!state.currentSegment || !state.prediction) {
    els.currentSummary.textContent = state.currentPoint.label || "Posizione corrente";
    els.zoneName.textContent = "Fuori area stimata";
    els.score.textContent = "--%";
    els.status.textContent = "--";
    els.trend.textContent = "--";
    els.searchTime.textContent = "--";
    els.confidence.textContent = "--";
    els.recommendation.textContent = state.trackingGps ? "Radar attivo, stime non disponibili in questa area." : "Scegli una zona demo o usa il GPS.";
    resetAiSuggestion();
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
  syncAiSuggestionForCurrentSegment();
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
  const zoom = Math.round(state.map?.getZoom() || MAP_DEFAULT_ZOOM);
  const heatmap = await api(`/segment-heatmap?bbox=${bboxAround(state.currentPoint)}&zoom=${zoom}`);
  state.heatmap = new Map(heatmap.segments.map((segment) => [segment.segment_id, segment]));
}

async function refreshRoadNetwork(force = false) {
  const key = `${localCellKey(state.currentPoint)}:${ROAD_NETWORK_RADIUS_M}`;
  if (!force && state.roadNetworkFetchKey === key) return;
  state.roadNetworkFetchKey = key;
  try {
    const params = new URLSearchParams({
      lat: state.currentPoint.lat.toFixed(6),
      lon: state.currentPoint.lon.toFixed(6),
      radius_m: String(ROAD_NETWORK_RADIUS_M),
    });
    const result = await api(`/road-network?${params}`);
    state.roadEdges = result.edges || [];
  } catch {
    state.roadEdges = [];
  }
}

function setTomTomPoiStatus(text) {
  if (els.tomtomPoiStatus) els.tomtomPoiStatus.textContent = text;
}

function setTomTomPredictionStatus(text) {
  if (els.tomtomPredictionStatus) els.tomtomPredictionStatus.textContent = text;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function refreshTomTomBudget() {
  if (!els.tomtomSearchBudget && !els.tomtomTrafficBudget) return;
  try {
    const budget = await ingestionApi("/traffic/tomtom/budget");
    const search = budget.services?.search;
    const flow = budget.services?.traffic_flow;
    const incidents = budget.services?.traffic_incidents;
    els.tomtomSearchBudget.textContent = search
      ? `Search: ${search.used}/${search.test_limit}`
      : "Search: --";
    if (els.tomtomTrafficBudget) {
      els.tomtomTrafficBudget.textContent = flow && incidents
        ? `Flow ${flow.used}/${flow.test_limit} · Incidents ${incidents.used}/${incidents.test_limit}`
        : "Flow/Incidents: --";
    }
  } catch {
    els.tomtomSearchBudget.textContent = "Search: --";
    if (els.tomtomTrafficBudget) els.tomtomTrafficBudget.textContent = "Flow/Incidents: --";
  }
}

async function refreshTomTomPrediction(point, force = false) {
  const key = `${localCellKey(point)}:${LOCAL_RADIUS_M}`;
  if (!force && state.tomtomPredictionFetchKey === key && Date.now() - state.tomtomPredictionFetchAt < TOMTOM_PREDICTION_REFRESH_MS) {
    setTomTomPredictionStatus("Prediction TomTom: cache");
    return;
  }

  try {
    setTomTomPredictionStatus("Prediction TomTom: aggiorno");
    const result = await ingestionApi("/traffic/tomtom/publish", {
      method: "POST",
      body: JSON.stringify({
        lat: point.lat,
        lon: point.lon,
        radius_m: LOCAL_RADIUS_M,
      }),
    });
    state.tomtomPredictionFetchKey = key;
    state.tomtomPredictionFetchAt = Date.now();
    const live = result.estimate && result.estimate.cache_hit === false;
    setTomTomPredictionStatus(live ? "Prediction TomTom: live" : "Prediction TomTom: cache");
    await refreshTomTomBudget();
    if (live) await wait(TOMTOM_PREDICTION_SETTLE_MS);
  } catch {
    state.tomtomPredictionFetchKey = key;
    state.tomtomPredictionFetchAt = Date.now();
    setTomTomPredictionStatus("Prediction TomTom: non disponibile");
    refreshTomTomBudget();
  }
}

async function refreshParkingPois(force = false) {
  const key = `${localCellKey(state.currentPoint)}:${PARKING_POI_RADIUS_M}`;
  if (!force && state.parkingPoiFetchKey === key && Date.now() - state.parkingPoiFetchAt < PARKING_POI_REFRESH_MS) {
    setTomTomPoiStatus("POI TomTom: cache frontend");
    return;
  }
  state.parkingPoiFetchKey = key;
  state.parkingPoiFetchAt = Date.now();

  try {
    const params = new URLSearchParams({
      lat: state.currentPoint.lat.toFixed(6),
      lon: state.currentPoint.lon.toFixed(6),
      radius_m: String(PARKING_POI_RADIUS_M),
      limit: "10",
    });
    const result = await api(`/tomtom/parking-pois?${params}`);
    setTomTomPoiStatus(result.cache_hit ? "POI TomTom: cache backend" : "POI TomTom: live");
    state.parkingPois = (result.parking_pois || [])
      .filter((poi) => Number.isFinite(poi.lat) && Number.isFinite(poi.lon))
      .map((poi) => ({
        ...poi,
        distance_m: Number.isFinite(poi.distance_m) ? poi.distance_m : distanceMeters(state.currentPoint, poi),
      }))
      .filter((poi) => poi.distance_m <= PARKING_POI_RADIUS_M);
    refreshTomTomBudget();
  } catch {
    state.parkingPois = [];
    setTomTomPoiStatus("POI TomTom: non disponibile");
  }
  syncParkingPoiMarkers();
}

async function refreshPointData(token, point, options = {}) {
  await refreshRoadNetwork();
  if (token !== state.updateToken) return;
  await refreshTomTomPrediction(point, Boolean(options.forceTomTom));
  if (token !== state.updateToken) return;
  await refreshHeatmap();
  if (token !== state.updateToken) return;
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

async function setPoint(point, options = {}) {
  const token = ++state.updateToken;
  if (Number.isFinite(point.bearing)) state.driveBearing = point.bearing;
  state.currentPoint = point;
  renderDemoButtons();
  if (!options.visualOnly) els.radarStatus.textContent = "Analisi";
  syncMarkers();
  syncCamera(options);
  if (options.visualOnly) return;
  if (!options.skipPoiRefresh) refreshParkingPois();
  refreshRoadNetwork();

  if (options.debounce) {
    clearTimeout(state.pointRefreshTimer);
    state.pointRefreshTimer = setTimeout(() => {
      refreshPointData(token, point, options).catch((error) => console.error(error));
    }, DATA_REFRESH_DEBOUNCE_MS);
    return;
  }

  await refreshPointData(token, point, options);
}

function handleGpsPosition(position) {
  stopDriveSimulation();
  const { latitude, longitude, accuracy } = position.coords;
  state.trackingGps = true;
  els.gpsStatus.textContent = "GPS attivo";
  setPoint({ id: "gps", label: "La tua posizione", lat: latitude, lon: longitude, accuracy });
}

function handleGpsError(error) {
  const denied = error.code === error.PERMISSION_DENIED;
  els.gpsStatus.textContent = denied ? "GPS non autorizzato" : "GPS non disponibile";
}

function stopGpsWatch() {
  if (state.watchId !== null) {
    navigator.geolocation?.clearWatch(state.watchId);
    state.watchId = null;
  }
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

function getBrowserPoint() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("GPS non supportato"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude, accuracy } = position.coords;
        resolve({ id: "gps-test", label: "La tua posizione", lat: latitude, lon: longitude, accuracy });
      },
      reject,
      GPS_OPTIONS,
    );
  });
}

function movePointByMeters(point, northM, eastM) {
  const lat = point.lat + northM / 111320;
  const lon = point.lon + eastM / (111320 * Math.max(0.2, Math.cos((point.lat * Math.PI) / 180)));
  return { id: "keyboard", label: "Test tastiera", lat, lon };
}

function movementBearing(northM, eastM) {
  return (Math.atan2(eastM, northM) * 180 / Math.PI + 360) % 360;
}

function movementVector(bearing, distanceM) {
  const radians = (bearing * Math.PI) / 180;
  return {
    northM: Math.cos(radians) * distanceM,
    eastM: Math.sin(radians) * distanceM,
  };
}

function handleKeyboardMove(event) {
  const keys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];
  const tag = event.target?.tagName;
  if (!keys.includes(event.key) || ["INPUT", "SELECT", "TEXTAREA"].includes(tag) || event.target?.isContentEditable) return;

  event.preventDefault();
  const now = performance.now();
  if (event.repeat && now - state.lastKeyboardMoveAt < KEYBOARD_REPEAT_MS) return;
  state.lastKeyboardMoveAt = now;
  stopDriveSimulation();
  stopGpsWatch();
  state.trackingGps = false;
  els.gpsStatus.textContent = "Demo tastiera";
  const multiplier = event.shiftKey ? 3 : 1;
  let intendedBearing = state.driveBearing;
  let distanceM = KEYBOARD_MOVE_M * multiplier;
  if (event.key === "ArrowDown") distanceM *= -1;
  if (event.key === "ArrowLeft") intendedBearing = normalizeBearing(state.driveBearing - KEYBOARD_TURN_DEGREES);
  if (event.key === "ArrowRight") intendedBearing = normalizeBearing(state.driveBearing + KEYBOARD_TURN_DEGREES);
  const { northM, eastM } = movementVector(intendedBearing, distanceM);
  const nextPoint = snapPointToRoad(movePointByMeters(state.currentPoint, northM, eastM), intendedBearing);
  if (nextPoint.offRoad) {
    state.driveBearing = intendedBearing;
    els.gpsStatus.textContent = "Fuori strada";
    syncCamera({ duration: KEYBOARD_ANIMATION_MS, bearing: state.driveBearing });
    return;
  }
  state.driveBearing = nextPoint.bearing;
  setPoint(nextPoint, { debounce: true, duration: KEYBOARD_ANIMATION_MS, bearing: state.driveBearing }).catch((error) => console.error(error));
}

async function testTomTomPois() {
  setTomTomPoiStatus("POI TomTom: test live");
  let basePoint = state.currentPoint;
  try {
    basePoint = await getBrowserPoint();
  } catch {
    setTomTomPoiStatus("POI TomTom: test su posizione corrente");
  }

  await setPoint(basePoint, { debounce: true, duration: KEYBOARD_ANIMATION_MS, skipPoiRefresh: true });

  const offsets = [
    [0, 0],
    [250, 0],
    [0, 250],
  ].slice(0, TOMTOM_POI_TEST_CELLS);
  const seen = new Set();
  const pois = [];

  for (const [northM, eastM] of offsets) {
    const point = movePointByMeters(basePoint, northM, eastM);
    const params = new URLSearchParams({
      lat: point.lat.toFixed(6),
      lon: point.lon.toFixed(6),
      radius_m: String(PARKING_POI_RADIUS_M),
      limit: "10",
    });
    const result = await api(`/tomtom/parking-pois?${params}`);
    for (const poi of result.parking_pois || []) {
      const id = parkingPoiId(poi);
      if (seen.has(id)) continue;
      seen.add(id);
      pois.push({
        ...poi,
        distance_m: Number.isFinite(poi.distance_m) ? poi.distance_m : distanceMeters(basePoint, poi),
      });
    }
  }

  state.parkingPois = pois;
  state.parkingPoiFetchKey = `${localCellKey(basePoint)}:${PARKING_POI_RADIUS_M}`;
  state.parkingPoiFetchAt = Date.now();
  syncParkingPoiMarkers();
  setTomTomPoiStatus(`POI TomTom: ${pois.length} risultati`);
  refreshTomTomBudget();
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

async function explainCurrentZone(options = {}) {
  if (!state.currentSegment || !state.prediction) return;
  const automatic = Boolean(options.automatic);
  const requestKey = currentAiKey();
  const previousText = els.explainAi.textContent;
  if (state.aiSuggestionLoading && automatic) return;
  if (state.aiSuggestionLoading) return;
  state.aiSuggestionLoading = true;
  syncAiHud();
  if (!state.aiSuggestion || state.aiSuggestionKey !== requestKey) playAiHudDrop();
  els.explainAi.disabled = true;
  els.explainAi.classList.add("loading");
  els.explainAi.textContent = "Analisi in corso...";
  try {
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
        context: aiLocalContext(),
      }),
    });
    if (currentAiKey() === requestKey) renderAiSuggestion(explanation, { animate: true, speak: true });
  } catch {
    if (currentAiKey() === requestKey) {
      state.aiSuggestion = null;
      state.aiSuggestionKey = "";
      clearAiSuggestion();
    }
  } finally {
    state.aiSuggestionLoading = false;
    syncAiHud();
    els.explainAi.disabled = false;
    els.explainAi.classList.remove("loading");
    els.explainAi.textContent = previousText;
  }
}

function handleAiHudClick() {
  if (!state.currentSegment || !state.prediction || state.aiSuggestionLoading) return;
  if (state.aiSuggestion && state.aiSuggestionKey === currentAiKey()) {
    setSheet("navigation", true);
    return;
  }
  explainCurrentZone();
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
  updateWeather();
  setInterval(() => updateWeather(state.currentPoint, true), WEATHER_REFRESH_MS);
}

function bindEvents() {
  els.destinationZone.addEventListener("change", (event) => {
    state.destinationSegmentId = event.target.value;
    syncRouteUi();
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
  els.aiDriveCard?.addEventListener("click", handleAiHudClick);
  els.soundToggle?.addEventListener("click", toggleTts);
  els.themeToggle?.addEventListener("click", toggleTheme);
  els.saveFavorite.addEventListener("click", addCurrentFavorite);
  els.testTomtomPois?.addEventListener("click", () => testTomTomPois().catch((error) => {
    console.error(error);
    setTomTomPoiStatus("POI TomTom: test fallito");
  }));
  els.driveSimulation?.addEventListener("click", startDriveSimulation);
  window.addEventListener("keydown", handleKeyboardMove);
}

async function init() {
  applyTheme();
  syncSoundToggle();
  initMap();
  updateClock();
  setInterval(updateClock, 30000);
  startStatusRefresh();
  state.segments = await api("/segments");
  state.session = await api("/live-sessions/start", { method: "POST" });
  await refreshRoadNetwork(true);
  refreshTomTomBudget();
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
