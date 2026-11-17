// Daylight above the water: one shared sun, sky light, sky dome (gradient, sun aureole, clouds) and open-sea
// surface for every view whose camera is above the water (deployment intro, surface segments, the chase camera
// on a surfaced vehicle). Under water the lights keep exactly the values the underwater optics were calibrated
// with (UNDERWATER_DAYLIGHT), so nothing below the surface changes.
//
// Units: three.js physical light units relative to the rest of the scene. A clear day has a direct sun of about
// four to five times the sky's irradiance on a horizontal surface (diffuse fraction about 15-20 %), and the
// camera exposure for daylight is fixed (a sunny day meters to the same exposure; "sunny 16"), so sunlit white
// paint lands near the top of the tone curve while shade and sky stay well below it. The target values come
// from field photographs measured for docs/design/daylight/README.md; every number here is a presentation
// assumption, not X1 data. The wave-normal sampling (four scrolled taps of waternormals.webp) follows three.js's
// Water.js (MIT); the sea has no planar mirror pass, it reflects the analytic sky.
//
//   const daylight = createDaylight(scene, {base: 'models/'});
//   each frame: daylight.update({camera, world, dt, view: camMode, surface, renderer});
import * as THREE from 'three';
import { renderQualityState } from '../render_quality.js';

// Light rig the underwater optics were calibrated against (fx/water_optics.js LAMP_SCALE, SURFACE_DAYLIGHT).
export const UNDERWATER_DAYLIGHT = Object.freeze({
  sky: 0xa8dcf0,
  ground: 0x1a2a22,
  hemisphere: 1.5,
  sun: 0xdff4ff,
  sunIntensity: 1.6,
  sunPosition: Object.freeze([20, 60, 10])
});

// Linear RGB. `sun` is the direct irradiance on a surface facing the sun; `skyLight` and `groundLight` are the
// hemisphere light's sky and ground irradiance; the sky dome values are radiances. `exposure` is the camera's
// fixed daylight gain (overcast: the camera opens up about one and a half stops).
export const DAYLIGHT_PRESETS = Object.freeze({
  clear: Object.freeze({
    sunElevationDeg: 52,
    sunColour: Object.freeze([1.0, 0.9, 0.76]),
    sun: 5.6,
    skyLight: Object.freeze([0.56, 0.73, 0.98]),
    // Light from below: sun glitter off the sea and bounce from the structure itself (warm on yellow paint).
    groundLight: Object.freeze([0.1, 0.094, 0.08]),
    zenith: Object.freeze([0.07, 0.22, 0.84]),
    horizon: Object.freeze([0.3, 0.52, 1.02]),
    overcast: 0,
    cloudCover: 0.42,
    cloudLit: Object.freeze([1.1, 1.14, 1.22]),
    cloudShade: Object.freeze([0.52, 0.6, 0.74]),
    hazeDistance: 3600,
    glint: 1,
    exposure: 1
  }),
  overcast: Object.freeze({
    sunElevationDeg: 60,
    sunColour: Object.freeze([1.0, 0.97, 0.93]),
    sun: 0.22,
    skyLight: Object.freeze([1.0, 1.0, 0.98]),
    groundLight: Object.freeze([0.17, 0.18, 0.16]),
    zenith: Object.freeze([0.5, 0.51, 0.53]),
    horizon: Object.freeze([0.17, 0.172, 0.176]),
    overcast: 1,
    cloudCover: 1,
    cloudLit: Object.freeze([0.56, 0.57, 0.6]),
    cloudShade: Object.freeze([0.38, 0.39, 0.42]),
    hazeDistance: 1300,
    glint: 0,
    exposure: 2.1
  })
});

// Water-leaving radiance per unit downwelling irradiance (linear RGB), by the scenario's water type. Deep blue
// for open and shelf seas as seen from a boat; olive green for harbour and reservoir water (turbid, much more
// scattering). Assumptions tuned against the measured photo values, not ocean-colour data.
export const SEA_BODY = Object.freeze({
  oceanic: Object.freeze([0.0005, 0.0046, 0.0132]),
  coastal: Object.freeze([0.0009, 0.0058, 0.0118]),
  shelf: Object.freeze([0.0008, 0.0062, 0.0118]),
  harbour: Object.freeze([0.031, 0.049, 0.032]),
  fresh_clear: Object.freeze([0.028, 0.047, 0.033])
});
const DEFAULT_BODY = SEA_BODY.shelf;
// Horizontal direction the sun stands in (three.js axes), shared with the deployment intro's framing.
const SUN_AZIMUTH = new THREE.Vector3(0.45, 0, -0.8).normalize();
const SKY_RADIUS = 2000;
const SEA_SIZE = 5200;
const SHADOW_HALF = 26;
const SHADOW_SCAN_FRAMES = 60;
const OVERCAST_BIOMES = new Set(['harbor', 'harbour']);
const OVERCAST_WATER = new Set(['harbour', 'fresh_clear']);

