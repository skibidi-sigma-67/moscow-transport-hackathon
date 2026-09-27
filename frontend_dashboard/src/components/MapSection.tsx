import { memo, useEffect, useRef, useState } from 'react';
import {
  MAP_DEFAULT_CENTER,
  MAP_DEFAULT_ZOOM,
  MAP_PAN_DURATION_MS,
  SELECTED_VEHICLE_ZOOM,
  YANDEX_MAP_API_KEY,
} from '../config';
import type { VehicleState } from '../contracts';
import { REASON_LABELS, RISK_COLORS } from '../dashboardView';

declare global {
  interface Window {
    ymaps?: typeof import('yandex-maps');
  }
}

let mapApiPromise: Promise<typeof import('yandex-maps')> | null = null;

function loadMapApi(): Promise<typeof import('yandex-maps')> {
  if (!YANDEX_MAP_API_KEY) return Promise.reject(new Error('Не задан ключ Яндекс Карт'));
  if (window.ymaps) return window.ymaps.ready().then(() => window.ymaps as typeof import('yandex-maps'));
  if (mapApiPromise) return mapApiPromise;

  const promise = new Promise<typeof import('yandex-maps')>((resolve, reject) => {
    const script = document.createElement('script');
    const timeout = window.setTimeout(() => {
      script.remove();
      reject(new Error('Превышено время загрузки Яндекс Карт'));
    }, 15_000);
    const url = new URL('https://api-maps.yandex.ru/2.1/');
    url.searchParams.set('apikey', YANDEX_MAP_API_KEY);
    url.searchParams.set('lang', 'ru_RU');
    url.searchParams.set('load', 'package.full');
    script.src = url.toString();
    script.async = true;
    script.onload = () => {
      window.clearTimeout(timeout);
      const api = window.ymaps;
      if (!api) {
        reject(new Error('Яндекс Карты не загрузились'));
        return;
      }
      void api.ready().then(() => resolve(api), reject);
    };
    script.onerror = () => {
      window.clearTimeout(timeout);
      script.remove();
      reject(new Error('Не удалось загрузить Яндекс Карты'));
    };
    document.head.append(script);
  }).catch((error: unknown) => {
    mapApiPromise = null;
    throw error;
  });

  mapApiPromise = promise;
  return promise;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    switch (character) {
      case '&': return '&amp;';
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '"': return '&quot;';
      default: return '&#39;';
    }
  });
}

function balloonContent(vehicle: VehicleState): string {
  const incident = vehicle.incident_card;
  const reason = incident?.reason ? REASON_LABELS[incident.reason] : null;
  return `
    <div class="vehicle-balloon">
      <strong>ТС №${vehicle.tr_id}</strong>
      <p>Статус: ${vehicle.risk_color}</p>
      ${incident?.predicted_delay_s !== null && incident?.predicted_delay_s !== undefined
        ? `<p>Задержка: ${Math.round(incident.predicted_delay_s)} сек</p>` : ''}
      ${reason ? `<p>Причина: ${escapeHtml(reason)}</p>` : ''}
      ${incident?.route_segment ? `<p>Участок: ${escapeHtml(incident.route_segment)}</p>` : ''}
    </div>
  `;
}

function markerOptions(vehicle: VehicleState, selected: boolean) {
  return {
    preset: selected ? 'islands#circleDotIcon' : 'islands#circleIcon',
    iconColor: RISK_COLORS[vehicle.risk_color],
  };
}

interface MapSectionProps {
  vehicles: VehicleState[];
  selectedBusId: number | null;
  selectedVehicle: VehicleState | null;
  selectionRequest: number;
  onSelect: (vehicle: VehicleState) => void;
}

