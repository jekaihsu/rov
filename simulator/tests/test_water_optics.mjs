// Water optics model: per-channel extinction ordering, visibility tie-in, water colour at infinity and the
// exposure lag. The shaders evaluate the same formulas; these tests pin the model's qualitative behaviour.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {
  waterCoefficients, daylightAt, waterRadianceAtInfinity, adaptExposure, luminance, VISIBILITY_CONTRAST
} from '../viewer/fx/water_model.js';

test('red is attenuated first, then green, blue last, along any path', function () {
  for (const visibility of [4, 10, 18]) {
    const water = waterCoefficients(visibility);
    assert.ok(water.c[0] > water.c[1], `red beam attenuation exceeds green at ${visibility} m`);
    assert.ok(water.kd[0] > water.kd[1] && water.kd[0] > water.kd[2], `red daylight fades first at ${visibility} m`);
    assert.ok(water.c.every(function positive(value) {
      return value > 0;
    }));
  }
});

test('the green channel reaches the visibility contrast threshold at the scenario visibility', function () {
  for (const visibility of [1, 7, 12, 18]) {
    const water = waterCoefficients(visibility);
    assert.ok(Math.abs(water.c[1] * visibility - VISIBILITY_CONTRAST) < 1e-9);
  }
});

test('silt and turbidity add scattering and shift absorption towards blue', function () {
  const clear = waterCoefficients(18);
  const turbid = waterCoefficients(4);
  const silty = waterCoefficients(4, 1);
  assert.ok(turbid.b > clear.b);
  assert.ok(silty.a[2] > turbid.a[2]);
  assert.equal(silty.a[0], turbid.a[0]);
});

test('red daylight is essentially gone by 10 m in coastal water; green survives much deeper', function () {
  const water = waterCoefficients(10);
  const ten = daylightAt(10, water);
  assert.ok(ten[0] < 0.03, `red at 10 m: ${ten[0]}`);
  assert.ok(ten[1] > 0.1, `green at 10 m: ${ten[1]}`);
  assert.deepEqual(daylightAt(-3, water), [1, 1, 1]);
});

test('water colour at infinity is never black in shallow water, darkens with depth and is blue-green', function () {
  const water = waterCoefficients(12);
  const shallow = waterRadianceAtInfinity(3, 0, water);
  const deep = waterRadianceAtInfinity(32, 0, water);
  assert.ok(luminance(shallow) > 0.05);
  assert.ok(luminance(deep) < luminance(shallow) / 10);
  assert.ok(shallow[1] > shallow[0] * 3 && shallow[2] > shallow[0] * 3, 'blue-green, not grey');
  // Looking up is brighter than looking down, continuously: no horizon edge.
  const up = waterRadianceAtInfinity(10, 0.2, water);
  const level = waterRadianceAtInfinity(10, 0, water);
  const down = waterRadianceAtInfinity(10, -0.2, water);
  assert.ok(luminance(up) > luminance(level) && luminance(level) > luminance(down));
  const nearUp = waterRadianceAtInfinity(10, 0.001, water);
  assert.ok(Math.abs(luminance(nearUp) - luminance(level)) / luminance(level) < 0.01);
});

test('exposure adapts over a few hundred milliseconds, symmetric in stops', function () {
  let exposure = 1;
  for (let i = 0; i < 6; i++) exposure = adaptExposure(exposure, 4, 1 / 60, 0.35);
  assert.ok(exposure > 1 && exposure < 1.5, `100 ms: ${exposure}`);
  for (let i = 0; i < 120; i++) exposure = adaptExposure(exposure, 4, 1 / 60, 0.35);
  assert.ok(Math.abs(exposure - 4) < 0.05, `2 s: ${exposure}`);
  const up = adaptExposure(1, 4, 0.1, 0.35);
  const down = adaptExposure(1, 0.25, 0.1, 0.35);
  assert.ok(Math.abs(Math.log(up) + Math.log(down)) < 1e-9);
  assert.equal(adaptExposure(0, 2, 0.1, 0.35), 2);
});

test('medium contributors add extinction and coloured backscatter on top of the water', async function () {
  const {combineMedium} = await import('../viewer/fx/water_model.js');
  const water = waterCoefficients(10);
  assert.deepEqual(combineMedium(water, []).c, water.c);
  const silty = combineMedium(water, [null, {extinction: 1.2, scattering: [1.0, 0.9, 0.7]}]);
  for (let i = 0; i < 3; i++) assert.ok(Math.abs(silty.c[i] - water.c[i] - 1.2) < 1e-9);
  assert.ok(silty.b[0] > silty.b[2], 'per-channel scattering tints the backscatter');
  assert.ok(silty.kd[2] > water.kd[2], 'absorbed remainder dims daylight too');
  // Visibility shrinks the way the silt module expects: V ~ 4.8 / c.
  assert.ok(VISIBILITY_CONTRAST / silty.c[1] < 10 / 2);
  assert.ok(luminance(waterRadianceAtInfinity(5, 0, silty)) > 0);
  // A local cloud around the camera attenuates every path but does not shade the water column above it.
  const cloud = combineMedium(water, [{extinction: 1.2, scattering: 1.0, local: true}]);
  assert.deepEqual(cloud.kd, water.kd);
  assert.ok(cloud.c[1] > water.c[1]);
});

test('water type moves the water colour from blue (oceanic) to green (shelf, harbour)', async function () {
  const {WATER_TYPES} = await import('../viewer/fx/water_model.js');
  const ratio = function blueOverGreen(type, visibility = 10) {
    const rgb = waterRadianceAtInfinity(10, 0, waterCoefficients(visibility, 0, type));
    return rgb[2] / rgb[1];
  };
  assert.ok(ratio('oceanic') > ratio('coastal'));
  assert.ok(ratio('coastal') > ratio('shelf'));
  assert.ok(ratio('shelf') > ratio('harbour'));
  assert.ok(ratio('oceanic', 18) > 0.9, `clear oceanic reef water stays blue-cyan: ${ratio('oceanic', 18)}`);
  assert.ok(ratio('shelf') < 0.6, `shelf water is green: ${ratio('shelf')}`);
  assert.deepEqual(waterCoefficients(10, 0, 'unknown'), waterCoefficients(10));
  assert.ok(Object.keys(WATER_TYPES).includes('fresh_clear'));
  // Visibility still sets the green attenuation when the water type leaves room for it.
  assert.ok(Math.abs(waterCoefficients(10, 0, 'shelf').c[1] - 0.48) < 1e-9);
});
