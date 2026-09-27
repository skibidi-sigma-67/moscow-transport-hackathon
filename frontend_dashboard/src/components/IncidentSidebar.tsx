import { memo, useEffect, useRef } from 'react';
import type { VehicleState } from '../contracts';
import { REASON_LABELS } from '../dashboardView';

interface IncidentSidebarProps {
  incidents: VehicleState[];
  hasData: boolean;
  selectedVehicle: VehicleState | null;
  selectedBusId: number | null;
  onSelect: (vehicle: VehicleState) => void;
}

export const IncidentSidebar = memo(function IncidentSidebar({
  incidents,
  hasData,
  selectedVehicle,
  selectedBusId,
  onSelect,
}: IncidentSidebarProps) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedBusId === null) return;
    const selected = [...(listRef.current?.querySelectorAll<HTMLElement>('[data-vehicle-id]') ?? [])]
      .find((element) => element.dataset.vehicleId === String(selectedBusId));
    if (!selected || !listRef.current) return;
    const top = selected.getBoundingClientRect().top - listRef.current.getBoundingClientRect().top
      + listRef.current.scrollTop - listRef.current.clientHeight / 2;
    listRef.current.scrollTo({ top, behavior: 'smooth' });
  }, [selectedBusId]);

  return (
    <aside className="sidebar" aria-label="Лента инцидентов">
      <h2>Лента инцидентов</h2>
      {selectedVehicle && !incidents.some(({ tr_id }) => tr_id === selectedVehicle.tr_id) && (
        <div className="selected-vehicle-summary">
          <strong>Выбрано ТС №{selectedVehicle.tr_id}</strong>
          <span>Статус: в графике</span>
        </div>
      )}
      <div ref={listRef} className="incident-list">
        {incidents.map((vehicle) => (
          <button
            type="button"
            key={vehicle.tr_id}
            data-vehicle-id={vehicle.tr_id}
            className={`incident-card ${vehicle.risk_color.toLowerCase()} ${selectedBusId === vehicle.tr_id ? 'selected' : ''}`}
            aria-pressed={selectedBusId === vehicle.tr_id}
            onClick={() => onSelect(vehicle)}
          >
            <span className="incident-title">ТС №{vehicle.tr_id}</span>
            <span><strong>Задержка:</strong> +{Math.round(vehicle.incident_card?.predicted_delay_s ?? 0)} сек</span>
            <span><strong>Причина:</strong> {vehicle.incident_card?.reason
              ? REASON_LABELS[vehicle.incident_card.reason] : 'Неизвестно'}</span>
            <span><strong>Участок:</strong> {vehicle.incident_card?.route_segment || 'Неизвестно'}</span>
          </button>
        ))}
        {incidents.length === 0 && (
          <p className="no-incidents">{hasData ? 'Инцидентов нет' : 'Нет данных телеметрии'}</p>
        )}
      </div>
    </aside>
  );
});
