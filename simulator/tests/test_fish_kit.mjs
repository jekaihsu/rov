// Kit fish (fish_kit.js): every species a site uses is vendored with its three levels, the models load into
// nose-forward bodies of the species' length with fins kept out of the silver sheen, the far cards fold, and the
// scene-wide level of detail keeps every tier within its triangle budget.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import {readFileSync, statSync} from 'node:fs';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const kit = await import('../viewer/fish_kit.js');
const schools = await import('../viewer/fish_schools.js');

const FOLDER = new URL('../viewer/models/fish/', import.meta.url);
// Fish triangles allowed per tier on a site with free schools (4 server schools of up to 40 fish): low stays below
// the procedural fish it replaces (9.6k), see docs/design/fish-kit/README.md.
const FREE_SITE_BUDGET = {low: 9600, medium: 40000, high: 75000};

function parse(name) {
  const bytes = readFileSync(new URL(name, FOLDER));
  return kit.parseFishGlb(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}

function triangles(geometry) {
  return geometry.index.count / 3;
}

const used = [...new Set(Object.values(kit.SITE_SPECIES).flat())];

test('every species a site uses is vendored with all three levels, each file under 2 MB', () => {
  assert.ok(used.includes(kit.FARMED_SPECIES));
  for (const species of used) {
    assert.ok(kit.KIT_SPECIES[species], `${species} has a drawn length`);
    for (const suffix of ['.glb', '_lo.glb', '_card.webp']) {
      const size = statSync(new URL(`${species}${suffix}`, FOLDER)).size;
      assert.ok(size > 1000 && size < 2 * 1024 * 1024, `${species}${suffix}: ${size} bytes`);
    }
  }
});

test('sites get coastal East Asian species and the pen its farmed species', () => {
  const pen = {scenario: {key: 'aquaculture_pen'}, biome: 'aquaculture'};
  assert.equal(kit.fishSite(pen), 'pen');
  assert.equal(kit.schoolKitSpecies(pen, 'pen-school-5'), 'madai');
  const harbour = {scenario: {key: 'harbor_inspection'}, biome: 'harbor'};
  assert.equal(kit.fishSite(harbour), 'harbour');
  assert.ok(['aji', 'kurodai', 'mebaru'].includes(kit.schoolKitSpecies(harbour, 'school-3')));
  const reef = {scenario: {key: 'coral_reef'}, biome: 'reef'};
  assert.equal(kit.schoolKitSpecies(reef, 'school-0'), 'isaki');
  const wreck = {scenario: {key: 'wreck_survey'}, biome: 'temperate', obstacles: [{kind: 'wreck'}]};
  assert.ok(['isaki', 'mebaru'].includes(kit.schoolKitSpecies(wreck, 'school-1')));
  const jacket = {scenario: {key: 'jacket_inspection'}, biome: 'temperate'};
  assert.ok(['saba', 'aji', 'buri'].includes(kit.schoolKitSpecies(jacket, 'school-2')));
});

test('kit models become nose-forward bodies of the species length; fins carry no silver sheen', () => {
  for (const species of used) {
    const full = parse(`${species}.glb`);
    const distance = parse(`${species}_lo.glb`);
    assert.ok(full.atlas && full.atlas.type === 'image/webp', `${species}: full model carries the atlas`);
    assert.equal(distance.atlas, null, `${species}: distance model shares the full model's atlas`);
    const length = kit.KIT_SPECIES[species].length;
    const body = kit.kitGeometry(full, length);
    const far = kit.kitGeometry(distance, length);
    assert.ok(triangles(body) > 3000 && triangles(body) < 6000, `${species} full ${triangles(body)}`);
    assert.ok(triangles(far) > 400 && triangles(far) < 900, `${species} distance ${triangles(far)}`);
    body.computeBoundingBox();
    const box = body.boundingBox;
    assert.ok(Math.abs(box.max.z - box.min.z - length) < 0.03 * length, `${species} length`);
    assert.ok(box.max.x - box.min.x < 0.45 * length, `${species}: slim from above, so +Z is the long axis`);
    // The eye (kit part 6) sits in the front fifth of the body: the nose points along +Z.
    const position = body.attributes.position;
    let eye = -Infinity;
    for (let i = 0; i < position.count; i++) {
      if (Math.round(full.parts[i * 3]) === 6) eye = Math.max(eye, position.getZ(i));
    }
    assert.ok(eye > box.max.z - 0.25 * length, `${species} eye near the nose`);
    const sheen = body.attributes.aSheen;
    for (let i = 0; i < sheen.count; i++) {
      const part = Math.round(full.parts[i * 3]);
      if (part >= 1 && part <= 6) assert.equal(sheen.getX(i), 0, `${species}: fin or eye vertex ${i} is not silver`);
    }
    const {body: swim, envelope} = body.userData.fishSwim;
    assert.ok(Math.abs(swim.snout - 0.47 * length) < 1e-9 && swim.length === length && swim.wave > 4);
    const tip = envelope[0] + envelope[1] + envelope[2];
    assert.ok(tip > 0.03 && tip < 0.15, `${species}: tail amplitude ${tip} body lengths`);
  }
});

test('far cards are 16 triangles in the body frame with folding side and top halves', () => {
  const full = parse('madai.glb');
  const card = kit.cardGeometry(full, kit.KIT_SPECIES.madai.length);
  assert.equal(triangles(card), 16);
  card.computeBoundingBox();
  const body = kit.kitGeometry(full, kit.KIT_SPECIES.madai.length);
  body.computeBoundingBox();
  assert.ok(card.boundingBox.min.distanceTo(body.boundingBox.min) < 1e-4, 'card spans the model bounds');
  assert.ok(card.boundingBox.max.distanceTo(body.boundingBox.max) < 1e-4, 'card spans the model bounds');
  const fold = card.attributes.aCard;
  const uv = card.attributes.uv;
  for (let i = 0; i < fold.count; i++) {
    assert.ok(uv.getX(i) >= 0 && uv.getX(i) <= 1 && uv.getY(i) >= 0 && uv.getY(i) <= 1);
    // Side half samples the top 80 of 128 rows, top half the rest.
    assert.ok(fold.getX(i) ? uv.getY(i) >= 80 / 128 - 1e-6 : uv.getY(i) <= 80 / 128 + 1e-6);
  }
  const material = kit.kitMaterial({card, cardMap: new THREE.Texture()}, 'card');
  assert.ok('FISH_CARD' in material.defines && 'FISH_PHOTO' in material.defines);
  assert.equal(material.side, THREE.DoubleSide);
  assert.equal(material.alphaTest, 0.5);
});

function worstCaseFish(detail, fishCount, perLevel) {
  const lod = schools.FISH_LOD[detail];
  const full = Math.min(lod.full, fishCount);
  const distance = Math.min(lod.distance, fishCount - full);
  const cards = fishCount - full - distance;
  return full * perLevel.full + distance * perLevel.distance + cards * perLevel.card;
}

test('the scene-wide level of detail keeps every tier within its fish triangle budget', () => {
  const perLevel = {full: 0, distance: 0, card: 16};
  for (const species of used) {
    perLevel.full = Math.max(perLevel.full, triangles(kit.kitGeometry(parse(`${species}.glb`), 1)));
    perLevel.distance = Math.max(perLevel.distance, triangles(kit.kitGeometry(parse(`${species}_lo.glb`), 1)));
  }
  for (const detail of ['low', 'medium', 'high']) {
    const total = worstCaseFish(detail, 4 * 40, perLevel);
    assert.ok(total <= FREE_SITE_BUDGET[detail], `${detail}: ${total} fish triangles on a free-school site`);
  }
  assert.ok(schools.FISH_LOD.low.full === 0, 'no full models on the low tier');
});

test('levels go to the nearest fish of the whole scene, within the tier counts and ranges', () => {
  const near = {stage: {distance: Float32Array.from([0.5, 2.5, 30, 3.5]), level: new Uint8Array(4)}};
  const far = {stage: {distance: Float32Array.from([1.0, 9, 12, 2.0]), level: new Uint8Array(4)}};
  const entries = [near, far].flatMap((school) => [0, 1, 2, 3].map((index) => ({school, index})));
  schools.assignLevels(entries, {full: 2, distance: 3, fullRange: 3, distanceRange: 10});
  assert.deepEqual([...near.stage.level], [0, 1, 2, 1]);
  assert.deepEqual([...far.stage.level], [0, 2, 2, 1], 'beyond the distance cap or range fish are cards');
});
