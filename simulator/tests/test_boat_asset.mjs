// Shipped asset contract: the actual compressed GLB must contain usable menu attachments and display UVs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const bytes = readFileSync(new URL('../viewer/models/small_boat.glb', import.meta.url));
const doc = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString());

test('small boat ships all camera, vehicle, equipment and replaceable display nodes', function () {
  const names = new Set(doc.nodes.map(node => node.name));
  const required = ['anchor_cockpit', 'anchor_platform', 'anchor_logbook', 'anchor_horizon',
    'target_cockpit', 'target_platform', 'target_logbook', 'target_horizon',
    'rov_slot_0', 'rov_slot_1', 'screen_main', 'screen_log', 'frame_licence',
    'lifebuoy_slot', 'buoy_slot'];
  for (let i = 0; i < 6; i++) required.push(`gear_slot_${i}`, `photo_wall_${i}`);
  for (const name of required) assert.ok(names.has(name), name);
  for (const node of doc.nodes.filter(node => /^(screen_|frame_licence|photo_wall_)/.test(node.name))) {
    assert.notEqual(node.mesh, undefined, node.name);
    for (const primitive of doc.meshes[node.mesh].primitives) {
      const uv = doc.accessors[primitive.attributes.TEXCOORD_0];
      assert.ok(uv, `${node.name} needs replaceable UVs`);
      assert.equal(uv.type, 'VEC2');
    }
  }
});

test('small boat stays inside triangle budget and uses compressed geometry and WebP', function () {
  const triangles = doc.meshes.flatMap(mesh => mesh.primitives)
    .reduce((sum, primitive) => sum + doc.accessors[primitive.indices].count / 3, 0);
  assert.ok(triangles <= 60000, triangles);
  assert.ok(doc.extensionsUsed.includes('EXT_meshopt_compression'));
  assert.ok(doc.images.every(image => image.mimeType === 'image/webp'));
});
