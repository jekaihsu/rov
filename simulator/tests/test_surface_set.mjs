// Above-water set (viewer/surface_set.js, viewer/wind_farm.js): which sites get a wind farm and land, that the
// farm is a staggered grid at real turbine spacing, and that the turbine model keeps slender proportions.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {surfacePlan, buildSurfaceSet} = await import('../viewer/surface_set.js');
const {farmLayout, turbineGeometry, TURBINE_TYPES, FARM_REACH} = await import('../viewer/wind_farm.js');

function seeded(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function world(key, biome, waterType, kinds = []) {
  const obstacles = kinds.map((kind, i) => ({type: 'cylinder', kind, p0: [20 + i, 0, 30], p1: [20 + i, 0, -3]}));
  return {scenario: {key, biome, water_type: waterType}, obstacles};
}

test('offshore wind sites stand inside a farm on their own foundation type', function () {
  const jacket = surfacePlan(world('jacket_inspection', 'temperate', 'shelf', ['jacket_leg', 'brace']));
  assert.equal(jacket.farm.type, 'jacket');
  assert.equal(jacket.farm.mode, 'inside');
  assert.ok(Math.abs(jacket.farm.anchor.z - 20) < 1e-9, 'the farm grid is anchored on the inspected jacket');
  const monopile = surfacePlan(world('monopile_current', 'temperate', 'shelf', ['monopile', 'transition_piece']));
  assert.equal(monopile.farm.type, 'large');
  assert.equal(monopile.farm.mode, 'inside');
});

test('harbours, fish farms, reefs, lakes and the pool get no farm; the pool gets no horizon at all', function () {
  assert.equal(surfacePlan(world('harbor_inspection', 'harbor', 'harbour', ['quay', 'pile'])).farm, null);
  assert.equal(surfacePlan(world('random', 'temperate', 'shelf', ['quay', 'tyre'])).farm, null);
  assert.equal(surfacePlan(world('aquaculture_pen', 'aquaculture', 'shelf', ['pen_net'])).farm, null);
  assert.equal(surfacePlan(world('coral_reef', 'reef', 'oceanic')).farm, null);
  assert.equal(surfacePlan(world('lake', 'temperate', 'fresh_clear')).farm, null);
  const pool = surfacePlan(world('tutorial_pool', 'temperate', 'fresh_clear', ['wall']));
  assert.deepEqual([pool.farm, pool.coast, pool.vessels.length, pool.buoys], [null, null, 0, false]);
  const open = surfacePlan(world('open_water', 'temperate', 'shelf'));
  assert.equal(open.farm.mode, 'distant');
});

test('a farm is dozens of turbines in a staggered grid, five to seven rotor diameters apart', function () {
  for (const type of Object.keys(TURBINE_TYPES)) {
    const plan = {type, mode: 'inside', anchor: {x: 0, z: 0}, windAngle: 0.7};
    const layout = farmLayout(plan, seeded(3));
    assert.ok(layout.turbines.length >= 30, `${type}: ${layout.turbines.length} turbines`);
    assert.ok(layout.substation, 'one offshore substation');
    const rotor = TURBINE_TYPES[type].rotor;
    let closest = Infinity;
    for (const a of layout.turbines) {
      assert.ok(Math.hypot(a.x, a.z) > 0.8 * layout.spacing.across, 'no turbine on the inspected foundation');
      for (const b of layout.turbines) {
        if (a !== b) closest = Math.min(closest, Math.hypot(a.x - b.x, a.z - b.z));
      }
    }
    assert.ok(closest > 4.5 * rotor && closest < 8 * rotor, `${type}: nearest neighbour ${closest.toFixed(0)} m`);
    const yaws = layout.turbines.map((t) => t.yaw);
    const spread = Math.max(...yaws) - Math.min(...yaws);
    assert.ok(spread > 0 && spread < THREE.MathUtils.degToRad(10), 'rotors face one wind, a few degrees apart');
    const turning = layout.turbines.filter((t) => t.omega > 0.1);
    for (const t of turning) {
      const rpm = t.omega * 60 / (Math.PI * 2);
      assert.ok(rpm > 5 && rpm < 13, `${type}: ${rpm.toFixed(1)} rpm`);
    }
    assert.ok(new Set(layout.turbines.map((t) => t.phase.toFixed(3))).size === layout.turbines.length,
      'rotors are not in sync');
  }
});

test('a distant farm starts kilometres off and recedes away from the site', function () {
  const plan = {type: 'mid', mode: 'distant', windAngle: 0.4 + Math.PI, bearing: 0.4, offset: 3000};
  const layout = farmLayout(plan, seeded(9));
  const along = (t) => t.x * Math.cos(0.4) + t.z * Math.sin(0.4);
  const nearest = Math.min(...layout.turbines.map((t) => Math.hypot(t.x, t.z)));
  assert.ok(nearest > 1500, `nearest turbine ${nearest.toFixed(0)} m`);
  const mean = layout.turbines.reduce((sum, t) => sum + along(t), 0) / layout.turbines.length;
  assert.ok(mean > 3000, 'rows extend away from the site');
});

test('turbine models keep slender, real proportions', function () {
  for (const [name, type] of Object.entries(TURBINE_TYPES)) {
    assert.ok(type.hub >= 100 && type.hub <= 150, `${name} hub height`);
    assert.ok(type.rotor >= 150 && type.rotor <= 236, `${name} rotor diameter`);
    assert.ok(type.rotor / 2 / type.maxChord > 15, `${name} blades are slender`);
    assert.ok(type.hub - type.rotor / 2 > type.tpTop + 4, `${name} tips clear the platform`);
    for (const detailed of [true, false]) {
      const geometry = turbineGeometry(type, detailed);
      // Rotor vertices are stored about the hub (the shader turns and places them), the rest in place.
      const position = geometry.attributes.position;
      const spin = geometry.attributes.aSpin;
      let tip = 0;
      let top = 0;
      for (let i = 0; i < position.count; i++) {
        if (spin.getX(i) > 0.5) tip = Math.max(tip, Math.hypot(position.getX(i), position.getY(i)));
        else top = Math.max(top, position.getY(i));
      }
      assert.ok(Math.abs(tip - type.rotor / 2) < 1, `${name} blade tip radius ${tip}`);
      assert.ok(top > type.hub && top < type.hub + type.nacelle[1], `${name} nacelle top ${top}`);
      const triangles = geometry.index.count / 3;
      assert.ok(triangles < (detailed ? 2600 : 700), `${name} ${detailed ? 'near' : 'far'}: ${triangles} triangles`);
      assert.ok(geometry.attributes.aSpin && geometry.attributes.color, 'rotor flag and paint');
    }
  }
});

test('the whole set builds, and props are kept inside the far plane by the horizon shader', function () {
  assert.ok(FARM_REACH < 2600);
  const centre = new THREE.Vector3();
  const set = buildSurfaceSet(world('jacket_inspection', 'temperate', 'shelf', ['jacket_leg']), centre, seeded(1),
    {detail: 'low'});
  const meshes = [];
  set.group.traverse((object) => {
    if (object.isMesh) meshes.push(object);
  });
  assert.equal(set.group.getObjectByName('wind-farm-near'), undefined, 'low detail draws the simple model only');
  assert.ok(set.group.getObjectByName('wind-farm-far').count >= 30);
  assert.ok(set.vessels.every((v) => v.v.isGroup && Number.isFinite(v.speed)));
  assert.equal(set.buoys.length, 5);
  assert.ok(meshes.length < 40, `${meshes.length} meshes`);
});

test('blades read as curved sabres: straight leading edge, trailing edge bulging near the root', function () {
  const type = TURBINE_TYPES.jacket;
  const geometry = turbineGeometry(type, true);
  const position = geometry.attributes.position;
  const blade = geometry.attributes.aBlade;
  // The first blade points along +y; bin its vertices by span and take the leading (max x) and trailing edges.
  const bins = new Map();
  for (let i = 0; i < position.count; i++) {
    if (blade.getW(i) < 0.5 || Math.abs(blade.getX(i)) > 3 || blade.getY(i) < 5) continue;
    const key = Math.round(blade.getY(i));
    const bin = bins.get(key) || {lead: -Infinity, trail: Infinity};
    bin.lead = Math.max(bin.lead, position.getX(i));
    bin.trail = Math.min(bin.trail, position.getX(i));
    bins.set(key, bin);
  }
  const radius = type.rotor / 2;
  const at = (fraction) => {
    const keys = [...bins.keys()].sort((a, b) => Math.abs(a - fraction * radius) - Math.abs(b - fraction * radius));
    return bins.get(keys[0]);
  };
  const root = at(0.22);
  const mid = at(0.6);
  const tip = at(0.97);
  const chordRoot = root.lead - root.trail;
  assert.ok(chordRoot > 3.5 && chordRoot < 6.5, `maximum chord ${chordRoot.toFixed(2)} m`);
  assert.ok(tip.lead - tip.trail < 0.25 * chordRoot, 'thin tip');
  assert.ok(Math.abs(root.lead - mid.lead) < 0.5 * Math.abs(root.trail - mid.trail),
    'the trailing edge carries the taper; the leading edge stays nearly straight');
});

// Scenario-shaped worlds: the jacket of scenarios.jacket() and the monopile of site_dressing.dress_monopile().
function jacketWorld() {
  const obstacles = [];
  for (const [sx, sy] of [[1, 1], [1, -1], [-1, -1], [-1, 1]]) {
    obstacles.push({type: 'cylinder', kind: 'jacket_leg', radius: 0.6,
      p0: [20 + sx * 4.8, sy * 4.8, -3], p1: [20 + sx * 6, sy * 6, 33]});
  }
  return {scenario: {key: 'jacket_inspection', biome: 'temperate', water_type: 'shelf'}, obstacles};
}

function monopileWorld() {
  const obstacles = [
    {type: 'cylinder', kind: 'monopile', radius: 3, p0: [15, 0, -3], p1: [15, 0, 29]},
    {type: 'cylinder', kind: 'transition_piece', radius: 3.3, p0: [15, 0, -3], p1: [15, 0, 4]},
    {type: 'cylinder', kind: 'boat_landing', radius: 0.2, p0: [15, 4.3, -2.5], p1: [15, 4.3, 3]}
  ];
  return {scenario: {key: 'monopile_current', biome: 'temperate', water_type: 'shelf'}, obstacles};
}

test('the inspected foundation gets its above-water part and turbine above the collision floor', async function () {
  const {SKIN_FLOOR, SKIN_PROUD, jacketLegs} = await import('../viewer/site_topside.js');
  assert.ok(SKIN_PROUD <= 0.03 && SKIN_FLOOR > -1, 'below +0.5 m only a thin skin on the existing collision');
  for (const [world, name] of [[jacketWorld(), 'site-jacket-topside'], [monopileWorld(), 'site-monopile-topside']]) {
    const set = buildSurfaceSet(world, new THREE.Vector3(), seeded(4), {detail: 'medium'});
    const topside = set.group.getObjectByName(name);
    assert.ok(topside, name);
    assert.ok(set.group.getObjectByName('site-turbine'), 'a turbine stands on the site');
    topside.geometry.computeBoundingBox();
    const floor = topside.geometry.boundingBox.min.y;
    assert.ok(floor >= SKIN_FLOOR - 0.05, `${name} reaches down to ${floor} m`);
  }
  // The jacket legs carry on along the scenario's batter: the sleeve passes through each leg top.
  const legs = jacketLegs(jacketWorld());
  assert.equal(legs.length, 4);
  for (const leg of legs) {
    assert.ok(Math.abs(leg.top.y - 3) < 1e-9);
    assert.ok(leg.up.y > 0.99 && leg.up.y < 1, 'battered legs lean inwards going up');
  }
});
