import assert from 'node:assert/strict';
import test from 'node:test';
import { parseDashboardResponse } from '../src/contracts.ts';
import { createMockSnapshot } from '../src/mockData.ts';

test('demo starts with 15 vehicles and visible incidents', () => {
  const snapshot = createMockSnapshot(null, () => 0.5, new Date('2026-09-27T12:00:00Z'));

  assert.equal(snapshot.vehicles.length, 15);
  assert.ok(snapshot.vehicles.some(({ risk_color }) => risk_color === 'RED'));
  assert.ok(snapshot.vehicles.some(({ risk_color }) => risk_color === 'YELLOW'));
  assert.deepEqual(parseDashboardResponse(snapshot), snapshot);
});

test('demo updates keep stable vehicle identities and valid coordinates', () => {
  const initial = createMockSnapshot(null, () => 0.5, new Date('2026-09-27T12:00:00Z'));
  const updated = createMockSnapshot(initial, () => 0.95, new Date('2026-09-27T12:00:07Z'));

  assert.deepEqual(updated.vehicles.map(({ tr_id }) => tr_id), initial.vehicles.map(({ tr_id }) => tr_id));
  assert.equal(updated.timestamp, '2026-09-27T12:00:07.000Z');
  assert.deepEqual(parseDashboardResponse(updated), updated);
});
