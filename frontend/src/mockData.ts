import type { DashboardStateResponse, IncidentCard, RiskColor, VehicleState } from './contracts';

export const MOCK_UPDATE_INTERVAL_MS = 7_000;

const MOCK_VEHICLE_COUNT = 15;
const STREETS = [
  'Центральный проспект',
  'Садовое кольцо',
  'Тверская улица',
  'Кутузовский проспект',
  'Ленинский проспект',
  'Проспект Мира',
] as const;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function createIncident(color: RiskColor, random: () => number): IncidentCard | null {
  if (color === 'GREEN') return null;
  const red = color === 'RED';
  return {
    has_incident: true,
    predicted_delay_s: red ? 300 + Math.floor(random() * 600) : 60 + Math.floor(random() * 300),
    reason: red ? 'ACCIDENT' : 'TRAFFIC_JAM',
    route_segment: STREETS[Math.floor(random() * STREETS.length)] ?? STREETS[0],
  };
}

export function createMockSnapshot(
  previous: DashboardStateResponse | null,
  random: () => number = Math.random,
  now: Date = new Date(),
): DashboardStateResponse {
  const vehicles: VehicleState[] = Array.from({ length: MOCK_VEHICLE_COUNT }, (_, index) => {
    const last = previous?.vehicles[index];
    const roll = last ? random() : index % 7 === 0 ? 0.95 : index % 3 === 0 ? 0.8 : 0.1;
    const riskColor: RiskColor = roll > 0.9 ? 'RED' : roll > 0.7 ? 'YELLOW' : 'GREEN';

    return {
      tr_id: last?.tr_id ?? 1000 + index,
      latitude: clamp(last ? last.latitude + (random() - 0.5) * 0.002 : 55.7 + random() * 0.1, 55.7, 55.8),
      longitude: clamp(last ? last.longitude + (random() - 0.5) * 0.002 : 37.5 + random() * 0.2, 37.5, 37.7),
      risk_color: riskColor,
      incident_card: createIncident(riskColor, random),
    };
  });

  return { timestamp: now.toISOString(), vehicles };
}
