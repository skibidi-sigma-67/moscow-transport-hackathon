import { useEffect, useState } from 'react';
import { getHealth } from '../api';
import { HEALTH_CHECK_INTERVAL_MS } from '../config';
import type { HealthSettings } from '../contracts';

export type HealthStatus = 'loading' | 'healthy' | 'degraded' | 'offline';

interface HealthState {
  status: HealthStatus;
  settings: HealthSettings | null;
  error: string | null;
}

export function useHealthCheck(): HealthState {
  const [state, setState] = useState<HealthState>({
    status: 'loading',
    settings: null,
    error: null,
  });

  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    let controller: AbortController | undefined;

    const poll = async () => {
      controller = new AbortController();
      try {
        const response = await getHealth(controller.signal);
        if (!disposed) {
          setState({
            status: response.status !== 'ok'
              ? 'offline'
              : response.ml_status === 'ok'
                ? 'healthy'
                : 'degraded',
            settings: response.settings,
            error: response.status === 'ok' ? null : `Статус сервера: ${response.status}`,
          });
        }
      } catch (error) {
        if (!disposed) {
          setState({
            status: 'offline',
            settings: null,
            error: error instanceof Error ? error.message : 'Не удалось проверить сервер',
          });
        }
      } finally {
        if (!disposed) timer = window.setTimeout(poll, HEALTH_CHECK_INTERVAL_MS);
      }
    };

    void poll();
    return () => {
      disposed = true;
      controller?.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  return state;
}