// Which sky a site gets: `?sky=clear|overcast` for reviews, else harbours and fresh water get an overcast day.
export function daylightPresetFor(world, search = globalThis.location?.search || '') {
  const asked = new URLSearchParams(search).get('sky');
  if (asked && Object.hasOwn(DAYLIGHT_PRESETS, asked)) return asked;
  const scenario = world?.scenario || {};
  if (OVERCAST_WATER.has(scenario.water_type) || OVERCAST_BIOMES.has(scenario.biome)) return 'overcast';
  return 'clear';
}

export function sunDirection(preset, out = new THREE.Vector3()) {
  const elevation = THREE.MathUtils.degToRad(preset.sunElevationDeg);
  return out.copy(SUN_AZIMUTH).multiplyScalar(Math.cos(elevation)).setY(Math.sin(elevation)).normalize();
}

// Irradiance on a horizontal surface (luminance-weighted), used to scale the water-leaving radiance.
export function downwelling(preset) {
  const sun = preset.sun * Math.sin(THREE.MathUtils.degToRad(preset.sunElevationDeg));
  const sky = 0.2126 * preset.skyLight[0] + 0.7152 * preset.skyLight[1] + 0.0722 * preset.skyLight[2];
  return sun + sky;
}

export function seaBody(preset, waterType) {
  const reflectance = SEA_BODY[waterType] || DEFAULT_BODY;
  const light = downwelling(preset);
  return reflectance.map(function scale(value) {
    return value * light;
  });
}

// Camera metering above water: a fixed daylight gain and no grey-world white balance (daylight white balance
// keeps a blue sky blue). fx/pipeline.js hands it to the auto-exposure pass while the camera is above water.
export function daylightMetering(preset) {
  return {compensation: 0, reference: preset.exposure, balance: 0};
}

// Colour rendering of a daylight camera, after tone mapping (display-referred sRGB values), above water only.
// ACES pushes saturated yellows towards lemon and, under blue skylight, shaded yellow paint towards olive green;
// field photos keep sunlit yellow golden and shaded yellow ochre. The grade turns hues between about 45 and 80
// degrees back by up to 14 degrees and lifts their saturation slightly; sky, sea, greens, oranges and greys are
// left alone. Applied by fx/pipeline.js; the low tier has no screen passes and keeps the plain ACES look.
export const DAYLIGHT_GRADE = Object.freeze({
  uniforms: {tDiffuse: {value: null}, uStrength: {value: 1}},
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uStrength;
    varying vec2 vUv;
    vec3 toHsv(vec3 c) {
      vec4 k = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
      vec4 p = mix(vec4(c.bg, k.wz), vec4(c.gb, k.xy), step(c.b, c.g));
      vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
      float d = q.x - min(q.w, q.y);
      return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-6)), d / (q.x + 1e-6), q.x);
    }
    vec3 toRgb(vec3 c) {
      vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
      return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
    }
    void main() {
      vec4 colour = texture2D(tDiffuse, vUv);
      vec3 hsv = toHsv(clamp(colour.rgb, 0.0, 1.0));
      float degrees = hsv.x * 360.0;
      float band = smoothstep(42.0, 54.0, degrees) * (1.0 - smoothstep(74.0, 88.0, degrees));
      float weight = band * clamp(hsv.y * 1.6, 0.0, 1.0) * uStrength;
      hsv.x -= weight * 14.0 / 360.0;
      hsv.y = clamp(hsv.y * (1.0 + 0.14 * weight), 0.0, 1.0);
      gl_FragColor = vec4(toRgb(hsv), colour.a);
    }`
});

const SKY_GLSL = /* glsl */ `
  uniform vec3 uSunDir;
  uniform vec3 uSunRadiance;
  uniform vec3 uZenith;
  uniform vec3 uHorizon;
  uniform float uOvercast;
  float daylightHash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }
  float daylightNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = daylightHash(i);
    float b = daylightHash(i + vec2(1.0, 0.0));
    float c = daylightHash(i + vec2(0.0, 1.0));
    float d = daylightHash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
  }
  float daylightFbm(vec2 p) {
    float sum = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
      sum += amplitude * daylightNoise(p);
      p = p * 2.03 + vec2(17.1, 9.2);
      amplitude *= 0.5;
    }
    return sum;
  }
  // Clear: deep zenith over a paler, hazier horizon band plus forward scattering around the sun.
  // Overcast: the CIE overcast law, the zenith three times as bright as the horizon.
  vec3 daylightSky(vec3 dir) {
    float h = clamp(dir.y, 0.0, 1.0);
    vec3 clear = mix(uHorizon, uZenith, pow(h, 0.55));
    vec3 grey = uZenith * (1.0 + 2.0 * h) / 3.0;
    vec3 sky = mix(clear, grey, uOvercast);
    float mu = max(dot(dir, uSunDir), 0.0);
    sky += uSunRadiance * (0.006 * pow(mu, 5.0) + 0.03 * pow(mu, 48.0)) * (1.0 - uOvercast);
    return sky;
  }