export const MapSection = memo(function MapSection({
  vehicles,
  selectedBusId,
  selectedVehicle,
  selectionRequest,
  onSelect,
}: MapSectionProps) {
  const elementRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<ymaps.Map | null>(null);
  const managerRef = useRef<ymaps.ObjectManager | null>(null);
  const vehiclesRef = useRef(vehicles);
  const selectedIdRef = useRef(selectedBusId);
  const selectedVehicleRef = useRef(selectedVehicle);
  const onSelectRef = useRef(onSelect);
  const syncRef = useRef<(() => void) | null>(null);
  const previousSelectedIdRef = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let disposed = false;
    let manager: ymaps.ObjectManager | null = null;
    let map: ymaps.Map | null = null;

    void loadMapApi().then((api) => {
      if (disposed || !elementRef.current) return;
      map = new api.Map(elementRef.current, {
        center: MAP_DEFAULT_CENTER,
        zoom: MAP_DEFAULT_ZOOM,
      });
      manager = new api.ObjectManager({ clusterize: true, gridSize: 64 });
      map.geoObjects.add(manager);
      mapRef.current = map;
      managerRef.current = manager;

      manager.objects.events.add('click', (event: ymaps.IEvent) => {
        const rawId = event.get('objectId') as unknown;
        const id = Number(rawId);
        if (!Number.isSafeInteger(id)) return;
        const vehicle = vehiclesRef.current.find(({ tr_id }) => tr_id === id);
        if (vehicle) onSelectRef.current(vehicle);
      });

      syncRef.current = () => {
        if (!manager) return;
        manager.removeAll();
        manager.add({
          type: 'FeatureCollection',
          features: vehiclesRef.current.map((vehicle) => ({
            type: 'Feature',
            id: String(vehicle.tr_id),
            geometry: {
              type: 'Point',
              coordinates: [vehicle.latitude, vehicle.longitude],
            },
            properties: { balloonContent: balloonContent(vehicle) },
            options: markerOptions(vehicle, vehicle.tr_id === selectedIdRef.current),
          })),
        });
      };
      syncRef.current();
      setLoading(false);
      const selected = selectedVehicleRef.current;
      if (selected) {
        void map.setCenter(
          [selected.latitude, selected.longitude],
          SELECTED_VEHICLE_ZOOM,
          { duration: MAP_PAN_DURATION_MS },
        );
      }
    }).catch((cause: unknown) => {
      if (!disposed) {
        setLoading(false);
        setError(cause instanceof Error ? cause.message : 'Ошибка карты');
      }
    });

    return () => {
      disposed = true;
      syncRef.current = null;
      managerRef.current = null;
      mapRef.current = null;
      manager?.removeAll();
      map?.destroy();
    };
  }, [retryCount]);

  useEffect(() => {
    vehiclesRef.current = vehicles;
    syncRef.current?.();
  }, [vehicles]);

  useEffect(() => {
    selectedIdRef.current = selectedBusId;
    selectedVehicleRef.current = selectedVehicle;
    const manager = managerRef.current;
    const previousId = previousSelectedIdRef.current;
    if (manager && previousId !== null) {
      const previous = vehiclesRef.current.find(({ tr_id }) => tr_id === previousId);
      if (previous) manager.objects.setObjectOptions(String(previousId), markerOptions(previous, false));
    }
    if (manager && selectedBusId !== null && selectedVehicle) {
      manager.objects.setObjectOptions(String(selectedBusId), markerOptions(selectedVehicle, true));
    }
    previousSelectedIdRef.current = selectedBusId;
  }, [selectedBusId, selectedVehicle]);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    const vehicle = selectedVehicleRef.current;
    if (!map || !vehicle || selectionRequest === 0) return;
    void map.setCenter(
      [vehicle.latitude, vehicle.longitude],
      SELECTED_VEHICLE_ZOOM,
      { duration: MAP_PAN_DURATION_MS },
    );
  }, [selectionRequest]);

  return (
    <section className="map-section" aria-label="Карта транспортных средств">
      <div ref={elementRef} className="map-canvas" />
      {loading && <div className="map-overlay" role="status">Загрузка Яндекс Карт…</div>}
      {error && (
        <div className="map-overlay map-error" role="alert">
          <p>{error}</p>
          <button type="button" onClick={() => {
            setError(null);
            setLoading(true);
            setRetryCount((count) => count + 1);
          }}>Повторить загрузку карты</button>
        </div>
      )}
    </section>
  );
});
