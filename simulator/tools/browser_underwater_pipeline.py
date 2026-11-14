"""Underwater optics pipeline lifecycle on real WebGL: low bypass, composer, exposure, camera pass, offscreen, resize.

Run through the runner: python tools/run_browser_checks.py browser_underwater_pipeline
"""
import json
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, timeout

FIXTURE = ('<script type="importmap">{"imports":{"three":"/vendor/three/build/three.module.js",'
           '"three/addons/":"/vendor/three/examples/jsm/"}}</script>')

CHECK = '''async () => {
  const T = await import('three');
  const {installUnderwaterPipeline} = await import('./fx/pipeline.js');
  const {applyUnderwaterLighting} = await import('./underwater_lighting.js');
  const {configureRenderQuality} = await import('./render_quality.js');
  const {getFidelity} = await import('./fidelity.js');
  const lowRenderer = new T.WebGLRenderer();
  configureRenderQuality(lowRenderer, 'performance');
  const lowOriginal = lowRenderer.render;
  const lowStartup = installUnderwaterPipeline(lowRenderer) === null && lowRenderer.render === lowOriginal;
  lowRenderer.dispose();
  const r = new T.WebGLRenderer({preserveDrawingBuffer: true});
  r.toneMapping = T.ACESFilmicToneMapping;
  const scene = new T.Scene();
  const camera = new T.PerspectiveCamera(60, 1, .01, 100);
  camera.position.set(0, -20, 3);
  camera.lookAt(0, -20, 0);
  scene.background = new T.Color(0x102a30);
  scene.fog = new T.Fog(0x102a30, .3, 10 * 1.35);
  const mesh = new T.Mesh(new T.BoxGeometry(), new T.MeshStandardMaterial({color: 0xff4020}));
  mesh.position.y = -20;
  const marker = new T.Mesh(new T.SphereGeometry(.2), new T.MeshBasicMaterial({color: 0xffff00}));
  marker.position.set(1, -20, 0);
  scene.add(mesh, marker, new T.HemisphereLight(0xffffff, 0x112233, 1.5));
  const lamp = new T.SpotLight(0xffffff, 260, 22, .5, .5, 1.3);
  lamp.position.set(0, -20, 2.5);
  lamp.target.position.set(0, -20, 0);
  scene.add(lamp, lamp.target);
  const surface = new T.Mesh(new T.PlaneGeometry(50, 50), new T.MeshBasicMaterial());
  surface.rotation.x = -Math.PI / 2;
  scene.add(surface);
  const fx = installUnderwaterPipeline(r, {surface});
  configureRenderQuality(r, 'performance');
  applyUnderwaterLighting(scene, null, r);
  r.render(scene, camera);
  const lowBypass = fx.composer === null && lamp.decay === 1.3;
  configureRenderQuality(r, 'medium');
  applyUnderwaterLighting(scene, null, r);
  for (let i = 0; i < 4; i++) r.render(scene, camera);
  const composed = !!fx.composer && lamp.decay === 2;
  const exposure = fx.exposure();
  const exposureSane = exposure.exposure > 0 && Number.isFinite(exposure.exposure);
  const geometryIgnored = surface.userData.observationIgnore === true &&
    scene.getObjectByName('water-suspension').userData.observationIgnore === true &&
    scene.getObjectByName('water-background').userData.observationIgnore === true;
  const beautyDefaultOff = fx.enhancements === false && getFidelity().get('waterBeautify') === false;
  let calls = 0;
  const {ShaderPass} = await import('three/addons/postprocessing/ShaderPass.js');
  const pass = new ShaderPass({uniforms: {tDiffuse: {value: null}},
    vertexShader: 'varying vec2 vUv; void main(){vUv=uv;' +
      'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: 'uniform sampler2D tDiffuse;varying vec2 vUv;void main(){gl_FragColor=texture2D(tDiffuse,vUv);}'});
  const render = pass.render.bind(pass);
  pass.render = function countedRender(...args) {
    calls++;
    render(...args);
  };
  fx.setCameraPass(pass);
  r.render(scene, camera);
  const cameraPassAfterExposure = fx.composer.passes.indexOf(pass) === 2;
  r.setPixelRatio(.7);
  r.setSize(640, 360);
  r.render(scene, camera);
  const size = r.getDrawingBufferSize(new T.Vector2());
  const resized = fx.width === size.x && fx.height === size.y;
  const target = new T.WebGLRenderTarget(64, 64);
  r.setRenderTarget(target);
  r.render(scene, camera);
  const offscreenPreserved = r.getRenderTarget() === target && calls === 2;
  r.setRenderTarget(null);
  const blob = await new Promise(resolve => r.domElement.toBlob(resolve));
  fx.setCameraPass(null);
  pass.dispose();
  configureRenderQuality(r, 'performance');
  applyUnderwaterLighting(scene, null, r);
  r.render(scene, camera);
  const legacyAgain = lamp.decay === 1.3 && !scene.getObjectByName('water-background').visible;
  fx.dispose();
  target.dispose();
  return {lowStartup, lowBypass, composed, exposureSane, geometryIgnored, beautyDefaultOff,
    cameraPassAfterExposure, resized, offscreenPreserved, legacyAgain, png: blob.type === 'image/png', exposure};
}'''

with sync_playwright() as p:
    browser = launch(p, headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda m: errors.append(m.text) if 'Shader Error' in m.text else None)
    page.route('**/fixture.html', lambda route: route.fulfill(body=FIXTURE, content_type='text/html'))
    page.goto(f'{http_base(8093)}/fixture.html')
    page.set_default_timeout(timeout(60000))
    result = page.evaluate(CHECK)
    exposure = result.pop('exposure')
    assert all(result.values()), result
    assert not errors, errors
    print(json.dumps({**result, 'exposure': exposure}))
    browser.close()
