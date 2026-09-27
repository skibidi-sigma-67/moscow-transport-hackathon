import { API_BASE_URL, API_TIMEOUT_MS, MAX_CSV_SIZE_BYTES, UPLOAD_TIMEOUT_MS } from './config';
import {
  parseHealthResponse,
  parseUploadResponse,
  type HealthResponse,
  type UploadResponse,
} from './contracts';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function errorMessage(payload: unknown): string {
  if (typeof payload === 'string') return payload.slice(0, 300);
  if (payload !== null && typeof payload === 'object' && 'detail' in payload) {
    const detail = payload.detail;
    if (typeof detail === 'string') return detail.slice(0, 300);
    if (Array.isArray(detail)) {
      const messages = detail
        .filter((item): item is { msg: string } => item !== null && typeof item === 'object'
          && 'msg' in item && typeof item.msg === 'string')
        .map(({ msg }) => msg);
      if (messages.length) return messages.join('; ').slice(0, 300);
    }
  }
  return 'Сервер вернул ошибку';
}

async function request(
  path: string,
  init: RequestInit,
  signal: AbortSignal,
  timeoutMs = API_TIMEOUT_MS,
): Promise<unknown> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) controller.abort();
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(response.status, `${errorMessage(payload)} (HTTP ${response.status})`);
    }
    return payload;
  } catch (error) {
    if (timedOut) throw new Error('Превышено время ожидания сервера');
    if (error instanceof TypeError) throw new Error('Не удалось связаться с сервером');
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener('abort', abort);
  }
}

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  return parseHealthResponse(await request('/api/v1/health', { method: 'GET' }, signal));
}

export async function uploadCsv(
  endpoint: '/api/v1/schedule/upload' | '/api/v1/reference/devices/upload',
  file: File,
  signal: AbortSignal,
): Promise<UploadResponse> {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('Выберите CSV-файл');
  }
  if (file.size === 0 || file.size > MAX_CSV_SIZE_BYTES) {
    throw new Error('Размер CSV-файла должен быть от 1 байта до 100 МБ');
  }

  const body = new FormData();
  body.append('file', file);
  return parseUploadResponse(await request(endpoint, { method: 'POST', body }, signal, UPLOAD_TIMEOUT_MS));
}
