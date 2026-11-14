/* Onboard-only optical presentation. Coefficients and lens/exposure settings are
 * provisional artistic approximations, not measured vehicle parameters.
 * OSD layout is 暂定: research report's older-generation description pending real screenshots.
 * Geometry, camera transforms and observation evidence are never modified here. */
import * as THREE from 'three';
import {applyUnderwaterLighting} from '../underwater_lighting.js';

const STRINGS = {
  title: '機載影像（叠字配置暫定）', real: '真實影像', strength: '效果強度',
  osd: '顯示叠字', burn: '拍照／錄影燒入叠字', delay: '影像延遲',
  mode: '模式', locked: '鎖定', unlocked: '解鎖', recording: '錄影',
  connected: '連線', offline: '離線', depth: '深度', heading: '航向', light: '燈光',
};

export function installOnboard({renderer, scene, camera, getState, getMode, isRecording}) {
  const settings = {real: false, strength: 0.6, osd: true, burn: false, delay: 0};
  const panel = document.createElement('details');
  panel.style.cssText = 'position:fixed;bottom:100px;right:4%;z-index:15;color:white;background:#08121acc;padding:8px';
  const summary = document.createElement('summary');
  summary.textContent = STRINGS.title;
  panel.append(summary);
  for (const key of ['real', 'strength', 'osd', 'burn', 'delay']) {
    const label = document.createElement('label');
    label.style.display = 'block';
    label.append(STRINGS[key] + ' ');
    const input = document.createElement(key === 'delay' ? 'select' : 'input');
    if (key === 'delay') {
      for (const value of [0, 80, 150]) input.add(new Option(`${value} ms`, value));
    } else if (key === 'strength') {
      input.type = 'range';
      input.min = 0;
      input.max = 1;
      input.step = 0.05;
      input.value = settings[key];
    } else {
      input.type = 'checkbox';
      input.checked = settings[key];
    }
    input.onchange = function updateSetting() {
      settings[key] = input.type === 'checkbox' ? input.checked : Number(input.value);
    };
    label.append(input);
    panel.append(label);
  }
  document.body.append(panel);
  const overlay = document.createElement('canvas');
  overlay.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9';
  overlay.width = 1600;
  overlay.height = 900;
  document.body.append(overlay);
  const ctx = overlay.getContext('2d');
  const osdTexture = new THREE.CanvasTexture(overlay);
  const optical = {value: 0};
  const strength = {value: 0};
  const patched = new WeakSet();
  function patchMaterials() {
    scene.traverse(function patchObject(object) {
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        if (!material?.isMeshStandardMaterial || patched.has(material)) continue;
        patched.add(material);
        const previous = material.onBeforeCompile;
        material.onBeforeCompile = function compile(shader, webgl) {
          previous.call(this, shader, webgl);
          shader.uniforms.onboardOptical = optical;
          shader.uniforms.onboardStrength = strength;
          shader.fragmentShader = 'uniform float onboardOptical; uniform float onboardStrength;\n'
            + shader.fragmentShader;
          // Independent RGB Beer-Lambert coefficients; no single-color fog substitute.
          // Incoming sunlight travels to the surface point; point/spot lights travel from lamp to point.
          let chunk = shader.fragmentShader;
          for (const type of ['Point', 'Spot']) {
            const call = `get${type}LightInfo( ${type.toLowerCase()}Light, geometryPosition, directLight );`;
            chunk = chunk.replace(call, call + ` directLight.color *= exp(-vec3(.18,.065,.03) *
              length(${type.toLowerCase()}Light.position - geometryPosition) * onboardOptical * onboardStrength);`);
          }
          chunk = chunk.replace('getDirectionalLightInfo( directionalLight, directLight );',
            `getDirectionalLightInfo( directionalLight, directLight );
             directLight.color *= exp(-vec3(.18,.065,.03) * vWaterDepth * onboardOptical * onboardStrength);`);
          chunk = chunk.replace('getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal )',
            `getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal ) *
             exp(-vec3(.18,.065,.03) * vWaterDepth * onboardOptical * onboardStrength)`);
          // Existing depth varying is provided by underwater_lighting.js.
          shader.fragmentShader = chunk;
        };
        const oldKey = material.customProgramCacheKey.bind(material);
        material.customProgramCacheKey = function cacheKey() { return oldKey() + '|onboard-v1'; };
        material.needsUpdate = true;
      }
    });
  }
  const targets = [];
  const screen = new THREE.Scene();
  const screenCamera = new THREE.Camera();
  const uniforms = {
    image: {value: null}, depth: {value: null}, osd: {value: osdTexture}, burn: {value: 0},
    amount: strength, near: {value: camera.near}, far: {value: camera.far}, time: {value: 0},
    rayScale: {value: new THREE.Vector2()}, exposure: {value: 1}, lamp: {value: 0},
  };
  const material = new THREE.ShaderMaterial({uniforms,
    vertexShader: 'varying vec2 uv0; void main(){uv0=uv;gl_Position=vec4(position.xy,0.,1.);}',
    fragmentShader: `varying vec2 uv0;
      uniform sampler2D image, depth, osd;
      uniform vec2 rayScale;
      uniform float amount, near, far, time, exposure, burn, lamp;
      float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
      void main(){
        vec2 p=uv0-.5;
        vec2 uv=.5+p*(1.+amount*.08*dot(p,p));
        uv=clamp(uv,0.,1.);
        vec2 block=floor(uv*vec2(800.,450.))/vec2(800.,450.);
        vec3 c=mix(texture2D(image,uv).rgb,texture2D(image,block).rgb,amount*.18);
        float z=texture2D(depth,uv).x;
        float d=near*far/(far-z*(far-near))*length(vec3((uv-.5)*rayScale,1.));
        // Return path completes sunlight depth+range and lamp->object->camera paths.
        c*=exp(-vec3(.18,.065,.03)*d*amount);
        vec3 scatter=vec3(.025,.11,.13)*(1.-exp(-vec3(.1,.14,.16)*d));
        c+=scatter*amount*(.35+lamp);
        float noise=hash(gl_FragCoord.xy+floor(time*30.));
        c+=(noise-.5)*amount*.065;
        c+=step(.998,noise)*amount*.25*lamp;
        c*=exposure;
        vec4 text=texture2D(osd,uv0);
        gl_FragColor=vec4(mix(c,text.rgb,text.a*burn),1.);
      }`});
  screen.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material));
  let lastFrame = -Infinity;
  let lastTime = performance.now();
  let meteredExposure = 1;
  const pixel = new Uint8Array(4);
  let size = '';
  function drawOSD(state) {
    ctx.clearRect(0, 0, 1600, 900);
    if (!settings.osd) return;
    ctx.font = '22px monospace';
    ctx.fillStyle = 'white';
    ctx.shadowColor = 'black';
    ctx.shadowBlur = 4;
    const euler = state?.euler || [0, 0, 0];
    const status = state ? STRINGS.connected : STRINGS.offline;
    ctx.fillText(`${status}   ${STRINGS.light} ${state?.rc?.right_switch ?? '—'}`, 64, 65);
    ctx.fillText(`${STRINGS.mode} ${state?.operation_mode || '—'}`, 600, 65);
    ctx.fillText(new Date().toISOString(), 1000, 65);
    const lock = state?.rc?.rc_lock ? STRINGS.locked : STRINGS.unlocked;
    ctx.fillText(`${lock}  ${state?.recording ? STRINGS.recording : ''}`, 1250, 120);
    ctx.fillText(`${STRINGS.depth} ${(state?.pos?.[2] ?? 0).toFixed(1)} m`, 64, 400);
    ctx.fillText(`${STRINGS.heading} ${euler[2].toFixed(0)}°`, 1250, 760);
    ctx.fillText(`R ${euler[0].toFixed(1)}°  P ${euler[1].toFixed(1)}°`, 64, 800);
  }
  function render({capture = false} = {}) {
    const active = getMode() === 'onboard';
    panel.hidden = !active;
    overlay.hidden = !active;
    if (!active) {
      optical.value = 0;
      renderer.render(scene, camera);
      return;
    }
    applyUnderwaterLighting(scene);
    patchMaterials();
    optical.value = settings.real ? 1 : 0;
    strength.value = settings.real ? settings.strength : 0;
    const now = performance.now();
    const dimensions = renderer.getDrawingBufferSize(new THREE.Vector2());
    const nextSize = `${dimensions.x},${dimensions.y}`;
    if (nextSize !== size) {
      targets.splice(0).forEach(function disposeFrame(frame) { frame.target.dispose(); });
      size = nextSize;
      lastFrame = -Infinity;
    }
    drawOSD(getState());
    osdTexture.needsUpdate = true;
    const burn = settings.osd && settings.burn && (capture || isRecording());
    overlay.style.visibility = burn ? 'hidden' : 'visible';
    if (!settings.real && settings.delay === 0 && !burn) {
      renderer.render(scene, camera);
      return;
    }
    if (capture || now - lastFrame >= 30 || !targets.length) {
      const frame = targets.length >= 8 ? targets.shift() : {target: new THREE.WebGLRenderTarget(
        dimensions.x, dimensions.y, {depthTexture: new THREE.DepthTexture(dimensions.x, dimensions.y)})};
      const fog = scene.fog;
      if (settings.real) scene.fog = null;
      renderer.setRenderTarget(frame.target);
      renderer.render(scene, camera);
      renderer.setRenderTarget(null);
      scene.fog = fog;
      renderer.readRenderTargetPixels(frame.target, Math.floor(dimensions.x / 2),
        Math.floor(dimensions.y / 2), 1, 1, pixel);
      const luminance = (pixel[0] * .2126 + pixel[1] * .7152 + pixel[2] * .0722) / 255;
      meteredExposure = THREE.MathUtils.clamp(.3 / Math.max(.05, luminance), .7, 1.8);
      frame.time = now;
      targets.push(frame);
      lastFrame = now;
    }
    // Evidence photos use the current frame so displayed geometry agrees with authoritative inspection.
    const frame = capture ? targets[targets.length - 1]
      : [...targets].reverse().find(item => item.time <= now - settings.delay) || targets[0];
    uniforms.image.value = frame.target.texture;
    uniforms.depth.value = frame.target.depthTexture;
    uniforms.burn.value = burn ? 1 : 0;
    const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    uniforms.rayScale.value.set(2 * tangent * camera.aspect, 2 * tangent);
    uniforms.near.value = camera.near;
    uniforms.far.value = camera.far;
    uniforms.time.value = now / 1000;
    uniforms.lamp.value = [0, .55, 1][getState()?.rc?.right_switch || 0] || 0;
    // Provisional slow adaptation to lamp setting and depth; no calibrated sensor response claimed.
    const targetExposure = settings.real ? meteredExposure : 1;
    uniforms.exposure.value += (targetExposure - uniforms.exposure.value) * (1 - Math.exp(-(now-lastTime)/900));
    lastTime = now;
    renderer.render(screen, screenCamera);
  }
  return {render, settings};
}
