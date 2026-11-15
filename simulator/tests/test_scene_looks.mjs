// Pen and reef look modules: shapes stay inside the server's envelopes and the dressing is reef-only.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const reef = await import('../viewer/reef_life.js');
const pen = await import('../viewer/pen_life.js');
const {objectiveNearFade} = await import('../viewer/hud/objective_fade.js');

function signedVolume(geometry) {
  const position = geometry.attributes.position;
  const index = geometry.index.array;
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  let volume = 0;
  for (let i = 0; i < index.length; i += 3) {
    a.fromBufferAttribute(position, index[i]);
    b.fromBufferAttribute(position, index[i + 1]);
    c.fromBufferAttribute(position, index[i + 2]);
    volume += a.dot(b.cross(c)) / 6;
  }
  return volume;
}

test('every coral style fits the collision capsule envelope and keeps the low tier light', () => {
  for (let style = 0; style < reef.CORAL_STYLES.length; style++) {
    for (const detail of ['low', 'medium', 'high']) {
      const geometry = reef.reefCoralGeometry(style, detail);
      geometry.computeBoundingBox();
      const box = geometry.boundingBox;
      assert.ok(box.min.y > -0.06 && box.max.y <= 1.0, `${style} ${detail} height ${box.max.y}`);
      assert.ok(Math.max(-box.min.x, box.max.x, -box.min.z, box.max.z) <= 0.7, `${style} ${detail} reach`);
      assert.ok(geometry.attributes.color, 'vertex shade');
      const triangles = geometry.index.count / 3;
      assert.ok(triangles <= (detail === 'low' ? 220 : 560), `${style} ${detail} ${triangles} triangles`);
      // Single-sided styles must face outwards: positive enclosed volume.
      if (reef.CORAL_STYLES[style] !== 'fan') assert.ok(signedVolume(geometry) > 0.005, `${style} ${detail} winding`);
      geometry.dispose();
    }
  }
});

test('coral style and tint are stable per entity and use both styles of a variant', () => {
  const styles = new Set();
  for (let i = 0; i < 60; i++) {
    const entity = {id: `coral-${i}`, variant: 1};
    assert.equal(reef.reefCoralStyle(entity), reef.reefCoralStyle({...entity}));
    assert.equal(reef.reefCoralTint(entity).getHex(), reef.reefCoralTint(entity).getHex());
    styles.add(reef.reefCoralStyle(entity));
  }
  assert.deepEqual([...styles].sort(), [1, 3]);
});

function reefWorld(biome) {
  const depths = Array.from({length: 3}, (_, n) => Array.from({length: 3}, (_, e) => 14 - n * 0.5 - e * 0.25));
  const entities = [0, 1, 2, 3].map((i) => ({id: `coral-${i}`, kind: 'coral', variant: i % 3, scale: 0.5 + i * 0.1,
    pos: [2 + i * 2, 3, 13], yaw: 0}));
  return {biome, world_seed: 5, seabed_depth: 14, habitat: {entities},
    terrain: {origin: [0, 0], spacing: 5, size: [3, 3], depths}};
}

test('reef dressing exists only on reefs, sits on the terrain and stays low', () => {
  assert.equal(reef.installReefDressing(new THREE.Group(), reefWorld('seagrass'), 'medium'), null);
  const world = reefWorld('reef');
  assert.equal(reef.terrainHeight(world, 5, 5), -13.25);
  assert.equal(reef.terrainHeight(world, 2.5, 0), -13.75);
  const counts = {};
  for (const detail of ['low', 'medium']) {
    const group = new THREE.Group();
    const dressing = reef.installReefDressing(group, world, detail);
    dressing.update(3.5);
    counts[detail] = group.children.reduce((sum, mesh) => sum + mesh.count, 0);
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const scale = new THREE.Vector3();
    for (const mesh of group.children) {
      if (mesh.name === 'reef-fish') continue;
      for (let i = 0; i < mesh.count; i++) {
        mesh.getMatrixAt(i, matrix);
        matrix.decompose(position, new THREE.Quaternion(), scale);
        const floor = reef.terrainHeight(world, position.z, -position.x);
        assert.ok(Math.abs(position.y - floor) < 0.06, `${mesh.name} on the bed`);
        assert.ok(scale.y <= 0.31, `${mesh.name} stays low (${scale.y})`);
      }
    }
  }
  assert.ok(counts.low < counts.medium);
});

test('pen fish circle the pen inside the net and face along their track', () => {
  const geometry = pen.salmonGeometry();
  assert.ok(geometry.index.count / 3 <= 120);
  assert.ok(signedVolume(geometry) > 1e-5, 'body faces outwards (fins are drawn on both sides)');
  geometry.computeBoundingBox();
  assert.ok(geometry.boundingBox.max.z - geometry.boundingBox.min.z < 0.32);
  let seed = 1;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const school = {pos: new THREE.Vector3(-14, -8, 24), vel: new THREE.Vector3(0, 0, -0.3)};
  const turn = pen.penTurn(school);
  const position = new THREE.Vector3();
  const euler = new THREE.Euler();
  const later = new THREE.Vector3();
  for (let i = 0; i < 40; i++) {
    const fish = {offset: pen.penFishOffset(random), phase: random() * 6};
    pen.placePenFish(school, fish, 2, turn, position, euler);
    assert.ok(Math.hypot(position.x, position.z - 24) < 17.5, 'inside the 18 m net');
    assert.ok(position.y < -1 && position.y > -15.5, 'between surface and bottom net');
    // The nose (+Z turned by the heading) points where the school is going.
    const nose = new THREE.Vector3(Math.sin(euler.y), 0, Math.cos(euler.y));
    const moved = {pos: school.pos.clone().addScaledVector(school.vel, 1), vel: school.vel};
    pen.placePenFish(moved, fish, 2, turn, later, new THREE.Euler());
    assert.ok(nose.dot(later.sub(position).setY(0).normalize()) > 0.5, 'heading follows motion');
  }
});

test('a ring mark fades out when the camera stands inside it', () => {
  const mark = {g: {position: new THREE.Vector3(0, 0, 0)}, mat: {opacity: 0.8}, wire: {opacity: 0.07}};
  const camera = {position: new THREE.Vector3(0.2, 0.1, 0)};
  assert.equal(objectiveNearFade(mark, 1, camera), 0);
  assert.equal(mark.mat.opacity, 0);
  assert.equal(mark.wire.opacity, 0);
  mark.mat.opacity = 0.8;
  camera.position.set(4, 0, 0);
  assert.equal(objectiveNearFade(mark, 1, camera), 1);
  assert.equal(mark.mat.opacity, 0.8);
  assert.equal(mark.wire.opacity, 0.07);
});
