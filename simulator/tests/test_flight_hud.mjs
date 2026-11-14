// Known-geometry checks for read-only HUD range estimates.
import test from 'node:test';
import assert from 'node:assert/strict';
import { forwardRange } from '../viewer/hud/range.js';

test('forward estimate follows NED heading and ignores obstacles behind', function () {
  const world = { obstacles: [{ type: 'box', center: [2, 0, 2], half: [.5, .5, .5], yaw_deg: 0 }] };
  const s = { pos: [0, 0, 2], euler: [0, 0, 0] };
  assert.ok(Math.abs(forwardRange(s, world) - 1.4) < .11);
  assert.equal(forwardRange({ ...s, euler: [0, 0, 180] }, world), null);
});
test('cylinder and wall estimates respect geometry and height', function () {
  const s = { pos: [0, 0, 2], euler: [0, 0, 90] };
  const pole = { type: 'cylinder', p0: [0, 3, 0], p1: [0, 3, 10], radius: .5 };
  assert.ok(Math.abs(forwardRange(s, { obstacles: [pole] }) - 2.4) < .11);
  const wall = { type: 'wall', point: [0, 2, 0], normal_deg: 90, width: 4, top: 3 };
  assert.equal(forwardRange(s, { obstacles: [wall] }), null);
});
