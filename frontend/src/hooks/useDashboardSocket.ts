import { useEffect, useState } from 'react';
import { MAX_RECONNECT_DELAY_MS, MIN_STALE_DELAY_MS, WS_URL } from '../config';
import { parseDashboardResponse, type DashboardStateResponse } from '../contracts';

export type SocketStatus = 'connecting' | 'connected' | 'disconnected' | 'invalid-data' | 'stale';

interface DashboardSocketState {
  data: DashboardStateResponse | null;
  status: SocketStatus;
  error: string | null;
  lastMessageAt: number | null;
}

export function useDashboardSocket(
  updateIntervalSeconds: number | null,
  onSnapshot: (snapshot: DashboardStateResponse) => void,
  enabled = true,
): DashboardSocketState {
  const [state, setState] = useState<DashboardSocketState>({
    data: null,
    status: 'connecting',
    error: null,
    lastMessageAt: null,
  });

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let socket: WebSocket | undefined;
    let retryTimer: number | undefined;
    let staleTimer: number | undefined;
    let attempt = 0;

    const armStaleTimer = () => {
      if (staleTimer !== undefined) window.clearTimeout(staleTimer);
      const staleAfterMs = Math.max((updateIntervalSeconds ?? 2) * 3_000, MIN_STALE_DELAY_MS);
      staleTimer = window.setTimeout(() => {
        setState((previous) => ({
          ...previous,
          status: 'stale',
          error: 'Данные перестали обновляться',
        }));
        socket?.close();
      }, staleAfterMs);
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      const baseDelay = Math.min(1_000 * 2 ** Math.min(attempt++, 5), MAX_RECONNECT_DELAY_MS);
      retryTimer = window.setTimeout(connect, baseDelay + Math.random() * 500);
    };

    const connect = () => {
      if (disposed) return;
      setState((previous) => ({ ...previous, status: 'connecting' }));

      try {
        socket = new WebSocket(WS_URL);
      } catch (error) {
        setState((previous) => ({
          ...previous,
          status: 'disconnected',
          error: error instanceof Error ? error.message : 'Не удалось открыть WebSocket',
        }));
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        setState((previous) => ({ ...previous, status: 'connected', error: null }));
        armStaleTimer();
      };

      socket.onmessage = ({ data }) => {
        try {
          if (typeof data !== 'string') throw new Error('Неподдерживаемый формат сообщения');
          const parsed = parseDashboardResponse(JSON.parse(data) as unknown);
          attempt = 0;
          onSnapshot(parsed);
          const receivedAt = Date.now();
          setState({ data: parsed, status: 'connected', error: null, lastMessageAt: receivedAt });
          armStaleTimer();
        } catch (error) {
          setState((previous) => ({
            ...previous,
            status: 'invalid-data',
            error: error instanceof Error ? error.message : 'Некорректное сообщение сервера',
          }));
          socket?.close();
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (disposed) return;
        if (staleTimer !== undefined) window.clearTimeout(staleTimer);
        setState((previous) => ({
          ...previous,
          status: 'disconnected',
          error: previous.status === 'invalid-data' || previous.status === 'stale'
            ? previous.error : 'Соединение с потоком данных потеряно',
        }));
        scheduleReconnect();
      };
    };

    connect();
    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      if (staleTimer !== undefined) window.clearTimeout(staleTimer);
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close(1000, 'Component unmounted');
      }
    };
  }, [enabled, updateIntervalSeconds, onSnapshot]);

  return state;
}
