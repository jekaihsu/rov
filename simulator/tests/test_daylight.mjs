// Shared daylight above the water (viewer/fx/daylight.js): preset choice, light ratios, sea colour by water
// type, and that the camera below the surface keeps exactly the light rig the underwater optics use.
import {register} from 'node:module';
import assert from 'node:assert/strict';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const daylight = await import('../viewer/fx/daylight.js');
const {
  DAYLIGHT_PRESETS, UNDERWATER_DAYLIGHT, createDaylight, daylightMetering, daylightPresetFor, downwelling, seaBody,
  sunDirection
} = daylight;

function world(waterType, biome = 'temperate') {
  return {scenario: {water_type: waterType, biome}};
}

function luminance(rgb) {
  return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
}

test('open-sea sites get a clear day, harbours and fresh water an overcast one, ?sky= overrides', function () {
  assert.equal(daylightPresetFor(world('shelf'), ''), 'clear');
  assert.equal(daylightPresetFor(world('oceanic', 'reef'), ''), 'clear');
  assert.equal(daylightPresetFor(world('harbour', 'harbor'), ''), 'overcast');
  assert.equal(daylightPresetFor(world('fresh_clear', 'pool'), ''), 'overcast');
  assert.equal(daylightPresetFor(null, ''), 'clear');
  assert.equal(daylightPresetFor(world('shelf'), '?sky=overcast'), 'overcast');
  assert.equal(daylightPresetFor(world('harbour'), '?sky=clear'), 'clear');
  assert.equal(daylightPresetFor(world('shelf'), '?sky=storm'), 'clear');
});

test('a clear day is sun-dominated like a real one; overcast has almost no direct sun', function () {
  const clear = DAYLIGHT_PRESETS.clear;
  const sunOnGround = clear.sun * Math.sin(THREE.MathUtils.degToRad(clear.sunElevationDeg));
  const diffuseShare = luminance(clear.skyLight) / (sunOnGround + luminance(clear.skyLight));
  assert.ok(diffuseShare > 0.1 && diffuseShare < 0.25, `diffuse share ${diffuseShare.toFixed(3)}`);
  assert.ok(clear.sunColour[0] > clear.sunColour[2], 'the sun is warmer than white');
  assert.ok(clear.skyLight[2] > clear.skyLight[0], 'the sky light is bluer than the sun');
  const overcast = DAYLIGHT_PRESETS.overcast;
  assert.ok(overcast.sun < 0.25 * luminance(overcast.skyLight));
  assert.ok(overcast.exposure > clear.exposure, 'the camera opens up under cloud');
  assert.ok(downwelling(overcast) < downwelling(clear));
});

test('the sun direction has the preset elevation and is a unit vector', function () {
  for (const preset of Object.values(DAYLIGHT_PRESETS)) {
    const direction = sunDirection(preset);
    assert.ok(Math.abs(direction.length() - 1) < 1e-9);
    const elevation = THREE.MathUtils.radToDeg(Math.asin(direction.y));
    assert.ok(Math.abs(elevation - preset.sunElevationDeg) < 1e-6);
  }
});

test('open water is deep blue from above, harbour and reservoir water olive green', function () {
  const clear = DAYLIGHT_PRESETS.clear;
  for (const type of ['oceanic', 'coastal', 'shelf']) {
    const [r, g, b] = seaBody(clear, type);
    assert.ok(b > g && g > r, `${type} is blue`);
  }
  for (const type of ['harbour', 'fresh_clear']) {
    const [r, g, b] = seaBody(DAYLIGHT_PRESETS.overcast, type);
    assert.ok(g > r && g > b, `${type} is green`);
  }
  assert.deepEqual(seaBody(clear, 'unknown'), seaBody(clear, 'shelf'));
});

