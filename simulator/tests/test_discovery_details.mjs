// A photo must resolve the subject actually drawn at the host surface, even after the near batch is repacked.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {installDiscoveryDetails} = await import('../viewer/discovery_details.js');
const {inspectObservation} = await import('../viewer/observation_camera.js');

function marker(id, kind, north) {
  return {id, kind, pos: [north, 0, 8], normal: [0, 0, -1], yaw: 31};
}

function setup(discoveries) {
  const world = {habitat: {discoveries}, scenario: {visibility_m: 6}};
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, 16 / 9, .05, 100);
  const targets = [];
  const details = installDiscoveryDetails(scene, world, targets);
  return {world, scene, camera, targets, details};
}

function aim(context, north) {
  const {camera, details} = context;
  camera.position.set(.04, -7.44, north - .28);
  camera.lookAt(0, -8, north);
  details.update(camera);
}

function photo(context) {
  const {world, scene, camera, targets} = context;
  return inspectObservation({world, scene, camera, camMode: 'onboard', environment: {observationTargets: targets}});
}

test('every attached discovery has an opaque, photographable close-up silhouette', () => {
  const kinds = ['mussels', 'barnacles', 'limpet', 'anemones', 'brittle_star', 'shell_hash', 'crab_molt',
    'rope_offcut', 'shackle', 'bottle_glass', 'ceramic_shard', 'net_patch', 'rust_flake'];
  for (const kind of kinds) {
    const context = setup([marker(kind + '-1', kind, 0)]);
    aim(context, 0);
    const evidence = photo(context);
    assert.ok(evidence.ok, kind + ': ' + JSON.stringify(evidence));
    assert.equal(evidence.entity_id, kind + '-1');
    const geo = context.targets[0].mesh.geometry;
    geo.computeBoundingBox();
    assert.ok(geo.boundingBox.max.y <= .09, kind + ' thickness exceeds attachment envelope');
    assert.ok(geo.index.count / 3 < 2500, kind + ' close-up triangle count');
    context.details.dispose();
  }
});

test('near batches skip distant geometry and keep entity identity when the camera crosses the site', () => {
  const context = setup([marker('a', 'shackle', 20), marker('b', 'shackle', 22)]);
  const {scene, targets} = context;
  aim(context, 0);
  assert.equal(scene.children.length, 0);
  aim(context, 22);
  assert.equal(scene.children.length, 1);
  assert.deepEqual(targets.map(t => t.instanceIds[0]), [0, 1]);
  assert.equal(photo(context).entity_id, 'b');
  const closeFaces = targets[1].mesh.geometry.index.count;
  aim(context, 30);
  assert.equal(targets[0].mesh, null);
  assert.equal(targets[1].instanceIds[0], 0);
  assert.equal(targets[1].mesh.count, 1);
  assert.ok(targets[1].mesh.geometry.index.count < closeFaces);
  aim(context, 45);
  assert.equal(photo(context).ok, false);
  assert.ok(targets.every(t => t.mesh === null));
  context.details.dispose();
});

test('colonies on a vertical host face the water and remain occluded from its far side', () => {
  const colony = {...marker('pile-mussels', 'mussels', 0), normal: [-1, 0, 0]};
  const context = setup([colony]);
  const {camera, details, scene} = context;
  const host = new THREE.Mesh(new THREE.BoxGeometry(1, 1, .25), new THREE.MeshStandardMaterial());
  host.position.set(0, -8, .125);
  scene.add(host);
  camera.position.set(0, -8, -.6);
  camera.lookAt(0, -8, 0);
  details.update(camera);
  assert.equal(photo(context).entity_id, 'pile-mussels');
  assert.ok(photo(context).ok);
  camera.position.z = .65;
  camera.lookAt(0, -8, 0);
  details.update(camera);
  assert.equal(photo(context).ok, false);
  details.dispose();
});
