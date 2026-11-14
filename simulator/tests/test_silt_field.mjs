// Silt optics math in the viewer must match the server model (qysim/silt.py, PROTOCOL.md §4a).
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  lampBackscatter, presentedVisibility, siltConcentration, siltOpticalDepth, siltOpticsAt
} from '../viewer/fx/silt_field.js';

// Reference values printed by World.silt_concentration_at / visibility_at / optical_depth for the same puffs.
const ENVIRONMENT = {
  silt_puffs: [[1.0, 2.0, 19.2, 0.5, 0.3, 42.329], [0.0, 0.0, 18.0, 0.8, 0.6, 3.307]],
  turbidity: {seabed_type: 'mud', c_water: 0.6857, k_m2_per_g: 0.5, bnl_height_m: 1.5, bnl_mg_l: 2.0}
};
const OPTIONS = {visibilityM: 7, seabed: 20};

function near(actual, expected, relative = 0.01) {
  assert.ok(Math.abs(actual - expected) <= relative * Math.abs(expected) + 1e-6, `${actual} vs ${expected}`);
}

test('concentration and visibility match the server', function matchesServer() {
  near(siltConcentration(ENVIRONMENT, [1, 2, 19.5], 20), 27.1134);
  near(siltConcentration(ENVIRONMENT, [0, 0, 18], 20), 3.83416);
  near(siltConcentration(ENVIRONMENT, [3, 3, 15], 20), 0.071348);
  near(siltOpticsAt(ENVIRONMENT, [1, 2, 19.5], OPTIONS).visibility, 0.33702);
  near(siltOpticsAt(ENVIRONMENT, [0, 0, 18], OPTIONS).visibility, 1.84417);
  near(siltOpticalDepth(ENVIRONMENT, [0, 0, 18], [2, 2, 19.5], {...OPTIONS, samples: 16}), 12.9377);
  assert.equal(siltConcentration(ENVIRONMENT, [0, 0, 20.5], 20), 0);
});

test('legacy state without puffs is clear water', function legacyState() {
  const optics = siltOpticsAt({}, [0, 0, 5], {visibilityM: 12, seabed: 30});
  near(optics.visibility, 12);
  assert.equal(optics.mgL, 0);
});

test('lamp veil grows with sediment and lamp power; only the assisted floor clamps', function veilAndFloor() {
  assert.equal(lampBackscatter(0, 1), 0);
  assert.equal(lampBackscatter(20, 0), 0);
  assert.ok(lampBackscatter(20, 1) > lampBackscatter(20, 0.55));
  assert.ok(lampBackscatter(20, 1) > lampBackscatter(2, 1));
  assert.ok(lampBackscatter(20, 1, 5, 2) < lampBackscatter(20, 1, 0, 2));
  assert.equal(presentedVisibility(0.1, 8, false), 0.1);
  assert.equal(presentedVisibility(0.1, 8, true), 2);
});