test('the daylight camera keeps a fixed exposure and no grey-world white balance', function () {
  assert.deepEqual(daylightMetering(DAYLIGHT_PRESETS.clear), {compensation: 0, reference: 1, balance: 0});
  assert.equal(daylightMetering(DAYLIGHT_PRESETS.overcast).reference, DAYLIGHT_PRESETS.overcast.exposure);
});

function rig(scene) {
  let hemi = null;
  let sun = null;
  scene.traverse(function find(object) {
    if (object.isHemisphereLight) hemi = object;
    if (object.isDirectionalLight) sun = object;
  });
  return {hemi, sun};
}

test('under water (and in the top-down map view) the light rig is the one the underwater optics use', function () {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#0a2a38');
  scene.fog = new THREE.Fog(0x0a2a38, 0.3, 12);
  const surface = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial());
  const sky = createDaylight(scene, {base: null});
  const camera = new THREE.PerspectiveCamera();
  const expected = {hemi: UNDERWATER_DAYLIGHT.hemisphere, sun: UNDERWATER_DAYLIGHT.sunIntensity};
  function check(label) {
    const {hemi, sun} = rig(scene);
    assert.equal(hemi.intensity, expected.hemi, label);
    assert.equal(hemi.color.getHex(), UNDERWATER_DAYLIGHT.sky, label);
    assert.equal(hemi.groundColor.getHex(), UNDERWATER_DAYLIGHT.ground, label);
    assert.equal(sun.intensity, expected.sun, label);
    assert.equal(sun.color.getHex(), UNDERWATER_DAYLIGHT.sun, label);
    assert.deepEqual(sun.position.toArray(), [...UNDERWATER_DAYLIGHT.sunPosition], label);
    assert.equal(sky.sky.visible, false, label);
    assert.equal(sky.sea.visible, false, label);
    assert.equal(scene.userData.daylightMetering, null, label);
  }
  camera.position.set(0, -5, 0);
  sky.update({camera, world: world('shelf'), dt: 0.016, view: 'chase', surface});
  check('below');
  assert.equal(surface.visible, true);
  camera.position.set(0, 4, 0);
  sky.update({camera, world: world('shelf'), dt: 0.016, view: 'chase', surface});
  assert.equal(sky.sea.visible, true);
  assert.equal(surface.visible, false, 'the sea replaces the flat surface above water');
  assert.ok(scene.userData.daylightMetering);
  assert.equal(rig(scene).sun.intensity, DAYLIGHT_PRESETS.clear.sun);
  camera.position.set(0, -2, 0);
  sky.update({camera, world: world('shelf'), dt: 0.016, view: 'chase', surface});
  check('back below');
  camera.position.set(0, 20, 0);
  sky.update({camera, world: world('shelf'), dt: 0.016, view: 'top', surface});
  check('top view');
  assert.equal(surface.visible, false, 'top view above water keeps the surface hidden as before');
  sky.dispose();
});

test('above water the sun stands in the preset direction and the background is the sea colour', function () {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color();
  scene.fog = new THREE.Fog(0, 1, 2);
  const sky = createDaylight(scene, {base: null});
  const camera = new THREE.PerspectiveCamera();
  camera.position.set(3, 2, -4);
  camera.lookAt(10, 0, 10);
  camera.updateMatrixWorld();
  sky.update({camera, world: world('harbour', 'harbor'), dt: 0.016});
  assert.equal(sky.preset, 'overcast');
  const {sun} = rig(scene);
  const direction = sun.position.clone().sub(sun.target.position).normalize();
  assert.ok(direction.distanceTo(sunDirection(DAYLIGHT_PRESETS.overcast)) < 1e-6);
  const body = seaBody(DAYLIGHT_PRESETS.overcast, 'harbour');
  const background = scene.background;
  assert.ok(Math.abs(background.r - body[0]) < 1e-6 && Math.abs(background.g - body[1]) < 1e-6);
  assert.ok(scene.fog.far > 1000, 'air haze, not underwater visibility');
  sky.dispose();
});