`;

const SKY_VERTEX = /* glsl */ `
  varying vec3 vDirection;
  void main() {
    vDirection = normalize((modelMatrix * vec4(position, 0.0)).xyz);
    vec4 clip = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_Position = clip.xyww;
  }
`;

const SKY_FRAGMENT = /* glsl */ `
  ${SKY_GLSL}
  uniform float uCloudCover;
  uniform vec3 uCloudLit;
  uniform vec3 uCloudShade;
  uniform float uCloudTime;
  uniform vec3 uBelow;
  varying vec3 vDirection;
  void main() {
    vec3 dir = normalize(vDirection);
    vec3 colour = daylightSky(dir);
    float mu = dot(dir, uSunDir);
    colour += uSunRadiance * 60.0 * smoothstep(0.99995, 0.99998, mu) * (1.0 - uOvercast);
    if (dir.y > 0.0 && uCloudCover > 0.0) {
      // Cloud layer on a plane: coordinates spread out towards the horizon, so clouds flatten and crowd there.
      vec2 p = dir.xz / (dir.y + 0.08) * 0.9 + vec2(uCloudTime, uCloudTime * 0.37);
      float n = daylightFbm(p);
      // Fair-weather cumulus: rounded tops with a fairly sharp edge, mostly in the lower sky.
      float cover = uCloudCover * mix(1.0, 0.55, smoothstep(0.08, 0.5, dir.y) * (1.0 - uOvercast));
      float density = smoothstep(1.0 - cover, 1.0 - cover + 0.12, n);
      float towardsSun = daylightFbm(p + uSunDir.xz * 0.12);
      float lit = clamp(0.62 + (n - towardsSun) * 5.0, 0.0, 1.0);
      vec3 cloud = mix(uCloudShade, uCloudLit, lit);
      float fade = smoothstep(0.0, 0.1, dir.y);
      vec3 cumulus = mix(colour, mix(uHorizon, cloud, fade * 0.85 + 0.15), density * fade);
      // Overcast: one continuous deck, only its thickness varies (darker and lighter patches).
      vec3 deck = colour * mix(1.0, 0.78 + 0.44 * n, fade);
      colour = mix(cumulus, deck, uOvercast);
    }
    if (dir.y < 0.0) colour = mix(colour, uBelow, smoothstep(0.0, 0.02, -dir.y));
    gl_FragColor = vec4(colour, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

const SEA_VERTEX = /* glsl */ `
  varying vec3 vWorld;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    vWorld = world.xyz;
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const SEA_FRAGMENT = /* glsl */ `
  ${SKY_GLSL}
  uniform sampler2D tNormals;
  uniform float uHasNormals;
  uniform float uTime;
  uniform vec3 uBody;
  uniform vec3 uBelow;
  uniform float uHazeRate;
  uniform float uGlint;
  varying vec3 vWorld;
  vec3 seaNormal(vec2 p, float distance) {
    vec3 n = vec3(0.0, 1.0, 0.0);
    if (uHasNormals > 0.5) {
      vec2 uv0 = p / 61.0 + vec2(uTime / 17.0, uTime / 29.0);
      vec2 uv1 = p / 67.0 - vec2(uTime / -19.0, uTime / 31.0);
      vec2 uv2 = p / vec2(9.1, 8.3) + vec2(uTime / 101.0, uTime / 97.0);
      vec2 uv3 = p / vec2(13.7, 12.9) - vec2(uTime / 109.0, uTime / -113.0);
      vec4 noise = texture2D(tNormals, uv0) + texture2D(tNormals, uv1) + texture2D(tNormals, uv2) +
        texture2D(tNormals, uv3);
      vec3 bump = noise.xzy * 0.5 - 1.0;
      // Far away the facets are smaller than a pixel and the texture's mipmaps average them; keep the slope
      // statistics instead of flattening the sea into a mirror.
      float strength = mix(1.4, 0.9, smoothstep(20.0, 900.0, distance));
      n = normalize(vec3(bump.x * strength, 1.0, bump.z * strength));
    }
    return n;
  }
  void main() {
    vec3 toEye = cameraPosition - vWorld;
    float distance = length(toEye);
    vec3 view = toEye / distance;
    vec3 normal = seaNormal(vWorld.xz, distance);
    float cosView = max(dot(normal, view), 0.0);
    // Wind-roughened sea: near grazing, facets facing away are hidden and the visible ones face the eye, so the
    // mean reflectance stays far below a mirror's (Cox-Munk); capped rather than integrated.
    float fresnel = min(0.02 + 0.98 * pow(1.0 - cosView, 5.0), 0.38);
    vec3 mirrored = reflect(-view, normal);
    mirrored.y = abs(mirrored.y);
    vec3 sky = daylightSky(mirrored);
    float sun = pow(max(dot(mirrored, uSunDir), 0.0), 1400.0) * 220.0;
    vec3 glint = uSunRadiance * sun * fresnel * uGlint;
    // Looking steeply down the eye sees into the first metres of water (objects there are drawn already);
    // towards the horizon the surface reflects and the water body is opaque.
    float steep = clamp(view.y, 0.0, 1.0);
    float body = mix(1.0, 0.55, smoothstep(0.35, 0.9, steep));
    float alpha = clamp(fresnel + (1.0 - fresnel) * body, 0.0, 1.0);
    vec3 colour = fresnel * sky + glint + (1.0 - fresnel) * body * uBody;
    float haze = 1.0 - exp(-distance * uHazeRate);
    colour = mix(colour, uBelow * alpha, haze);
    gl_FragColor = vec4(colour / max(alpha, 1e-3), alpha);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

function skyUniforms() {
  return {
    uSunDir: {value: new THREE.Vector3(0, 1, 0)},
    uSunRadiance: {value: new THREE.Vector3()},
    uZenith: {value: new THREE.Vector3()},
    uHorizon: {value: new THREE.Vector3()},
    uOvercast: {value: 0},
    uBelow: {value: new THREE.Vector3()}
  };
}

function createSky(uniforms) {
  const material = new THREE.ShaderMaterial({
    uniforms: Object.assign(uniforms, {
      uCloudCover: {value: 0},
      uCloudLit: {value: new THREE.Vector3()},
      uCloudShade: {value: new THREE.Vector3()},
      uCloudTime: {value: 0}
    }),
    vertexShader: SKY_VERTEX,
    fragmentShader: SKY_FRAGMENT,
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: false,
    fog: false
  });
  const sky = new THREE.Mesh(new THREE.SphereGeometry(SKY_RADIUS, 32, 16), material);
  sky.name = 'daylight-sky';
  sky.frustumCulled = false;
  sky.renderOrder = -1e9;
  sky.visible = false;
  sky.userData.observationIgnore = true;
  return sky;
}

function createSea(uniforms) {
  const material = new THREE.ShaderMaterial({
    uniforms: Object.assign({}, uniforms, {
      tNormals: {value: null},
      uHasNormals: {value: 0},
      uTime: {value: 0},
      uBody: {value: new THREE.Vector3()},
      uHazeRate: {value: 0},
      uGlint: {value: 1}
    }),
    vertexShader: SEA_VERTEX,
    fragmentShader: SEA_FRAGMENT,
    transparent: true,
    depthWrite: true,
    fog: false
  });
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(SEA_SIZE, SEA_SIZE), material);
  sea.name = 'daylight-sea';
  sea.rotation.x = -Math.PI / 2;
  sea.frustumCulled = false;
  sea.renderOrder = -1;
  sea.visible = false;
  sea.userData.observationIgnore = true;
  return sea;
}

function setVector(target, values, scale = 1) {
  target.set(values[0] * scale, values[1] * scale, values[2] * scale);
}

function luminanceOf(values) {
  return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
}

// Shadows only exist above water: under water the shadow frustum is parked outside the world (every lookup is
// "lit") and the map is not re-rendered, so the underwater look and cost stay as they were.
function parkShadow(sun) {
  const camera = sun.shadow.camera;
  camera.left = 1e6;
  camera.right = 1e6 + 1;
  camera.top = 1e6 + 1;
  camera.bottom = 1e6;
  camera.updateProjectionMatrix();
  sun.shadow.needsUpdate = true;
  sun.shadow.autoUpdate = false;
}

function aimShadow(sun, mapSize) {
  const camera = sun.shadow.camera;
  camera.left = -SHADOW_HALF;
  camera.right = SHADOW_HALF;
  camera.top = SHADOW_HALF;
  camera.bottom = -SHADOW_HALF;
  camera.near = 1;
  camera.far = 400;
  camera.updateProjectionMatrix();
  if (sun.shadow.mapSize.x !== mapSize) {
    sun.shadow.mapSize.set(mapSize, mapSize);
    sun.shadow.map?.dispose();
    sun.shadow.map = null;
  }
  sun.shadow.autoUpdate = true;
}

export function createDaylight(scene, {base = 'models/', normals = null} = {}) {
  const hemi = new THREE.HemisphereLight(UNDERWATER_DAYLIGHT.sky, UNDERWATER_DAYLIGHT.ground,
    UNDERWATER_DAYLIGHT.hemisphere);
  const sun = new THREE.DirectionalLight(UNDERWATER_DAYLIGHT.sun, UNDERWATER_DAYLIGHT.sunIntensity);
  sun.position.fromArray(UNDERWATER_DAYLIGHT.sunPosition);
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.03;
  parkShadow(sun);
  const uniforms = skyUniforms();
  const sky = createSky(uniforms);
  const sea = createSea(uniforms);
  scene.add(hemi, sun, sun.target, sky, sea);
  const direction = new THREE.Vector3();
  const focus = new THREE.Vector3();
  const forward = new THREE.Vector3();
  const body = new THREE.Color();
  let presetName = null;
  let preset = null;
  let above = null;
  let scanAge = SHADOW_SCAN_FRAMES;
  let shadowsLive = false;
  if (normals) useNormals(normals);
  else if (base) {
    new THREE.TextureLoader().loadAsync(base + 'waternormals.webp').then(useNormals).catch(function noNormals() {
      return null;
    });
  }

  function useNormals(texture) {
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    sea.material.uniforms.tNormals.value = texture;
    sea.material.uniforms.uHasNormals.value = 1;
  }

  function applyPreset(name, waterType) {
    preset = DAYLIGHT_PRESETS[name];
    sunDirection(preset, direction);
    uniforms.uSunDir.value.copy(direction);
    setVector(uniforms.uSunRadiance.value, preset.sunColour, preset.sun);
    setVector(uniforms.uZenith.value, preset.zenith);
    setVector(uniforms.uHorizon.value, preset.horizon);
    uniforms.uOvercast.value = preset.overcast;
    const below = preset.overcast ? preset.horizon.map((value) => value * 1.6) : preset.horizon;
    setVector(uniforms.uBelow.value, below, 0.82);
    sky.material.uniforms.uCloudCover.value = preset.cloudCover;
    setVector(sky.material.uniforms.uCloudLit.value, preset.cloudLit);
    setVector(sky.material.uniforms.uCloudShade.value, preset.cloudShade);
    const water = sea.material.uniforms;
    water.uBody.value.fromArray(seaBody(preset, waterType));
    water.uHazeRate.value = 1 / preset.hazeDistance;
    water.uGlint.value = preset.glint;
    body.setRGB(...seaBody(preset, waterType), THREE.LinearSRGBColorSpace);
  }

  function lightAboveWater() {
    const skyLevel = Math.max(...preset.skyLight);
    hemi.color.setRGB(...preset.skyLight.map((value) => value / skyLevel), THREE.LinearSRGBColorSpace);
    hemi.groundColor.setRGB(...preset.groundLight.map((value) => value / skyLevel), THREE.LinearSRGBColorSpace);
    hemi.intensity = skyLevel;
    sun.color.setRGB(...preset.sunColour, THREE.LinearSRGBColorSpace);
    sun.intensity = preset.sun;
  }

  function lightUnderWater() {
    hemi.color.set(UNDERWATER_DAYLIGHT.sky);
    hemi.groundColor.set(UNDERWATER_DAYLIGHT.ground);
    hemi.intensity = UNDERWATER_DAYLIGHT.hemisphere;
    sun.color.set(UNDERWATER_DAYLIGHT.sun);
    sun.intensity = UNDERWATER_DAYLIGHT.sunIntensity;
    sun.position.fromArray(UNDERWATER_DAYLIGHT.sunPosition);
    sun.target.position.set(0, 0, 0);
  }

  // Every mesh casts and receives sun shadows; only the shadow pass above water makes this visible.
  function flagShadows() {
    scene.traverse(function flag(object) {
      if (!object.isMesh || object === sea || object === sky) return;
      const material = Array.isArray(object.material) ? object.material[0] : object.material;
      if (!material?.isMeshStandardMaterial || object.userData.daylightShadow === false) return;
      object.castShadow = true;
      object.receiveShadow = true;
    });
  }

  // Above water the sun stands in the preset's direction around a point ahead of the camera, which is also the
  // centre of the shadow map.
  function aimSun(camera) {
    camera.getWorldDirection(forward);
    focus.copy(camera.position).addScaledVector(forward, SHADOW_HALF * 0.6);
    focus.y = Math.max(-2, Math.min(focus.y, 6));
    sun.target.position.copy(focus);
    sun.position.copy(focus).addScaledVector(direction, 200);
  }

  function updateShadows(renderer, wanted) {
    const enabled = !!renderer?.shadowMap.enabled;
    sun.castShadow = enabled;
    if (!enabled) return;
    if (++scanAge >= SHADOW_SCAN_FRAMES) {
      scanAge = 0;
      flagShadows();
    }
    if (!wanted) {
      if (shadowsLive) parkShadow(sun);
      shadowsLive = false;
      return;
    }
    const sharp = renderer.getPixelRatio() > 1;
    aimShadow(sun, sharp ? 2048 : 1024);
    shadowsLive = true;
  }

  /**
   * Per frame, before rendering. `view` is the camera mode: the top-down map view keeps the underwater rig and
   * no sea so the vehicle stays visible from above. `surface` (the viewer's flat surface) is hidden while the
   * sea shows. Automatic quality's fallback (effects suppressed) drops the shadow pass.
   */
  function update({camera, world = null, dt = 0, view = 'chase', surface = null, renderer = null} = {}) {
    const effectsSuppressed = !!(renderer && renderQualityState(renderer)?.effectsSuppressed);
    const name = daylightPresetFor(world);
    const waterType = world?.scenario?.water_type ?? null;
    const key = `${name}|${waterType}`;
    if (key !== presetName) {
      presetName = key;
      applyPreset(name, waterType);
      above = null;
    }
    const nowAbove = camera.position.y > 0 && view !== 'top';
    sky.visible = nowAbove;
    sea.visible = nowAbove;
    if (surface) surface.visible = view === 'top' ? camera.position.y < 0 : !nowAbove;
    if (nowAbove !== above) {
      above = nowAbove;
      if (nowAbove) lightAboveWater();
      else lightUnderWater();
    }
    if (nowAbove) aimSun(camera);
    updateShadows(renderer, nowAbove && preset.sun > 1 && !effectsSuppressed);
    scene.userData.daylightMetering = nowAbove ? daylightMetering(preset) : null;
    scene.userData.daylightHaze = nowAbove ? {colour: uniforms.uHorizon.value, rate: 1 / preset.hazeDistance}
      : null;
    if (!nowAbove) return false;
    sky.position.copy(camera.position);
    sea.position.set(camera.position.x, 0, camera.position.z);
    sea.material.uniforms.uTime.value += dt;
    sky.material.uniforms.uCloudTime.value += dt * 0.0016;
    if (scene.background?.isColor) scene.background.copy(body);
    if (scene.fog) {
      scene.fog.color.setRGB(uniforms.uHorizon.value.x, uniforms.uHorizon.value.y, uniforms.uHorizon.value.z,
        THREE.LinearSRGBColorSpace);
      scene.fog.near = 60;
      scene.fog.far = preset.hazeDistance * 1.6;
    }
    return true;
  }

  function dispose() {
    scene.remove(hemi, sun, sun.target, sky, sea);
    sky.geometry.dispose();
    sky.material.dispose();
    sea.geometry.dispose();
    sea.material.dispose();
    sun.shadow.map?.dispose();
  }

  return {
    hemi, sun, sky, sea, update, dispose,
    get preset() {
      return presetName?.split('|')[0] ?? null;
    },
    get above() {
      return !!above;
    },
    luminance: luminanceOf
  };
}
