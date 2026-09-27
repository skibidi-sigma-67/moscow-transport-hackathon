const apiBase = import.meta.env.VITE_API_URL?.trim() || window.location.origin;

export const API_BASE_URL = apiBase.replace(/\/$/, '');
export const WS_URL = import.meta.env.VITE_WS_URL?.trim() ||
  `${API_BASE_URL.replace(/^http/, 'ws')}/api/v1/dashboard/websocket`;
export const YANDEX_MAP_API_KEY = import.meta.env.VITE_YANDEX_MAP_API_KEY?.trim() || '';

const configuredHealthInterval = Number(import.meta.env.VITE_HEALTH_CHECK_INTERVAL);
export const HEALTH_CHECK_INTERVAL_MS =
  Number.isFinite(configuredHealthInterval) && configuredHealthInterval >= 5_000
    ? Math.min(configuredHealthInterval, 300_000)
    : 60_000;

export const API_TIMEOUT_MS = 10_000;
export const UPLOAD_TIMEOUT_MS = 120_000;
export const MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024;
export const TOP_SEGMENTS_LIMIT = 5;
export const MAP_DEFAULT_CENTER: [number, number] = [55.751244, 37.618423];
export const MAP_DEFAULT_ZOOM = 11;
export const SELECTED_VEHICLE_ZOOM = 14;
export const MAP_PAN_DURATION_MS = 500;
export const MAX_RECONNECT_DELAY_MS = 30_000;
export const MIN_STALE_DELAY_MS = 10_000;
