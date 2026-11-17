// Quality mode scales authored LOD distances. auto / high / ultra stay put.
import assert from 'node:assert/strict';
import test from 'node:test';
import { configureRenderQuality, onQualityMode } from '../viewer/render_quality.js';
import { lodDistanceScale, releaseLodQuality, scaledLodDistance, watchLodQuality } from '../viewer/model_lod.js';

test('performance and medium pull LOD distances in', () => {
  assert.equal(lodDistanceScale('auto'), 1);
  assert.equal(lodDistanceScale('high'), 1);
  assert.equal(lodDistanceScale('ultra'), 1);
  assert.ok(lodDistanceScale('medium') < 1);
  assert.ok(lodDistanceScale('performance') < lodDistanceScale('medium'));
  assert.ok(scaledLodDistance(40, 'performance') < 40);
  assert.equal(scaledLodDistance(40, 'high'), 40);
});

function renderer() {
  return {
    domElement: { clientWidth: 1280, clientHeight: 720 },
    shadowMap: {},
    info: { render: { calls: 1, triangles: 1 } },
    setPixelRatio() {},
    getContext() {
      return {
        RENDERER: 1,
        VENDOR: 2,
        getExtension() {
          return { UNMASKED_RENDERER_WEBGL: 3, UNMASKED_VENDOR_WEBGL: 4 };
        },
        getParameter(key) {
          return key === 3 ? 'SwiftShader' : 'vendor';
        },
      };
    },
  };
}

function lodWith(distance) {
  const lod = {
    userData: {},
    children: [],
    levels: [
      { object: { userData: {} }, distance: 0 },
      { object: { userData: {} }, distance },
    ],
    traverse(visit) {
      visit(this);
    },
  };
  return lod;
}

test('releasing a LOD drops its quality listener', () => {
  const lod = lodWith(40);
  const unsubscribe = watchLodQuality(lod);
  assert.equal(typeof unsubscribe, 'function');
  configureRenderQuality(renderer(), 'performance');
  assert.ok(lod.levels[1].distance < 40);
  const held = lod.levels[1].distance;
  releaseLodQuality(lod);
  configureRenderQuality(renderer(), 'high');
  assert.equal(lod.levels[1].distance, held);
  let calls = 0;
  const stop = onQualityMode(() => {
    calls += 1;
  });
  configureRenderQuality(renderer(), 'medium');
  assert.equal(calls, 1);
  stop();
  configureRenderQuality(renderer(), 'high');
  assert.equal(calls, 1);
});
