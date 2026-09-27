import { useEffect, useState } from 'react';
import type { DashboardStateResponse } from '../contracts';
import { createMockSnapshot, MOCK_UPDATE_INTERVAL_MS } from '../mockData';

export function useMockData(enabled: boolean): DashboardStateResponse | null {
  const [snapshot, setSnapshot] = useState<DashboardStateResponse | null>(() =>
    enabled ? createMockSnapshot(null) : null);

  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      setSnapshot((previous) => createMockSnapshot(previous));
    }, MOCK_UPDATE_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [enabled]);

  return snapshot;
}
