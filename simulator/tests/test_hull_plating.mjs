// Plating seams must span both axes on the flat bottom directly above the longitudinal survey route.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const {shipHullGeometry} = await import('../viewer/structures.js');

test('keel plates span the breadth as well as the length of a rotated cargo hull', () => {
  const geometry = shipHullGeometry({length: 80, beam: 18, draft: 8, center: [50, 3, 0], yaw_deg: 37});
  const {position, normal, uv} = geometry.attributes;
  let plates = 0;
  for (let i = 0; i < position.count; i += 3) {
    if (position.getY(i) !== -8 || normal.getY(i) > -.995) continue;
    const du1 = uv.getX(i + 1) - uv.getX(i);
    const dv1 = uv.getY(i + 1) - uv.getY(i);
    const du2 = uv.getX(i + 2) - uv.getX(i);
    const dv2 = uv.getY(i + 2) - uv.getY(i);
    assert.ok(Math.abs(du1 * dv2 - du2 * dv1) > 1e-9);
    plates++;
  }
  assert.ok(plates > 20);
  geometry.dispose();
});
