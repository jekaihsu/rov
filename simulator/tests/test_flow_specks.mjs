// Verify the single-pass optical cues using the same draw range and material the viewer submits.
import assert from 'node:assert/strict';
import {register} from 'node:module';
import test from 'node:test';
register('../tools/three_resolve_hooks.mjs', import.meta.url);
const THREE = await import('three');
const {configureRenderQuality} = await import('../viewer/render_quality.js');
const {updateFlowSpecks} = await import('../viewer/fx/suspension.js');

test('existing flow specks vary with actual visibility, daylight and powered lamps on single-pass tiers', () => {
  const renderer = {shadowMap: {}, setPixelRatio() {}};
  configureRenderQuality(renderer, 'performance');
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(900 * 3), 3));
  const points = new THREE.Points(geometry, new THREE.PointsMaterial());
  const camera = new THREE.PerspectiveCamera();
  function sample(depth, visibility, lamp) {
    camera.position.y = -depth;
    updateFlowSpecks(points, renderer, camera, camera.position, {visibility}, lamp);
    return [geometry.drawRange.count, points.material.opacity];
  }
  const [clear, shallow] = sample(2, 22, 0);
  const [cloudy, deep] = sample(32, 2, 0);
  const [, lit] = sample(32, 2, 1);
  assert.ok(clear > 0 && clear < cloudy && cloudy <= 900);
  assert.ok(deep < shallow && lit > deep && lit < 1);
  configureRenderQuality(renderer, 'medium');
  assert.deepEqual(sample(32, 2, 0), [900, 0.8]);
});
