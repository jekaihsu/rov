// Live fish: procedural species bodies stay within their triangle budget per tier and face outwards, and the school
// motion keeps fish near their server school, aligned with it, and pushed away from a vehicle that comes close.
// The drawn levels of detail (fish_schools.js) are checked here with the procedural stand-ins; the kit models
// themselves in test_fish_kit.mjs.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const life = await import('../viewer/fish_life.js');
const schools = await import('../viewer/fish_schools.js');

const BUDGET = {low: 110, medium: 260, high: 360};

function bodyVolume(geometry) {
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

test('every species fits its length and triangle budget on every tier', () => {
  for (const name of Object.keys(life.SPECIES)) {
    for (const detail of ['low', 'medium', 'high']) {
      const geometry = life.fishGeometry(name, detail);
      const triangles = geometry.index.count / 3;
      assert.ok(triangles <= BUDGET[detail], `${name} ${detail}: ${triangles} triangles`);
      geometry.computeBoundingBox();
      const box = geometry.boundingBox;
      const length = box.max.z - box.min.z;
      assert.ok(Math.abs(length - life.SPECIES[name].length) < 0.02 * life.SPECIES[name].length + 0.002,
        `${name} length ${length}`);
      assert.ok(bodyVolume(geometry) > 0, `${name} ${detail} faces outwards`);
      assert.ok(geometry.attributes.aSheen && geometry.attributes.color, 'sheen and countershading');
      geometry.dispose();
    }
  }
  assert.ok(life.fishGeometry('salmon', 'low').index.count < life.fishGeometry('salmon', 'medium').index.count);
});

test('countershading: the back is darker than the belly', () => {
  const geometry = life.fishGeometry('salmon', 'medium');
  const position = geometry.attributes.position;
  const colour = geometry.attributes.color;
  let top = null;
  let bottom = null;
  // Body vertices come first: nose, 10 rings of 8 on the medium tier, tail tip; fins and eyes follow.
  for (let i = 0; i < 82; i++) {
    if (Math.abs(position.getZ(i)) > 0.03) continue;
    if (!top || position.getY(i) > position.getY(top)) top = i;
    if (!bottom || position.getY(i) < position.getY(bottom)) bottom = i;
  }
  assert.ok(colour.getX(top) + colour.getY(top) < 0.5 * (colour.getX(bottom) + colour.getY(bottom)));
});

test('a school holds its heading, stays round its centre and opens up round the vehicle', () => {
  const world = {scenario: {key: 'open_water'}, biome: 'temperate', world_seed: 3,
    habitat: {fish_schools: [{id: 'school-0', pos: [10, 0, 6], count: 30, variant: 1}]}};
  assert.equal(schools.schoolSpecies(world), 'saithe');
  assert.equal(schools.schoolSpecies({scenario: {key: 'aquaculture_pen_slack'}}), 'salmon');
  assert.equal(schools.schoolSpecies({scenario: {key: 'coral_reef'}, biome: 'reef'}), 'fusilier');
  const group = new THREE.Group();
  const drawn = schools.createSharedSchools(group, world, 'medium', 3);
  assert.equal(group.children.length, 1, 'one object per school');
  assert.equal(drawn.schools[0].species, 'saba', 'offshore school 0');
  assert.equal(drawn.observationTargets[0].mesh, drawn.schools[0].mesh, 'the photo target covers every level');
  const camera = {position: new THREE.Vector3(0, -6, 10)};
  // Server school swimming north (+Z in three space) at 0.4 m/s, vehicle far away.
  const state = {pos: [-20, 0, 6], rc: {right_switch: 0},
    environment: {fish_schools: [{id: 'school-0', pos: [10, 0, 6], vel: [0.4, 0, 0]}]}};
  for (let i = 0; i < 120; i++) drawn.update(1 / 30, i / 30, camera, state);
  const meshes = schools.schoolMeshes(drawn.schools[0]);
  assert.equal(meshes.reduce((sum, mesh) => sum + mesh.count, 0), 30, 'every fish is drawn once');
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const rotation = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  const centre = new THREE.Vector3(0, -6, 10);
  let aligned = 0;
  let nearest = Infinity;
  const places = [];
  for (const mesh of meshes) {
    for (let i = 0; i < mesh.count; i++) {
      mesh.getMatrixAt(i, matrix);
      matrix.decompose(position, rotation, scale);
      assert.ok(position.distanceTo(centre) < 2.6, 'fish stay round the server centre');
      const nose = new THREE.Vector3(0, 0, 1).applyQuaternion(rotation);
      if (nose.z > Math.cos(THREE.MathUtils.degToRad(30))) aligned++;
      places.push(position.clone());
    }
  }
  assert.ok(aligned >= 30 * 0.9, `${aligned} of 30 within 30 degrees of the school heading`);
  for (let i = 0; i < places.length; i++) {
    for (let j = i + 1; j < places.length; j++) nearest = Math.min(nearest, places[i].distanceTo(places[j]));
  }
  assert.ok(nearest > 0.05, 'no two fish in the same place');
  // Park the vehicle in the middle of the school with the lamps on: nearby fish move out of its way.
  state.pos = [10, 0, 6];
  state.rc.right_switch = 2;
  for (let i = 0; i < 60; i++) drawn.update(1 / 30, 4 + i / 30, camera, state);
  let inside = 0;
  for (const mesh of meshes) {
    for (let i = 0; i < mesh.count; i++) {
      mesh.getMatrixAt(i, matrix);
      position.setFromMatrixPosition(matrix);
      if (position.distanceTo(centre) < 0.5) inside++;
    }
  }
  assert.equal(inside, 0, 'no fish left within 0.5 m of the vehicle');
  for (const mesh of meshes) {
    const swim = mesh.geometry.attributes.aSwim;
    if (mesh.count) assert.ok(swim.getY(0) >= 1 && swim.getY(0) <= 1.5, 'tail-beat amplitude scale');
  }
});

test('wild schools use the species field from habitat data', () => {
  const world = {scenario: {key: 'aquaculture_pen'}, biome: 'aquaculture', world_seed: 71,
    habitat: {fish_schools: [
      {id: 'pen-school-0', pos: [34, 0, 6], count: 48, variant: 0},
      {id: 'wild-school-1', pos: [5, 1, 3], count: 16, variant: 0, wild: true, species: 'aji'},
    ]}};
  const drawn = schools.createSharedSchools(new THREE.Group(), world, 'low', 71);
  assert.equal(drawn.schools[0].species, 'madai');
  assert.equal(drawn.schools[1].species, 'aji');
  assert.equal(drawn.schools[1].farm, false);
});

test('pen fish are the farmed species and keep the pen layout', () => {
  const world = {scenario: {key: 'aquaculture_pen'}, biome: 'aquaculture', world_seed: 71,
    habitat: {fish_schools: [{id: 'pen-school-0', pos: [34, 0, 6], count: 48, variant: 0}]}};
  const group = new THREE.Group();
  const drawn = schools.createSharedSchools(group, world, 'low', 71);
  const school = drawn.schools[0];
  assert.equal(school.fish.length, 12, 'low tier draws a quarter of the pen school, as before');
  assert.equal(school.species, 'madai');
  assert.equal(school.meshes.full, undefined, 'no full model on the low tier');
  assert.equal(school.meshes.card.geometry.userData.fishSpecies, 'salmon', 'salmon silhouette at distance');
  const server = {id: 'pen-school-0', pos: [34, 0, 6], vel: [0, 0.3, 0]};
  const state = {pos: [3, 0, 7], environment: {fish_schools: [server]}};
  drawn.update(1 / 30, 1, {position: new THREE.Vector3()}, state);
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  let drawnFish = 0;
  for (const mesh of schools.schoolMeshes(school)) {
    for (let i = 0; i < mesh.count; i++) {
      mesh.getMatrixAt(i, matrix);
      position.setFromMatrixPosition(matrix);
      assert.ok(Math.hypot(position.x, position.z - 24) < 17.5, 'inside the 18 m net');
      drawnFish++;
    }
  }
  assert.equal(drawnFish, 12);
});

test('a dense pen school shares the scene level of detail, keeps sizes within 15 % and stays in the net', () => {
  const world = {scenario: {key: 'aquaculture_pen'}, biome: 'aquaculture', world_seed: 71,
    habitat: {fish_schools: [{id: 'pen-school-0', pos: [34, 0, 6], count: 48, variant: 0},
      {id: 'pen-school-1', pos: [31.1, 7.1, 9], count: 48, variant: 1}]}};
  const drawn = schools.createSharedSchools(new THREE.Group(), world, 'medium', 71);
  const lod = schools.FISH_LOD.medium;
  const school = drawn.schools[0];
  assert.equal(school.fish.length, 96, 'medium draws two fish per server fish');
  assert.ok(school.meshes.card.geometry.index.count < school.meshes.full.geometry.index.count,
    'far fish use the cheap body');
  const sizes = school.fish.map((fish) => fish.scale);
  const mean = sizes.reduce((sum, size) => sum + size, 0) / sizes.length;
  assert.ok(sizes.every((size) => Math.abs(size / mean - 1) < 0.17), 'size spread about +-15 %');
  const servers = [{id: 'pen-school-0', pos: [34, 0, 6], vel: [0, 0.3, 0]},
    {id: 'pen-school-1', pos: [31.1, 7.1, 9], vel: [-0.2, 0.2, 0]}];
  const camera = {position: new THREE.Vector3(0, -6, 33)};
  drawn.update(1 / 30, 1, camera, {pos: [3, 0, 7], environment: {fish_schools: servers}});
  const counts = {full: 0, distance: 0, card: 0};
  const reach = {full: 0, distance: 0, card: Infinity};
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  for (const each of drawn.schools) {
    for (const mesh of schools.schoolMeshes(each)) {
      const level = mesh.userData.fishLevel;
      counts[level] += mesh.count;
      for (let i = 0; i < mesh.count; i++) {
        mesh.getMatrixAt(i, matrix);
        position.setFromMatrixPosition(matrix);
        assert.ok(Math.hypot(position.x, position.z - 24) < 17.5, 'inside the 18 m net');
        const range = position.distanceTo(camera.position);
        if (level === 'card') reach.card = Math.min(reach.card, range);
        else reach[level] = Math.max(reach[level], range);
      }
    }
  }
  assert.equal(counts.full + counts.distance + counts.card, 192, 'every fish is drawn once');
  assert.ok(counts.full > 0 && counts.full <= lod.full, `full ${counts.full} (scene-wide cap)`);
  assert.ok(counts.distance > 0 && counts.distance <= lod.distance, `distance ${counts.distance}`);
  assert.ok(reach.full < lod.fullRange && reach.distance < lod.distanceRange, 'detailed fish are near');
  assert.ok(reach.full <= reach.distance, 'the nearest fish get the full model');
  if (counts.distance === lod.distance) assert.ok(reach.card >= reach.distance, 'cards only behind the others');
});

test('reef species carry their own colour patterns and are not mirrors', () => {
  function average(name) {
    const colour = life.fishGeometry(name, 'medium').attributes.color;
    const sum = [0, 0, 0];
    for (let i = 0; i < colour.count; i++) {
      sum[0] += colour.getX(i);
      sum[1] += colour.getY(i);
      sum[2] += colour.getZ(i);
    }
    return sum.map((value) => value / colour.count);
  }
  const butterfly = average('butterfly');
  const damselColour = life.fishGeometry('damsel', 'medium').attributes.color;
  const surgeon = average('surgeon');
  assert.ok(butterfly[0] > butterfly[2] * 2, 'butterflyfish are yellow');
  let blue = 0;
  for (let i = 0; i < damselColour.count; i++) blue += damselColour.getZ(i) > 2 * damselColour.getX(i) ? 1 : 0;
  assert.ok(blue > damselColour.count * 0.3, 'damselfish: blue back and head, yellow belly and tail');
  assert.ok(surgeon[0] + surgeon[1] + surgeon[2] < 0.6, 'surgeonfish are dark');
  assert.ok(life.SPECIES.butterfly.sheen < 0.2 && life.SPECIES.salmon.sheen === 1);
});
