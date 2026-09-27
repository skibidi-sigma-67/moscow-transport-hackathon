import assert from 'node:assert/strict';
import test from 'node:test';
import { parseDashboardResponse, parseHealthResponse, parseUploadResponse } from '../src/contracts.ts';

const validDashboard = {
  timestamp: '2026-09-27T12:00:00Z',
  vehicles: [{
    tr_id: 1001,
    longitude: 37.62,
    latitude: 55.75,
    risk_color: 'YELLOW',
    incident_card: {
      has_incident: true,
      predicted_delay_s: 125.5,
      reason: 'TRAFFIC_JAM',
      route_segment: 'Садовое кольцо',
    },
  }],
};

test('accepts a valid dashboard snapshot', () => {
  const result = parseDashboardResponse(validDashboard);
  assert.equal(result.vehicles[0]?.incident_card?.predicted_delay_s, 125.5);
});

test('rejects malformed snapshots before rendering', () => {
  assert.throws(() => parseDashboardResponse({ ...validDashboard, vehicles: null }));
  assert.throws(() => parseDashboardResponse({ ...validDashboard, vehicles: [
    { ...validDashboard.vehicles[0], latitude: 200 },
  ] }));
  assert.throws(() => parseDashboardResponse({ ...validDashboard, vehicles: [
    validDashboard.vehicles[0], validDashboard.vehicles[0],
  ] }));
  assert.throws(() => parseDashboardResponse({ ...validDashboard, vehicles: [
    { ...validDashboard.vehicles[0], incident_card: {
      ...validDashboard.vehicles[0].incident_card,
      reason: '<img src=x onerror=alert(1)>',
    } },
  ] }));
});

test('accepts nullable backend incident fields', () => {
  const result = parseDashboardResponse({
    ...validDashboard,
    vehicles: [{
      ...validDashboard.vehicles[0],
      incident_card: {
        has_incident: false,
        predicted_delay_s: null,
        reason: null,
        route_segment: null,
      },
    }],
  });
  assert.equal(result.vehicles[0]?.incident_card?.reason, null);
});

test('rejects missing health settings and invalid upload counts', () => {
  assert.throws(() => parseHealthResponse({ status: 'ok', ml_status: 'ok', settings: {} }));
  assert.deepEqual(parseUploadResponse({ inserted_count: 5 }), { inserted_count: 5 });
  assert.throws(() => parseUploadResponse({ inserted_count: -1 }));
});
