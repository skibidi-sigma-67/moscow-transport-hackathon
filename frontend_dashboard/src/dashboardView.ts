import { TOP_SEGMENTS_LIMIT } from './config';
import type { IncidentReason, RiskColor, VehicleState } from './contracts';
import { BRAND_COLORS } from './palette';

export const RISK_COLORS: Record<RiskColor, string> = {
  GREEN: '#167d3e',
  YELLOW: BRAND_COLORS.yellow,
  RED: '#c53333',
};

export const REASON_LABELS: Record<IncidentReason, string> = {
  TRAFFIC_JAM: 'Плотный трафик',
  ACCIDENT: 'ДТП',
  ROAD_WORK: 'Дорожные работы',
  VEHICLE_BREAKDOWN: 'Поломка ТС',
  WEATHER_CONDITIONS: 'Погодные условия',
  UNKNOWN_DELAY: 'Неизвестная задержка',
};

export const REASON_COLORS: Record<IncidentReason, string> = {
  TRAFFIC_JAM: BRAND_COLORS.blue,
  ACCIDENT: BRAND_COLORS.mustard,
  ROAD_WORK: BRAND_COLORS.yellow,
  VEHICLE_BREAKDOWN: BRAND_COLORS.gray,
  WEATHER_CONDITIONS: BRAND_COLORS.lightBlue,
  UNKNOWN_DELAY: BRAND_COLORS.black,
};

export function buildDashboardView(vehicles: VehicleState[]) {
  const kpis = { total: vehicles.length, green: 0, risk: 0, yellow: 0, red: 0, totalDelay: 0 };
  const segments = new Map<string, number>();
  const reasons = new Map<IncidentReason, number>();
  const incidents: VehicleState[] = [];

  for (const vehicle of vehicles) {
    if (vehicle.risk_color === 'GREEN') kpis.green += 1;
    if (vehicle.risk_color === 'YELLOW') kpis.yellow += 1;
    if (vehicle.risk_color === 'RED') kpis.red += 1;

    const incident = vehicle.incident_card;
    if (vehicle.risk_color === 'GREEN' || !incident?.has_incident) continue;
    incidents.push(vehicle);
    const delay = incident.predicted_delay_s ?? 0;
    kpis.totalDelay += delay;
    if (incident.route_segment) {
      segments.set(incident.route_segment, (segments.get(incident.route_segment) ?? 0) + delay);
    }
    if (incident.reason) {
      reasons.set(incident.reason, (reasons.get(incident.reason) ?? 0) + 1);
    }
  }

  kpis.risk = kpis.yellow + kpis.red;
  incidents.sort((a, b) =>
    (b.incident_card?.predicted_delay_s ?? 0) - (a.incident_card?.predicted_delay_s ?? 0));

  return {
    kpis,
    incidents,
    segmentChartData: [...segments].map(([name, delay]) => ({ name, delay }))
      .sort((a, b) => b.delay - a.delay).slice(0, TOP_SEGMENTS_LIMIT),
    riskChartData: [
      { name: 'В графике', value: kpis.green, color: RISK_COLORS.GREEN },
      { name: 'Внимание', value: kpis.yellow, color: RISK_COLORS.YELLOW },
      { name: 'Опасность', value: kpis.red, color: RISK_COLORS.RED },
    ],
    reasonChartData: [...reasons].map(([reason, value]) => ({
      name: REASON_LABELS[reason],
      value,
      color: REASON_COLORS[reason],
    })),
  };
}
