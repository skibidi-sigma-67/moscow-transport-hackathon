export type RiskColor = 'GREEN' | 'YELLOW' | 'RED';

export type IncidentReason =
  | 'TRAFFIC_JAM'
  | 'ACCIDENT'
  | 'ROAD_WORK'
  | 'VEHICLE_BREAKDOWN'
  | 'WEATHER_CONDITIONS'
  | 'UNKNOWN_DELAY';

export interface IncidentCard {
  has_incident: boolean;
  predicted_delay_s: number | null;
  reason: IncidentReason | null;
  route_segment: string | null;
}

export interface VehicleState {
  tr_id: number;
  longitude: number;
  latitude: number;
  risk_color: RiskColor;
  incident_card: IncidentCard | null;
}

export interface DashboardStateResponse {
  timestamp: string;
  vehicles: VehicleState[];
}

export interface HealthSettings {
  prediction_cache_ttl: number;
  telemetry_max_history: number;
  stop_speed_threshold_kmh: number;
  ml_telemetry_window_minutes: number;
  max_idle_gap_s: number;
  historical_packet_delay_s: number;
  dashboard_websocket_update_interval_s: number;
}

export interface HealthResponse {
  status: string;
  ml_status: string;
  settings: HealthSettings;
}

export interface UploadResponse {
  inserted_count: number;
}

const riskColors = new Set<RiskColor>(['GREEN', 'YELLOW', 'RED']);
const incidentReasons = new Set<IncidentReason>([
  'TRAFFIC_JAM',
  'ACCIDENT',
  'ROAD_WORK',
  'VEHICLE_BREAKDOWN',
  'WEATHER_CONDITIONS',
  'UNKNOWN_DELAY',
]);

function record(value: unknown, name: string): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Некорректное поле ${name}`);
  }
  return value as Record<string, unknown>;
}

function finiteNumber(value: unknown, name: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`Некорректное поле ${name}`);
  }
  return value;
}

function nonnegativeNumber(value: unknown, name: string): number {
  const result = finiteNumber(value, name);
  if (result < 0) throw new Error(`Некорректное поле ${name}`);
  return result;
}

function integer(value: unknown, name: string): number {
  const result = nonnegativeNumber(value, name);
  if (!Number.isSafeInteger(result)) throw new Error(`Некорректное поле ${name}`);
  return result;
}

function string(value: unknown, name: string): string {
  if (typeof value !== 'string') throw new Error(`Некорректное поле ${name}`);
  return value;
}

function nullableString(value: unknown, name: string): string | null {
  if (value === null) return null;
  return string(value, name);
}

function incident(value: unknown): IncidentCard {
  const source = record(value, 'incident_card');
  if (typeof source.has_incident !== 'boolean') {
    throw new Error('Некорректное поле has_incident');
  }

  const rawReason = source.reason;
  if (rawReason !== null && !incidentReasons.has(rawReason as IncidentReason)) {
    throw new Error('Некорректное поле reason');
  }

  const predictedDelay = source.predicted_delay_s;
  const routeSegment = nullableString(source.route_segment, 'route_segment');
  if (routeSegment !== null && routeSegment.length > 500) {
    throw new Error('Слишком длинный route_segment');
  }

  return {
    has_incident: source.has_incident,
    predicted_delay_s:
      predictedDelay === null
        ? null
        : nonnegativeNumber(predictedDelay, 'predicted_delay_s'),
    reason: rawReason as IncidentReason | null,
    route_segment: routeSegment,
  };
}

export function parseDashboardResponse(value: unknown): DashboardStateResponse {
  const source = record(value, 'dashboard');
  const timestamp = string(source.timestamp, 'timestamp');
  if (!Number.isFinite(Date.parse(timestamp))) {
    throw new Error('Некорректное поле timestamp');
  }
  if (!Array.isArray(source.vehicles)) {
    throw new Error('Некорректное поле vehicles');
  }

  const seenIds = new Set<number>();
  const vehicles = source.vehicles.map((item) => {
    const vehicle = record(item, 'vehicle');
    const trId = integer(vehicle.tr_id, 'tr_id');
    const latitude = finiteNumber(vehicle.latitude, 'latitude');
    const longitude = finiteNumber(vehicle.longitude, 'longitude');
    if (seenIds.has(trId) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
      throw new Error('Некорректные координаты или повторяющийся tr_id');
    }
    seenIds.add(trId);
    if (!riskColors.has(vehicle.risk_color as RiskColor)) {
      throw new Error('Некорректное поле risk_color');
    }

    return {
      tr_id: trId,
      latitude,
      longitude,
      risk_color: vehicle.risk_color as RiskColor,
      incident_card:
        vehicle.incident_card === null ? null : incident(vehicle.incident_card),
    };
  });

  return { timestamp, vehicles };
}

export function parseHealthResponse(value: unknown): HealthResponse {
  const source = record(value, 'health');
  const settings = record(source.settings, 'settings');
  return {
    status: string(source.status, 'status'),
    ml_status: string(source.ml_status, 'ml_status'),
    settings: {
      prediction_cache_ttl: integer(settings.prediction_cache_ttl, 'prediction_cache_ttl'),
      telemetry_max_history: integer(settings.telemetry_max_history, 'telemetry_max_history'),
      stop_speed_threshold_kmh: nonnegativeNumber(settings.stop_speed_threshold_kmh, 'stop_speed_threshold_kmh'),
      ml_telemetry_window_minutes: integer(settings.ml_telemetry_window_minutes, 'ml_telemetry_window_minutes'),
      max_idle_gap_s: nonnegativeNumber(settings.max_idle_gap_s, 'max_idle_gap_s'),
      historical_packet_delay_s: nonnegativeNumber(settings.historical_packet_delay_s, 'historical_packet_delay_s'),
      dashboard_websocket_update_interval_s: nonnegativeNumber(settings.dashboard_websocket_update_interval_s, 'dashboard_websocket_update_interval_s'),
    },
  };
}

export function parseUploadResponse(value: unknown): UploadResponse {
  const source = record(value, 'upload');
  return { inserted_count: integer(source.inserted_count, 'inserted_count') };
}
